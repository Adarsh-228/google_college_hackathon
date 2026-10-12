"""Tokenizer abstraction for context measurement."""

from typing import Any, List, Optional
from packages.harness_core.providers.base import BaseLLMProvider, LLMMessage


class ContextTokenizer:
    """Measures message token counts, using exact provider API when available or calibrated estimate."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None) -> None:
        self.provider = provider

    async def count_tokens(self, text_or_messages: Any) -> int:
        """Count tokens of text or message list."""
        if self.provider and hasattr(self.provider, "count_tokens"):
            try:
                return await self.provider.count_tokens(text_or_messages)
            except Exception:
                pass

        # Calibrated fallback estimate: 1 token ~ 3.8 to 4 characters
        if isinstance(text_or_messages, str):
            return max(1, len(text_or_messages) // 4)
        if isinstance(text_or_messages, list):
            chars = 0
            for item in text_or_messages:
                if hasattr(item, "content"):
                    chars += len(item.content or "")
                    if getattr(item, "tool_calls", None):
                        chars += sum(len(str(tc.arguments)) for tc in item.tool_calls)
                elif isinstance(item, str):
                    chars += len(item)
                else:
                    chars += len(str(item))
            return max(1, chars // 4)
        return max(1, len(str(text_or_messages)) // 4)

    def is_exact(self) -> bool:
        """Returns True if provider supports exact counting."""
        if self.provider and hasattr(self.provider, "supports_exact_token_counting"):
            return self.provider.supports_exact_token_counting()
        return False
