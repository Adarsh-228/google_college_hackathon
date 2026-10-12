"""Model capability profiling for adaptive harness selection."""

from typing import Dict, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import HarnessMode


class ModelCapability(BaseModel):
    """Empirical capability scores and characteristics of a model."""
    model_name: str
    bash_proficiency_score: float = Field(0.5, description="Score 0.0 to 1.0 in multi-step terminal usage.")
    file_tool_fidelity: float = Field(0.8, description="Score 0.0 to 1.0 in adhering to file tool schemas.")
    long_context_retention: float = Field(0.8, description="Score 0.0 to 1.0 in multi-turn context retention.")
    recommended_mode: HarnessMode = Field(HarnessMode.HYBRID, description="Default optimal harness mode.")
    notes: str = ""


# Empirical model capability profiles
KNOWN_CAPABILITIES: Dict[str, ModelCapability] = {
    "gemini-2.5-pro": ModelCapability(
        model_name="gemini-2.5-pro",
        bash_proficiency_score=0.92,
        file_tool_fidelity=0.96,
        long_context_retention=0.98,
        recommended_mode=HarnessMode.HYBRID,
        notes="High-reasoning frontier model; excels in hybrid file editing and CLI execution.",
    ),
    "gemini-2.5-flash": ModelCapability(
        model_name="gemini-2.5-flash",
        bash_proficiency_score=0.82,
        file_tool_fidelity=0.93,
        long_context_retention=0.92,
        recommended_mode=HarnessMode.HYBRID,
        notes="Fast, highly reliable with structured file tools and moderate terminal tasks.",
    ),
    "gemini-1.5-flash": ModelCapability(
        model_name="gemini-1.5-flash",
        bash_proficiency_score=0.72,
        file_tool_fidelity=0.88,
        long_context_retention=0.85,
        recommended_mode=HarnessMode.GUIDED,
        notes="Best constrained to GUIDED file tools for deterministic code output.",
    ),
    "mock-coding-model": ModelCapability(
        model_name="mock-coding-model",
        bash_proficiency_score=0.9,
        file_tool_fidelity=0.9,
        long_context_retention=0.9,
        recommended_mode=HarnessMode.HYBRID,
        notes="Deterministic mock model profile.",
    ),
}


class CapabilityProfiler:
    """Provides capability profiles for models or returns conservative defaults."""

    @staticmethod
    def get_profile(model_name: Optional[str]) -> ModelCapability:
        """Retrieve known profile or conservative default."""
        if not model_name:
            return KNOWN_CAPABILITIES["gemini-2.5-flash"]

        clean_name = model_name.lower().strip()
        for key, prof in KNOWN_CAPABILITIES.items():
            if key in clean_name:
                return prof

        # Conservative default profile
        return ModelCapability(
            model_name=model_name,
            bash_proficiency_score=0.6,
            file_tool_fidelity=0.75,
            long_context_retention=0.7,
            recommended_mode=HarnessMode.GUIDED,
            notes="Unbenchmarked model: selected conservative GUIDED mode with strict verification.",
        )
