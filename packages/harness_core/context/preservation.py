"""Preservation rules for protected context elements."""

from typing import List, Set
from packages.harness_core.providers.base import LLMMessage


class PreservationRules:
    """Enforces non-negotiable retention of critical context items."""

    @staticmethod
    def identify_protected_indices(
        messages: List[LLMMessage],
        recent_window_size: int = 4,
    ) -> Set[int]:
        """Return the set of message indices that must never be removed or elided."""
        protected: Set[int] = set()
        total = len(messages)

        for idx, msg in enumerate(messages):
            # 1. System instructions are strictly preserved
            if msg.role == "system":
                protected.add(idx)

            # 2. Turn 0 (Initial User Task objective)
            elif idx == 0 and msg.role == "user":
                protected.add(idx)

            # 3. First user message if index 0 was system
            elif idx == 1 and msg.role == "user" and messages[0].role == "system":
                protected.add(idx)

            # 4. Critical unresolved errors
            elif msg.role == "tool" and "error" in (msg.metadata or {}):
                protected.add(idx)

        # 5. Recent interactions (last N messages)
        recent_start = max(0, total - recent_window_size)
        for idx in range(recent_start, total):
            protected.add(idx)

        return protected
