"""Deterministic mock LLM provider for testing and offline development."""

from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from packages.harness_core.contracts.enums import ProviderType
from packages.harness_core.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
)


class MockLLMProvider(BaseLLMProvider):
    """Configurable mock provider that supports queued responses or response generators."""

    def __init__(
        self,
        model_name: str = "mock-coding-model",
        custom_responses: Optional[List[LLMResponse]] = None,
        generator_fn: Optional[Callable[[List[LLMMessage]], LLMResponse]] = None,
    ) -> None:
        self._model_name = model_name
        self._queue: List[LLMResponse] = list(custom_responses) if custom_responses else []
        self._generator_fn = generator_fn
        self.call_history: List[List[LLMMessage]] = []

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MOCK

    @property
    def model_name(self) -> str:
        return self._model_name

    def queue_response(self, response: LLMResponse) -> None:
        """Enqueue a mock response."""
        self._queue.append(response)

    def queue_text_response(self, text: str, in_tokens: int = 10, out_tokens: int = 15) -> None:
        """Convenience method to enqueue plain text response."""
        self._queue.append(
            LLMResponse(
                content=text,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                finish_reason="stop",
            )
        )

    def queue_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        thought: str = "Executing tool",
        in_tokens: int = 15,
        out_tokens: int = 20,
    ) -> None:
        """Convenience method to enqueue a tool call."""
        call_id = f"call_{uuid4().hex[:8]}"
        self._queue.append(
            LLMResponse(
                content=thought,
                tool_calls=[
                    LLMToolCall(call_id=call_id, tool_name=tool_name, arguments=arguments)
                ],
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                finish_reason="tool_call",
            )
        )

    def queue_error(self, error: Exception) -> None:
        """Enqueue an exception to simulate provider or API errors."""
        self._queue.append(error)

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.call_history.append(list(messages))

        if self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        if self._generator_fn:
            return self._generator_fn(messages)

        # Default intelligent response behavior based on the last message
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.role == "tool":
            # Tool was just returned, produce final answer
            return LLMResponse(
                content="Task completed successfully based on tool results.",
                input_tokens=100,
                output_tokens=25,
                finish_reason="stop",
            )

        # First turn: default to inspecting workspace
        return LLMResponse(
            content="I will list existing files to assess project structure.",
            tool_calls=[
                LLMToolCall(
                    call_id=f"call_{uuid4().hex[:8]}",
                    tool_name="list_files",
                    arguments={"directory_path": "."},
                )
            ],
            input_tokens=50,
            output_tokens=30,
            finish_reason="tool_call",
        )

    async def count_tokens(self, text_or_messages: Any) -> int:
        if isinstance(text_or_messages, str):
            # Fast mock calculation: ~4 chars per token
            return max(1, len(text_or_messages) // 4)
        if isinstance(text_or_messages, list):
            total_chars = sum(len(m.content) for m in text_or_messages if hasattr(m, "content"))
            return max(1, total_chars // 4)
        return 10

    def supports_exact_token_counting(self) -> bool:
        return False


# Backward-compatible and semantic alias
MockModelProvider = MockLLMProvider
