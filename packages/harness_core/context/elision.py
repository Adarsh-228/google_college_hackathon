"""Rule-based elision for context management."""

from typing import Dict, List, Set, Tuple
from packages.harness_core.context.preservation import PreservationRules
from packages.harness_core.providers.base import LLMMessage


class RuleBasedElider:
    """Elides bulky historical tool outputs while preserving protected context."""

    def __init__(self, max_observation_chars: int = 300) -> None:
        self.max_chars = max_observation_chars
        # Store elided observations for external recall (T2)
        self.recall_store: Dict[str, str] = {}

    def elide(
        self,
        messages: List[LLMMessage],
        recent_window_size: int = 4,
    ) -> Tuple[List[LLMMessage], int]:
        """Elides bulky tool outputs not in protected set.

        Returns (pruned_messages, chars_saved).
        """
        protected = PreservationRules.identify_protected_indices(
            messages, recent_window_size=recent_window_size
        )

        pruned: List[LLMMessage] = []
        chars_saved = 0

        for idx, msg in enumerate(messages):
            if idx in protected or msg.role != "tool":
                pruned.append(msg)
                continue

            content = msg.content or ""
            if len(content) > self.max_chars:
                # Save full version in recall store for T2
                recall_id = f"recall_{idx}_{msg.tool_name or 'tool'}"
                self.recall_store[recall_id] = content

                head = content[:100]
                tail = content[-100:]
                elided_str = (
                    f"{head}\n... [ELIDED {len(content)} chars: refer to {recall_id}] ...\n{tail}"
                )
                saved = len(content) - len(elided_str)
                chars_saved += max(0, saved)

                # Clone message with truncated content
                cloned = msg.model_copy(
                    update={
                        "content": elided_str,
                        "metadata": {**msg.metadata, "elided": True, "recall_id": recall_id},
                    }
                )
                pruned.append(cloned)
            else:
                pruned.append(msg)

        return pruned, chars_saved
