"""Base LLM Provider interface and message structures."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import ProviderType


class LLMToolCall(BaseModel):
    """Normalized tool call parsed from model response."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class LLMMessage(BaseModel):
    """Normalized message representation across providers."""
    role: str = Field(..., description="user, model, system, or tool")
    content: str = Field("", description="Text content")
    tool_calls: List[LLMToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Normalized completion response from LLM."""
    content: str = ""
    tool_calls: List[LLMToolCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Provider identifier enum."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model name."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate response given conversation history and available tools."""
        pass

    @abstractmethod
    async def count_tokens(self, text_or_messages: Any) -> int:
        """Count tokens using provider API or calibrated fallback."""
        pass

    @abstractmethod
    def supports_exact_token_counting(self) -> bool:
        """Whether token count is exact via provider API or estimated."""
        pass


# Backward-compatible and semantic alias
BaseModelProvider = BaseLLMProvider
