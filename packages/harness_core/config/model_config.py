"""Model specifications and capability profiles."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ModelProfile(BaseModel):
    """Specification of model limits, cost, and supported features."""
    model_name: str
    provider: str
    context_window: int = 128000
    max_output_tokens: int = 8192
    supports_system_instructions: bool = True
    supports_tools: bool = True
    supports_json_mode: bool = True
    cost_per_1k_input_usd: float = 0.0001
    cost_per_1k_output_usd: float = 0.0004
    description: str = ""


# Default catalog of supported models
MODEL_CATALOG: Dict[str, ModelProfile] = {
    "gemini-2.5-flash": ModelProfile(
        model_name="gemini-2.5-flash",
        provider="google",
        context_window=1048576,
        max_output_tokens=8192,
        supports_system_instructions=True,
        supports_tools=True,
        supports_json_mode=True,
        cost_per_1k_input_usd=0.000075,
        cost_per_1k_output_usd=0.0003,
        description="Fast, low-latency multimodal reasoning model with 1M context."
    ),
    "gemini-2.5-pro": ModelProfile(
        model_name="gemini-2.5-pro",
        provider="google",
        context_window=2097152,
        max_output_tokens=8192,
        supports_system_instructions=True,
        supports_tools=True,
        supports_json_mode=True,
        cost_per_1k_input_usd=0.00125,
        cost_per_1k_output_usd=0.005,
        description="High-capability frontier model for complex architectural coding."
    ),
    "gemini-1.5-flash": ModelProfile(
        model_name="gemini-1.5-flash",
        provider="google",
        context_window=1048576,
        max_output_tokens=8192,
        supports_system_instructions=True,
        supports_tools=True,
        supports_json_mode=True,
        cost_per_1k_input_usd=0.000075,
        cost_per_1k_output_usd=0.0003,
        description="Legacy fast Gemini 1.5 flash model."
    ),
    "mock-coding-model": ModelProfile(
        model_name="mock-coding-model",
        provider="mock",
        context_window=16000,
        max_output_tokens=2048,
        supports_system_instructions=True,
        supports_tools=True,
        supports_json_mode=True,
        cost_per_1k_input_usd=0.0,
        cost_per_1k_output_usd=0.0,
        description="Mock model for unit testing and offline development."
    ),
}


def get_model_profile(model_name: Optional[str] = None) -> ModelProfile:
    """Retrieve model profile from catalog or return safe default."""
    if not model_name:
        return MODEL_CATALOG["gemini-2.5-flash"]
    return MODEL_CATALOG.get(
        model_name,
        ModelProfile(
            model_name=model_name,
            provider="google",
            context_window=128000,
            max_output_tokens=4096,
            description="Fallback generic model profile."
        )
    )
