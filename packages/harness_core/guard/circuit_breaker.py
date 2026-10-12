"""Execution limits and circuit breaker management."""

import time
from typing import Optional

from packages.harness_core.exceptions.errors import (
    CircuitBreakerError,
    ExecutionTimeoutError,
    TaskAbortedError,
)


class ExecutionLimitManager:
    """Enforces execution limits (tool calls, elapsed time, iterations, retries)."""

    def __init__(
        self,
        max_tool_calls: int = 30,
        timeout_seconds: int = 300,
        max_recovery_attempts: int = 5,
        max_iterations: int = 50,
    ) -> None:
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.max_recovery_attempts = max_recovery_attempts
        self.max_iterations = max_iterations

        self.start_time: float = time.time()
        self.tool_calls_count: int = 0
        self.recovery_attempts_count: int = 0
        self.iteration_count: int = 0
        self.is_cancelled: bool = False

    def cancel(self) -> None:
        """Signal cooperative cancellation."""
        self.is_cancelled = True

    def check_limits(self) -> None:
        """Validate that current execution has not exceeded any budget."""
        if self.is_cancelled:
            raise TaskAbortedError("Execution was cancelled by user or system signal.")

        elapsed = time.time() - self.start_time
        if elapsed > self.timeout_seconds:
            raise ExecutionTimeoutError(
                f"Global execution timeout exceeded ({elapsed:.1f}s > {self.timeout_seconds}s)."
            )

        if self.tool_calls_count > self.max_tool_calls:
            raise CircuitBreakerError(
                f"Tool call budget exhausted ({self.tool_calls_count - 1}/{self.max_tool_calls} calls)."
            )

        if self.recovery_attempts_count > self.max_recovery_attempts:
            raise CircuitBreakerError(
                f"Maximum recovery attempts exceeded ({self.recovery_attempts_count}/{self.max_recovery_attempts})."
            )

        if self.iteration_count > self.max_iterations:
            raise CircuitBreakerError(
                f"Maximum iterations exceeded ({self.iteration_count - 1}/{self.max_iterations} iterations)."
            )

    def record_tool_call(self) -> None:
        """Increment tool call count and check limits."""
        self.tool_calls_count += 1
        self.check_limits()

    def record_iteration(self) -> None:
        """Increment iteration count."""
        self.iteration_count += 1
        self.check_limits()

    def record_recovery(self) -> None:
        """Increment recovery attempts."""
        self.recovery_attempts_count += 1
        self.check_limits()


# Backward-compatible alias
CircuitBreaker = ExecutionLimitManager
