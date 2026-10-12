"""Engine configuration and environment settings."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import ContextStrategy, HarnessMode


class EngineConfig(BaseModel):
    """Central configuration for HarnessEngine runtime."""

    # LLM Provider
    use_vertex: bool = Field(default=False, description="Whether to route to Vertex AI instead of Google AI Studio.")
    gemini_api_key: Optional[str] = Field(default=None, description="Google AI Studio Gemini API Key.")
    google_cloud_project: Optional[str] = Field(default=None, description="GCP Project ID.")
    gcp_region: str = Field(default="us-central1", description="GCP Region.")
    google_application_credentials: Optional[str] = Field(default=None, description="Path to GCP service credentials JSON.")

    # Model Defaults
    model_name: str = Field(default="gemini-2.5-flash", description="Default model identifier.")
    temperature: float = Field(default=0.2, description="Sampling temperature.")

    # Harness Defaults
    default_harness_mode: HarnessMode = Field(default=HarnessMode.HYBRID, description="Default harness mode.")

    # ContextT4 Thresholds
    context_strategy: ContextStrategy = Field(default=ContextStrategy.T4_STAGED, description="Default context strategy.")
    context_soft_threshold: float = Field(default=0.60, description="Soft threshold triggering elision (fraction 0.0 - 1.0).")
    context_hard_threshold: float = Field(default=0.85, description="Hard threshold triggering LLM summarization.")
    context_window_limit: int = Field(default=128000, description="Effective context window token ceiling.")

    # AgentGuard Limits
    guard_max_tool_calls: int = Field(default=30, description="Maximum allowed tool calls per session.")
    guard_max_loop_attempts: int = Field(default=5, description="Consecutive identical calls triggering warning.")
    guard_max_failed_repeats: int = Field(default=8, description="Consecutive identical failing calls triggering stall.")
    guard_timeout_seconds: int = Field(default=300, description="Timeout ceiling for complete agent execution.")
    enable_ruff: bool = Field(default=True, description="Enable Ruff linter if available on system.")

    # Workspace Sandbox
    workspace_base_dir: str = Field(default="./workspaces", description="Root directory where workspaces are allocated.")
    allow_unsafe_host_execution: bool = Field(default=False, description="Strict sandbox mode flag.")

    @classmethod
    def from_env(cls) -> "EngineConfig":
        """Load configuration from environment variables."""
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass

        def _get_bool(key: str, default: bool) -> bool:
            val = os.getenv(key)
            if val is None:
                return default
            return val.strip().lower() in ("1", "true", "yes", "on")

        def _get_float(key: str, default: float) -> float:
            val = os.getenv(key)
            if val is None:
                return default
            try:
                return float(val.strip())
            except ValueError:
                return default

        def _get_int(key: str, default: int) -> int:
            val = os.getenv(key)
            if val is None:
                return default
            try:
                return int(val.strip())
            except ValueError:
                return default

        raw_mode = os.getenv("HARNESS_DEFAULT_MODE", "HYBRID").upper()
        harness_mode = HarnessMode.HYBRID
        try:
            harness_mode = HarnessMode(raw_mode)
        except ValueError:
            harness_mode = HarnessMode.HYBRID

        return cls(
            use_vertex=_get_bool("USE_VERTEX", False),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            gcp_region=os.getenv("GCP_REGION", "us-central1"),
            google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            model_name=os.getenv("HARNESS_MODEL_NAME", "gemini-2.5-flash"),
            default_harness_mode=harness_mode,
            context_soft_threshold=_get_float("CONTEXT_SOFT_THRESHOLD", 0.60),
            context_hard_threshold=_get_float("CONTEXT_HARD_THRESHOLD", 0.85),
            context_window_limit=_get_int("CONTEXT_WINDOW_LIMIT", 128000),
            guard_max_tool_calls=_get_int("GUARD_MAX_TOOL_CALLS", 30),
            guard_max_loop_attempts=_get_int("GUARD_MAX_LOOP_ATTEMPTS", 5),
            guard_max_failed_repeats=_get_int("GUARD_MAX_FAILED_REPEATS", 8),
            guard_timeout_seconds=_get_int("GUARD_TIMEOUT_SECONDS", 300),
            workspace_base_dir=os.getenv("WORKSPACE_BASE_DIR", "./workspaces"),
            allow_unsafe_host_execution=_get_bool("ALLOW_UNSAFE_HOST_EXECUTION", False),
        )

    def sanitized_dict(self) -> dict:
        """Return dict representation with sensitive tokens masked."""
        data = self.model_dump()
        if data.get("gemini_api_key"):
            data["gemini_api_key"] = "***MASKED***"
        if data.get("google_application_credentials"):
            data["google_application_credentials"] = "***MASKED***"
        return data
