import os
import time
from typing import Generator, Dict, Any, Optional
from .types import HarnessConfig, CircuitBreakerError, ContextOverflowError
from .guard import AgentGuard
from .context_t4 import ContextT4Manager
from .planning import PlanningEngine
from .tools import ToolRegistry
from .providers import VertexAIClient, MockLLMClient

def run_agent_task(
    workspace_path: str,
    task_prompt: str,
    model_id: str = "gemini-2.5-flash",
    harness_config: Optional[Dict[str, Any]] = None,
    client: Any = None,
    max_steps: int = 40,
) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """
    Core ReAct agent execution engine yielding live turn events.
    Fulfills Person 1's interface contract to Person 2.
    """
    config = HarnessConfig.from_dict(harness_config)
    config.max_turns = max_steps
    workspace_path = os.path.realpath(workspace_path)

    # Initialize components
    guard = AgentGuard(workspace_path, config)
    context_manager = ContextT4Manager(config)
    planning_engine = PlanningEngine(enabled=config.enable_planning)
    tool_registry = ToolRegistry(workspace_path, guard)

    # Resolve model client
    if client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
        if api_key or gcp_project:
            try:
                client = VertexAIClient(model_id=model_id, project_id=gcp_project, api_key=api_key)
            except Exception:
                client = MockLLMClient(scenario=os.path.basename(workspace_path))
        else:
            client = MockLLMClient(scenario=os.path.basename(workspace_path))

    # Base System Prompt
    system_prompt = (
        "You are an expert autonomous software engineering agent operating inside a code repository.\n"
        f"Goal: {task_prompt}\n"
        "Workflow:\n"
        "1. Explore and locate the bug.\n"
        "2. Read target files fully with read_file before editing.\n"
        "3. Make surgical edits with edit_file.\n"
        "4. Verify the fix with bash pytest.\n"
        "5. Conclude when verified."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task_prompt}"},
    ]

    # Metrics state
    tokens_in_uncached = 0
    tokens_in_cached = 0
    tokens_out = 0
    total_cost_usd = 0.0
    turn_idx = 0
    stop_reason = "MAX_TURNS"
    resolved = False
    re_patch_count = 0
    edited_files = set()

    # Rate cards for Gemini 2.5 Flash ($ / 1M tokens)
    COST_PER_M_UNCACHED_IN = 0.075
    COST_PER_M_CACHED_IN = 0.01875
    COST_PER_M_OUT = 0.300

    while turn_idx < max_steps:
        turn_idx += 1
        
        # 1. Yield TURN_START
        yield {
            "turn_idx": turn_idx,
            "type": "TURN_START",
            "data": {
                "turn": turn_idx,
                "current_plan": planning_engine.current_plan,
                "estimated_tokens": context_manager.estimate_tokens(messages),
                "budget_cap": config.budget_cap,
            },
        }

        # 2. Context Compaction Gate (ContextT4)
        try:
            messages, compaction_badge = context_manager.process_turn(messages)
            if compaction_badge:
                yield {
                    "turn_idx": turn_idx,
                    "type": "COMPACTION",
                    "data": {
                        "badge": compaction_badge,
                        "m1_count": context_manager.m1_elision_count,
                        "m3_count": context_manager.m3_summary_count,
                        "tokens_after": context_manager.estimate_tokens(messages),
                    },
                }
        except ContextOverflowError as coe:
            yield {
                "turn_idx": turn_idx,
                "type": "ERROR",
                "data": {"reason": "CONTEXT_OVERFLOW", "message": str(coe)},
            }
            stop_reason = "CONTEXT_OVERFLOW"
            resolved = False
            break

        # 3. Dynamic Plan Injection (fresh per turn)
        turn_messages = list(messages)
        if config.enable_planning:
            plan_reminder = planning_engine.format_plan_reminder()
            if plan_reminder:
                turn_messages.append({"role": "system", "content": plan_reminder})

        # 4. Invoke LLM
        try:
            response = client.generate(turn_messages, system_prompt=system_prompt)
        except Exception as e:
            yield {
                "turn_idx": turn_idx,
                "type": "ERROR",
                "data": {"message": f"LLM Generation Error: {str(e)}"},
            }
            stop_reason = "ERROR"
            break

        # Accumulate tokens & cache-aware cost
        tokens_in_uncached += response.tokens_in_uncached
        tokens_in_cached += response.tokens_in_cached
        tokens_out += response.tokens_out
        turn_cost = (
            (response.tokens_in_uncached * COST_PER_M_UNCACHED_IN / 1_000_000)
            + (response.tokens_in_cached * COST_PER_M_CACHED_IN / 1_000_000)
            + (response.tokens_out * COST_PER_M_OUT / 1_000_000)
        )
        total_cost_usd += turn_cost

        # Append assistant reasoning to history
        messages.append({"role": "assistant", "content": response.content})

        # 5. Check if model completed without tool calls
        if not response.tool_calls:
            # Model declared completion
            if "complete" in response.content.lower() or "fixed" in response.content.lower():
                resolved = True
                stop_reason = "RESOLVED"
            else:
                stop_reason = "AGENT_SUBMITTED"
            
            yield {
                "turn_idx": turn_idx,
                "type": "RUN_FINISH",
                "data": {
                    "resolved": resolved,
                    "stop_reason": stop_reason,
                    "final_message": response.content,
                },
            }
            break

        # 6. Execute Tool Calls
        for tc in response.tool_calls:
            tool_name = tc.get("name", "")
            args = tc.get("args", {})

            yield {
                "turn_idx": turn_idx,
                "type": "TOOL_CALL",
                "data": {"tool": tool_name, "args": args},
            }

            # Streak Circuit Breaker Evaluation
            streak_warn, should_terminate = guard.evaluate_streak(tool_name, args, is_error=False)
            if streak_warn:
                yield {
                    "turn_idx": turn_idx,
                    "type": "GUARD_EVENT",
                    "data": {"badge": "STREAK_WARNING", "message": streak_warn},
                }
            if should_terminate:
                yield {
                    "turn_idx": turn_idx,
                    "type": "ERROR",
                    "data": {"badge": "CIRCUIT_BREAKER_STUCK", "message": streak_warn},
                }
                stop_reason = "CIRCUIT_BREAKER_STUCK"
                break

            # Execute tool
            output = ""
            is_error = False
            guard_badge = None

            if tool_name == "update_plan":
                output = planning_engine.update_plan(args.get("plan", []))
                yield {
                    "turn_idx": turn_idx,
                    "type": "PLAN_UPDATE",
                    "data": {"current_plan": planning_engine.current_plan},
                }
            elif tool_name == "recall_event":
                output = context_manager.recall_event(args.get("id", ""))
            else:
                # Track re-patch metric
                if tool_name in ("edit_file", "write_file"):
                    p = args.get("path", "")
                    if p in edited_files:
                        re_patch_count += 1
                    else:
                        edited_files.add(p)

                output, is_error, guard_badge = tool_registry.execute_tool(tool_name, args)

            # Cap tool output size
            output = context_manager.truncate_tool_output(output)

            # Check for Guard Badges
            if guard_badge:
                yield {
                    "turn_idx": turn_idx,
                    "type": "GUARD_EVENT",
                    "data": {"badge": guard_badge, "tool": tool_name, "output": output[:300]},
                }

            yield {
                "turn_idx": turn_idx,
                "type": "TOOL_RESULT",
                "data": {"tool": tool_name, "output": output, "is_error": is_error},
            }

            # Append tool result to conversation history
            messages.append({"role": "tool", "content": output, "name": tool_name})

        if stop_reason == "CIRCUIT_BREAKER_STUCK":
            break

    # Return final results dictionary
    return {
        "resolved": resolved,
        "stop_reason": stop_reason,
        "total_turns": turn_idx,
        "total_cost_usd": round(total_cost_usd, 6),
        "tokens_in_uncached": tokens_in_uncached,
        "tokens_in_cached": tokens_in_cached,
        "tokens_out": tokens_out,
        "m1_count": context_manager.m1_elision_count,
        "m3_count": context_manager.m3_summary_count,
        "guard_events_count": len(guard.session_file_state),
        "re_patch_count": re_patch_count,
        "current_plan": planning_engine.current_plan,
    }
