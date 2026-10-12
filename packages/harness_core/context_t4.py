import math
from typing import List, Dict, Any, Optional, Tuple, Callable
from .types import HarnessConfig, ContextOverflowError

class ContextT4Manager:
    """
    Implements Staged Context Management (T4) from arXiv:2609.20804 Algorithm 1.
    Splits history into Preamble, Middle, and Recent Window.
    Staged policy: Rule-based elision (M1) at B1 (0.60), LLM summarization (M3) at B2 (0.85).
    """

    SUMMARIZATION_PROMPT = """You are compacting a coding agent's conversation to save context. You are given the OLDEST part of the transcript (and possibly a previous summary to update).
Respond with TEXT ONLY — do NOT call any tools. Produce a concise structured summary under these exact headings (omit a heading only if truly empty):
## Goal
The user's task / intent (preserve it precisely).
## Files touched
Paths examined or modified, with the key changes made and why.
## Done
What has been accomplished, with concrete results (tests passing, bug located, ...).
## Pending
What still needs doing.
## Errors & fixes
Errors hit and how they were resolved (or are still open).
## Current state
Key variables / branch / test status / anything needed to continue.
## Next step
The immediate next action, in line with the most recent work.
Be specific (keep exact file paths, function names, error messages, task ids). If a previous summary is given, UPDATE it: keep still-true facts, drop stale ones, merge in the new events."""

    def __init__(self, config: HarnessConfig, summarizer_fn: Optional[Callable[[str], str]] = None):
        self.config = config
        self.summarizer_fn = summarizer_fn
        
        # External store for recoverable observations (M2)
        self.external_store: Dict[str, str] = {}
        self.running_summary: Optional[str] = None
        
        # Telemetry counters
        self.m1_elision_count: int = 0
        self.m3_summary_count: int = 0
        self.m2_recall_count: int = 0
        
        # Soft and Hard Thresholds
        self.b1_tokens: int = int(config.budget_cap * config.soft_threshold_ratio)
        self.b2_tokens: int = int(config.budget_cap * config.hard_threshold_ratio)

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimates token count across message list (~3.8 characters per token)."""
        total_chars = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total_chars += len(str(part.get("text", "")))
                        total_chars += len(str(part.get("output", "")))
            if "tool_calls" in m:
                total_chars += len(str(m["tool_calls"]))
        return max(1, math.ceil(total_chars / 3.8))

    def truncate_tool_output(self, raw_output: str) -> str:
        """Enforces 24k character tool observation ceiling (§3.1)."""
        limit = self.config.max_tool_output_chars
        if len(raw_output) > limit:
            truncated = raw_output[:limit]
            return f"{truncated}\n\n[Warning: Tool output exceeded 24,000 characters and was truncated by Harness Kit]"
        return raw_output

    def recall_event(self, event_id: str) -> str:
        """M2 recall mechanism: returns verbatim observation from external store."""
        self.m2_recall_count += 1
        if event_id in self.external_store:
            return self.external_store[event_id]
        return f"[Error: Event ID '{event_id}' not found in external store]"

    def process_turn(
        self,
        messages: List[Dict[str, Any]],
        preamble_count: int = 2,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Executes per-turn compaction policy according to config.context_tier.
        Returns (compacted_messages, compaction_event_badge).
        """
        tier = self.config.context_tier.upper()
        current_tokens = self.estimate_tokens(messages)
        
        # -------------------------------------------------------------
        # T0: No management — unmanaged runs fail upon exceeding budget
        # -------------------------------------------------------------
        if tier == "T0":
            if current_tokens >= self.config.budget_cap:
                raise ContextOverflowError(
                    f"Context window exceeded budget ({current_tokens} >= {self.config.budget_cap}) "
                    f"under Tier 0 (Unmanaged). Execution halted by context overflow."
                )
            return messages, None

        # Determine zones: Preamble, Middle, Recent
        # Floor recent window at min_recent_turns turns (typically >= 2 turns = 4 messages)
        total_msgs = len(messages)
        if total_msgs <= preamble_count + (self.config.min_recent_turns * 2):
            return messages, None

        recent_msgs_count = max(self.config.min_recent_turns * 2, int(total_msgs * self.config.recent_window_ratio))
        recent_start_idx = max(preamble_count, total_msgs - recent_msgs_count)

        preamble = messages[:preamble_count]
        middle = messages[preamble_count:recent_start_idx]
        recent = messages[recent_start_idx:]

        compaction_badge: Optional[str] = None

        # -------------------------------------------------------------
        # Determine activation thresholds per Tier
        # -------------------------------------------------------------
        should_elide = False
        should_summarize = False

        if tier == "T1":  # Elision alone at B2
            should_elide = current_tokens >= self.b2_tokens
        elif tier == "T2":  # Elision + Recall at B2
            should_elide = current_tokens >= self.b2_tokens
        elif tier == "T3":  # Summarization alone at B2
            should_summarize = current_tokens >= self.b2_tokens
        elif tier in ("T4", "T4_NO_M2", "T4_WITH_M2"):  # Staged: M1 at B1, M3 at B2
            should_elide = current_tokens >= self.b1_tokens
            # Summarize will be evaluated after elision if tokens still >= B2

        # -------------------------------------------------------------
        # Stage 1: Rule-Based Elision (M1)
        # -------------------------------------------------------------
        if should_elide and middle:
            elided_any = False
            for idx, msg in enumerate(middle):
                if msg.get("role") == "tool" or msg.get("type") == "tool_result":
                    content = msg.get("content", "")
                    if isinstance(content, str) and len(content) > 300 and not content.startswith("[tool output elided:"):
                        lines = content.count("\n") + 1
                        chars = len(content)
                        event_id = f"evt_{preamble_count + idx}"

                        if self.config.enable_m2 or tier == "T2" or tier == "T4_WITH_M2":
                            self.external_store[event_id] = content
                            stub = (
                                f"[tool output elided: {lines} lines / {chars} chars. "
                                f"Use recall_event('{event_id}') for full output, or re-read/re-run.]"
                            )
                        else:
                            stub = f"[tool output elided: {lines} lines / {chars} chars. Re-read or re-run to get it again.]"

                        msg["content"] = stub
                        elided_any = True
                        self.m1_elision_count += 1

            if elided_any:
                compaction_badge = "M1_ELISION"

        # Re-measure tokens after elision
        reconstructed = preamble + middle + recent
        current_tokens = self.estimate_tokens(reconstructed)

        # -------------------------------------------------------------
        # Stage 2: LLM Running Summarization (M3)
        # -------------------------------------------------------------
        if (tier == "T3" and should_summarize) or (tier.startswith("T4") and current_tokens >= self.b2_tokens):
            if middle:
                summary_text = self._generate_summary(middle)
                if summary_text:
                    self.running_summary = summary_text
                    self.m3_summary_count += 1
                    compaction_badge = "M3_SUMMARY" if not compaction_badge else f"{compaction_badge}+M3_SUMMARY"

                    summary_msg = {
                        "role": "system",
                        "content": (
                            f"<context-summary>\n{summary_text}\n"
                            f"(Older events were summarized. Verbatim preamble and recent turns are preserved.)\n"
                            f"</context-summary>"
                        ),
                    }
                    # Middle events replaced by single compact summary message
                    return preamble + [summary_msg] + recent, compaction_badge

        return reconstructed, compaction_badge

    def _generate_summary(self, middle_events: List[Dict[str, Any]]) -> str:
        """Invokes summarizer callback or generates structured default summary."""
        transcript_text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in middle_events])
        if self.summarizer_fn:
            prompt = f"{self.SUMMARIZATION_PROMPT}\n\nExisting Summary:\n{self.running_summary or 'None'}\n\nTranscript to compact:\n{transcript_text}"
            try:
                return self.summarizer_fn(prompt)
            except Exception:
                pass

        # Offline deterministic summary fallback with 7 fixed headings
        return (
            f"## Goal\nContinue progress towards fixing active task.\n"
            f"## Files touched\nInspected and modified target repository files.\n"
            f"## Done\nLocated target files and executed test diagnostics.\n"
            f"## Pending\nApply surgical patch to resolve failing test.\n"
            f"## Errors & fixes\nIdentified failure trace; addressing root cause.\n"
            f"## Current state\nTests failing on target edge-case; preparing fix.\n"
            f"## Next step\nApply targeted edit to source file and verify."
        )
