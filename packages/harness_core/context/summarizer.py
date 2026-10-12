"""Structured LLM context summarizer."""

from typing import List, Optional, Tuple
from packages.harness_core.providers.base import BaseLLMProvider, LLMMessage


STRUCTURED_SUMMARY_TEMPLATE = """### CONTEXT SUMMARY (HarnessX ContextT4)
1. **Goal**: {goal}
2. **Files Touched**: {files_touched}
3. **Done**: {done}
4. **Pending**: {pending}
5. **Errors & Fixes**: {errors_and_fixes}
6. **Current State**: {current_state}
7. **Next Step**: {next_step}"""


class ContextSummarizer:
    """Condenses older interaction history into the required 7-section structured summary."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None) -> None:
        self.provider = provider

    async def summarize_history(
        self,
        messages_to_compress: List[LLMMessage],
        original_goal: str,
    ) -> str:
        """Generate 7-section structured summary from history."""
        # Extract files touched and errors observed directly from messages
        files_touched = set()
        errors_found = []
        tools_run = []

        for m in messages_to_compress:
            if m.tool_name:
                tools_run.append(m.tool_name)
            if m.metadata and "files_touched" in m.metadata:
                files_touched.update(m.metadata["files_touched"])
            if m.role == "tool" and ("error" in (m.metadata or {}) or "failed" in (m.content or "").lower()):
                errors_found.append(m.content[:120])

        files_str = ", ".join(sorted(files_touched)) if files_touched else "None recorded yet"
        tools_str = ", ".join(tools_run[-5:]) if tools_run else "Initial discovery"
        errors_str = "; ".join(errors_found[-3:]) if errors_found else "None"

        # If LLM provider is available, use it to refine summary
        if self.provider:
            prompt = (
                f"Summarize the autonomous coding agent history below into the 7 standard headers:\n"
                f"1. Goal: {original_goal}\n"
                f"2. Files Touched: {files_str}\n"
                f"3. Done: Actions completed\n"
                f"4. Pending: Remaining steps\n"
                f"5. Errors & Fixes: {errors_str}\n"
                f"6. Current State: Last known state\n"
                f"7. Next Step: Recommended immediate step\n\n"
                f"Conversation history snippets:\n"
                + "\n".join([f"[{m.role}]: {m.content[:150]}" for m in messages_to_compress[:8]])
            )
            try:
                resp = await self.provider.generate(
                    messages=[
                        LLMMessage(role="system", content="You are a concise context summarizer."),
                        LLMMessage(role="user", content=prompt),
                    ],
                    temperature=0.1,
                    max_output_tokens=500,
                )
                if resp.content and "1. **Goal**" in resp.content or "1. Goal" in resp.content:
                    return resp.content
            except Exception:
                pass

        # Deterministic structured summary fallback
        return STRUCTURED_SUMMARY_TEMPLATE.format(
            goal=original_goal,
            files_touched=files_str,
            done=f"Executed tools: {tools_str}",
            pending="Continue planned implementation tasks",
            errors_and_fixes=errors_str,
            current_state="Intermediate execution checkpoint compressed for context efficiency",
            next_step="Resume current subtask with full attention",
        )
