"""Metrics calculation and tracking."""

from typing import Optional

from packages.harness_core.config.model_config import get_model_profile
from packages.harness_core.contracts.enums import ExecutionStatus
from packages.harness_core.contracts.responses import PerformanceMetrics


class MetricsTracker:
    """Tracks token consumption, inference cost, tool calls, and diagnostics."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.profile = get_model_profile(model_name)
        self.metrics = PerformanceMetrics()

    def record_inference(self, in_tokens: int, out_tokens: int) -> None:
        """Add input/output tokens and update estimated dollar cost."""
        self.metrics.input_tokens += in_tokens
        self.metrics.output_tokens += out_tokens
        self.metrics.total_tokens = self.metrics.input_tokens + self.metrics.output_tokens

        # Estimated cost in USD
        cost_in = (in_tokens / 1000.0) * self.profile.cost_per_1k_input_usd
        cost_out = (out_tokens / 1000.0) * self.profile.cost_per_1k_output_usd
        self.metrics.estimated_cost_usd = round(
            self.metrics.estimated_cost_usd + cost_in + cost_out, 6
        )

    def record_tool_call(self, is_repeated: bool = False) -> None:
        """Increment tool call metrics."""
        self.metrics.tool_call_count += 1
        if is_repeated:
            self.metrics.repeated_call_count += 1

    def record_diagnostic(self, count: int = 1) -> None:
        """Record syntax or lint diagnostics encountered."""
        self.metrics.diagnostic_count += count

    def record_recovery(self) -> None:
        """Record a successful or attempted error recovery."""
        self.metrics.recovery_count += 1

    def record_tokens_saved(self, tokens: int) -> None:
        """Record estimated tokens saved by context elision."""
        self.metrics.tokens_saved_estimate += tokens

    def set_duration(self, seconds: float) -> None:
        """Record total execution duration."""
        self.metrics.execution_duration_seconds = round(seconds, 2)

    def set_final_status(self, status: ExecutionStatus) -> None:
        """Record terminal execution status."""
        self.metrics.final_status = status

    def get_metrics(self) -> PerformanceMetrics:
        """Return snapshot of current metrics."""
        return self.metrics.model_copy()
