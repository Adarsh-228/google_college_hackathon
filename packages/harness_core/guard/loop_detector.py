"""Repeated call detection and infinite loop monitoring."""

import json
from typing import Any, Dict, Optional
from pydantic import BaseModel

from packages.harness_core.exceptions.errors import LoopDetectedError


class LoopCheckResult(BaseModel):
    """Status returned after checking a tool call signature."""
    is_repeated: bool = False
    repeat_count: int = 1
    is_warning: bool = False
    is_stalled: bool = False
    message: Optional[str] = None


class RepeatedCallDetector:
    """Monitors consecutive tool calls using normalized signatures to catch loops."""

    def __init__(
        self,
        warning_threshold: int = 5,
        stall_threshold: int = 8,
    ) -> None:
        self.warning_threshold = warning_threshold
        self.stall_threshold = stall_threshold
        self._last_signature: Optional[str] = None
        self._consecutive_count: int = 0
        self._consecutive_failures: int = 0
        self.total_repeated_calls: int = 0

    def _normalize_signature(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Create a deterministic hash string from tool name and arguments."""
        try:
            norm_args = json.dumps(arguments, sort_keys=True)
        except Exception:
            norm_args = str(sorted(arguments.items()))
        return f"{tool_name}::{norm_args}"

    def record_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        success: bool,
    ) -> LoopCheckResult:
        """Record and analyze a tool execution call."""
        sig = self._normalize_signature(tool_name, arguments)

        if sig == self._last_signature:
            self._consecutive_count += 1
            self.total_repeated_calls += 1
            if not success:
                self._consecutive_failures += 1
            else:
                self._consecutive_failures = 0
        else:
            self._last_signature = sig
            self._consecutive_count = 1
            self._consecutive_failures = 1 if not success else 0

        is_warning = self._consecutive_count >= self.warning_threshold
        is_stalled = self._consecutive_failures >= self.stall_threshold

        msg = None
        if is_stalled:
            msg = (
                f"Loop Protection: Tool '{tool_name}' failed {self._consecutive_failures} "
                f"consecutive times with identical arguments. Terminating execution."
            )
            raise LoopDetectedError(msg)
        elif is_warning:
            msg = (
                f"Loop Warning: Tool '{tool_name}' invoked {self._consecutive_count} consecutive "
                f"times with identical parameters. Re-evaluate strategy."
            )

        return LoopCheckResult(
            is_repeated=(self._consecutive_count > 1),
            repeat_count=self._consecutive_count,
            is_warning=is_warning,
            is_stalled=is_stalled,
            message=msg,
        )


# Backward-compatible alias
LoopDetector = RepeatedCallDetector
