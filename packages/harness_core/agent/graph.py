"""Agent execution workflow graph."""

import asyncio
import logging
import time
from typing import Optional

from packages.harness_core.adaptive.configuration_selector import AdaptiveHarnessSelector
from packages.harness_core.agent.planner import TaskPlanner
from packages.harness_core.agent.state import AgentState
from packages.harness_core.agent.task_analyzer import TaskAnalyzer
from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import EventType, ExecutionStatus, HarnessMode
from packages.harness_core.contracts.requests import ToolExecutionRequest
from packages.harness_core.contracts.responses import ExecutionReport
from packages.harness_core.context.manager import ContextManager
from packages.harness_core.exceptions.errors import (
    CircuitBreakerError,
    ExecutionTimeoutError,
    GuardViolationError,
    LoopDetectedError,
    TaskAbortedError,
)
from packages.harness_core.execution.runner import BaseExecutionRunner
from packages.harness_core.execution.verification import TaskVerifier
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.guard.interceptor import AgentGuard
from packages.harness_core.providers.base import BaseLLMProvider, LLMMessage
from packages.harness_core.telemetry.collector import TelemetryCollector
from packages.harness_core.telemetry.reporter import ExecutionReporter
from packages.harness_core.tools.base import ToolContext
from packages.harness_core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentWorkflowGraph:
    """Orchestrates the autonomous agent graph lifecycle."""

    def __init__(
        self,
        state: AgentState,
        config: EngineConfig,
        provider: BaseLLMProvider,
        workspace: WorkspaceManager,
        runner: BaseExecutionRunner,
        telemetry: TelemetryCollector,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.state = state
        self.config = config
        self.provider = provider
        self.workspace = workspace
        self.runner = runner
        self.telemetry = telemetry
        self.tool_registry = tool_registry or ToolRegistry.create_default()

        self.guard = AgentGuard(
            workspace=self.workspace,
            config=self.config,
            on_event=self._on_guard_event,
        )
        self.verifier = TaskVerifier(self.workspace, self.runner)
        self.context_manager = ContextManager.from_config(
            self.config,
            provider=self.provider,
            strategy_override=self.state.context_strategy,
        )
        self._is_cancelled = False

    def _on_guard_event(self, event_name: str, payload: dict) -> None:
        if event_name == "loop_warning":
            asyncio.create_task(
                self.telemetry.emit(
                    event_type=EventType.LOOP_WARNING,
                    component="agent_guard",
                    status=self.state.execution_status,
                    payload=payload,
                )
            )

    def cancel(self) -> None:
        self._is_cancelled = True
        self.guard.circuit_breaker.cancel()

    async def execute(self) -> ExecutionReport:
        """Run complete autonomous graph execution."""
        start_time = time.time()
        self.state.execution_status = ExecutionStatus.INITIALIZING

        await self.telemetry.emit(
            event_type=EventType.SESSION_STARTED,
            component="orchestrator",
            status=ExecutionStatus.INITIALIZING,
            payload={"task": self.state.user_task, "workspace": str(self.workspace.root)},
        )

        try:
            # 1. Analyze Task
            analyzed = TaskAnalyzer.analyze(self.state.user_task)
            await self.telemetry.emit(
                event_type=EventType.TASK_ANALYZED,
                component="task_analyzer",
                payload=analyzed.model_dump(),
            )

            # 2. Adaptive Harness Selection
            workspace_files = self.workspace.list_files()
            recommendation = AdaptiveHarnessSelector.select_configuration(
                model_name=self.provider.model_name,
                task_description=self.state.user_task,
                user_mode_override=self.state.harness_mode if self.state.harness_mode != HarnessMode.HYBRID else None,
                user_strategy_override=self.state.context_strategy,
                workspace_file_count=len(workspace_files),
            )
            self.state.harness_mode = recommendation.mode
            self.state.context_strategy = recommendation.context_strategy
            self.state.selection_reasoning = recommendation.reasoning

            # Re-sync context manager strategy
            self.context_manager.strategy = self.state.context_strategy

            await self.telemetry.emit(
                event_type=EventType.MODEL_SELECTED,
                component="adaptive_harness",
                payload={
                    "model_name": self.provider.model_name,
                    "harness_mode": self.state.harness_mode.value,
                    "context_strategy": self.state.context_strategy.value,
                    "reasoning": recommendation.reasoning,
                },
            )

            # 3. Plan Generation
            self.state.plan = TaskPlanner.create_initial_plan(analyzed, self.state.harness_mode)
            self.state.pending_steps = [s.description for s in self.state.plan]
            await self.telemetry.emit(
                event_type=EventType.PLAN_CREATED,
                component="planner",
                payload={"plan": [s.model_dump() for s in self.state.plan]},
            )

            # 4. Initialize Conversation History
            system_instruction = (
                f"You are HarnessX Autonomous Coding Agent. You are operating in {self.state.harness_mode.value} mode.\n"
                f"Your goal is: {self.state.user_task}\n"
                f"Adhere to file integrity: you must inspect/read files before modifying them.\n"
                f"Produce robust, syntax-error-free code."
            )
            self.state.conversation_history = [
                LLMMessage(role="system", content=system_instruction),
                LLMMessage(role="user", content=f"Execute coding task: {self.state.user_task}"),
            ]

            # 5. Plan-Act Loop
            self.state.execution_status = ExecutionStatus.RUNNING
            max_turns = self.config.guard_max_tool_calls
            tool_schemas = self.tool_registry.export_schemas_for_mode(self.state.harness_mode)

            for step_idx in range(1, max_turns + 1):
                if self._is_cancelled:
                    raise TaskAbortedError("Execution cancelled by user.")

                self.guard.circuit_breaker.check_limits()

                # Step 5a: Context Management
                pre_compressed_history = await self.context_manager.prepare_context(
                    self.state.conversation_history
                )
                self.state.context_statistics = self.context_manager.get_statistics()
                self.telemetry.metrics_tracker.record_tokens_saved(
                    self.state.context_statistics.tokens_saved_estimate
                )

                if self.state.context_statistics.elided_count > 0 or self.state.context_statistics.summarized_count > 0:
                    await self.telemetry.emit(
                        event_type=EventType.CONTEXT_COMPRESSED,
                        component="context_t4",
                        payload=self.state.context_statistics.model_dump(),
                    )

                # Step 5b: LLM Generation Step
                llm_response = await self.provider.generate(
                    messages=pre_compressed_history,
                    tools=tool_schemas,
                    temperature=self.config.temperature,
                )

                # Track metrics
                self.telemetry.metrics_tracker.record_inference(
                    llm_response.input_tokens, llm_response.output_tokens
                )

                # Record model message
                model_msg = LLMMessage(
                    role="model",
                    content=llm_response.content,
                    tool_calls=llm_response.tool_calls,
                )
                self.state.conversation_history.append(model_msg)

                # If no tool calls, model considers task answered/completed
                if not llm_response.tool_calls:
                    self.state.final_result = llm_response.content
                    break

                # Step 5c: Tool Execution through AgentGuard
                for tc in llm_response.tool_calls:
                    tool = self.tool_registry.get_tool(tc.tool_name)
                    if not tool:
                        # Feed unknown tool error
                        self.state.conversation_history.append(
                            LLMMessage(
                                role="tool",
                                tool_name=tc.tool_name,
                                content=f"Tool '{tc.tool_name}' is not recognized.",
                                metadata={"error": True},
                            )
                        )
                        continue

                    req = ToolExecutionRequest(
                        tool_name=tc.tool_name,
                        arguments=tc.arguments,
                        session_id=self.state.session_id,
                        step_index=step_idx,
                    )

                    await self.telemetry.emit(
                        event_type=EventType.TOOL_CALL_STARTED,
                        component="agent_guard",
                        payload={"tool_name": tc.tool_name, "arguments": tc.arguments},
                    )

                    context = ToolContext(
                        session_id=self.state.session_id,
                        step_index=step_idx,
                        workspace=self.workspace,
                        runner=self.runner,
                    )

                    tool_result = await self.guard.execute_guarded(req, tool, context)
                    self.state.tool_history.append(tool_result)

                    is_repeated = bool(tool_result.metadata.get("loop_warning"))
                    self.telemetry.metrics_tracker.record_tool_call(is_repeated=is_repeated)

                    # Track files touched
                    for touched in tool_result.files_touched:
                        if tool_result.tool_name == "write_file":
                            if touched not in self.state.files_created:
                                self.state.files_created.append(touched)
                        elif tool_result.tool_name == "edit_file":
                            if touched not in self.state.files_modified:
                                self.state.files_modified.append(touched)

                    # Capture diagnostics
                    if tool_result.diagnostics:
                        diag_count = len(tool_result.diagnostics)
                        self.telemetry.metrics_tracker.record_diagnostic(diag_count)
                        await self.telemetry.emit(
                            event_type=EventType.DIAGNOSTIC_GENERATED,
                            component="code_diagnostics",
                            payload={
                                "diagnostics": [d.model_dump() for d in tool_result.diagnostics]
                            },
                        )

                    await self.telemetry.emit(
                        event_type=EventType.TOOL_CALL_COMPLETED,
                        component="agent_guard",
                        duration_ms=tool_result.duration_ms,
                        payload={
                            "tool_name": tc.tool_name,
                            "success": tool_result.success,
                            "output_snippet": str(tool_result.output)[:200],
                            "error": tool_result.error,
                        },
                    )

                    # Feed observation back into conversation
                    tool_obs = (
                        str(tool_result.output)
                        if tool_result.success
                        else f"ERROR: {tool_result.error}"
                    )
                    if tool_result.diagnostics:
                        diag_messages = "\n".join(
                            [f"- [{d.severity}] {d.file_path}: Line {d.line_number}: {d.message}" for d in tool_result.diagnostics]
                        )
                        tool_obs += f"\n[POST-EDIT DIAGNOSTICS DETECTED]:\n{diag_messages}\nPlease fix these issues in the next step."

                    self.state.conversation_history.append(
                        LLMMessage(
                            role="tool",
                            tool_name=tc.tool_name,
                            tool_call_id=tc.call_id,
                            content=tool_obs,
                            metadata={
                                "success": tool_result.success,
                                "files_touched": tool_result.files_touched,
                                "has_diagnostics": bool(tool_result.diagnostics),
                            },
                        )
                    )

            # 6. Verification
            verification = await self.verifier.verify_task()
            await self.telemetry.emit(
                event_type=EventType.VERIFICATION_COMPLETED,
                component="verifier",
                status=ExecutionStatus.COMPLETED if verification.success else ExecutionStatus.FAILED,
                payload=verification.model_dump(),
            )

            # Mark plan steps completed
            self.state.completed_steps = [s.description for s in self.state.plan]
            self.state.pending_steps = []
            self.state.execution_status = (
                ExecutionStatus.COMPLETED if verification.success else ExecutionStatus.FAILED
            )

        except LoopDetectedError as e:
            self.state.execution_status = ExecutionStatus.STALLED
            self.state.errors.append(str(e))
            await self.telemetry.emit(
                event_type=EventType.SESSION_FAILED,
                component="loop_detector",
                status=ExecutionStatus.STALLED,
                payload={"error": str(e)},
            )
        except (CircuitBreakerError, ExecutionTimeoutError) as e:
            self.state.execution_status = ExecutionStatus.FAILED
            self.state.errors.append(str(e))
            await self.telemetry.emit(
                event_type=EventType.SESSION_FAILED,
                component="circuit_breaker",
                status=ExecutionStatus.FAILED,
                payload={"error": str(e)},
            )
        except TaskAbortedError as e:
            self.state.execution_status = ExecutionStatus.CANCELLED
            await self.telemetry.emit(
                event_type=EventType.SESSION_CANCELLED,
                component="orchestrator",
                status=ExecutionStatus.CANCELLED,
                payload={"reason": str(e)},
            )
        except Exception as e:
            self.state.execution_status = ExecutionStatus.FAILED
            self.state.errors.append(str(e))
            await self.telemetry.emit(
                event_type=EventType.SESSION_FAILED,
                component="orchestrator",
                status=ExecutionStatus.FAILED,
                payload={"error": str(e)},
            )
        finally:
            elapsed = time.time() - start_time
            self.telemetry.metrics_tracker.set_duration(elapsed)
            self.telemetry.metrics_tracker.set_final_status(self.state.execution_status)
            self.state.execution_metrics = self.telemetry.metrics_tracker.get_metrics()

            if self.state.execution_status == ExecutionStatus.COMPLETED:
                await self.telemetry.emit(
                    event_type=EventType.SESSION_COMPLETED,
                    component="orchestrator",
                    status=ExecutionStatus.COMPLETED,
                    duration_ms=elapsed * 1000,
                    payload={"metrics": self.state.execution_metrics.model_dump()},
                )

        report = ExecutionReporter.build_report(
            session_id=self.state.session_id,
            task=self.state.user_task,
            status=self.state.execution_status,
            harness_mode=self.state.harness_mode,
            context_strategy=self.state.context_strategy,
            plan=self.state.plan,
            completed_steps=self.state.completed_steps,
            files_created=self.state.files_created,
            files_modified=self.state.files_modified,
            errors_encountered=self.state.errors,
            diagnostics_resolved=self.state.execution_metrics.diagnostic_count,
            metrics=self.state.execution_metrics,
            summary=self.state.final_result or "Task executed successfully.",
        )

        return report
