"""Exception classes for HarnessX core agent engine."""

from typing import Any, Dict, Optional


class HarnessError(Exception):
    """Base exception for all HarnessX errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(HarnessError):
    """Raised when engine or environment configuration is invalid."""
    pass


class ProviderError(HarnessError):
    """Base exception for LLM provider errors."""
    pass


class ModelAuthenticationError(ProviderError):
    """Raised when API credentials or permissions fail."""
    pass


class ModelRateLimitError(ProviderError):
    """Raised when model inference hits quota or rate limits."""
    pass


class ContextOverflowError(HarnessError):
    """Raised when context token limit is exceeded even after compression."""
    pass


class GuardViolationError(HarnessError):
    """Base exception for AgentGuard security and integrity violations."""
    pass


class StaleFileEditError(GuardViolationError):
    """Raised when an edit is attempted on a file modified since last read."""
    pass


class SecurityViolationError(GuardViolationError):
    """Raised when an unsafe operation, path traversal, or forbidden command is detected."""
    pass


class LoopDetectedError(GuardViolationError):
    """Raised when repeated identical failing tool calls trigger loop protection."""
    pass


class CircuitBreakerError(GuardViolationError):
    """Raised when execution limits (time, calls, retries) are exhausted."""
    pass


class WorkspaceError(HarnessError):
    """Base exception for workspace management operations."""
    pass


class PathTraversalError(WorkspaceError, SecurityViolationError):
    """Raised when file path escapes the configured workspace root."""
    pass


class ToolExecutionError(HarnessError):
    """Raised when a registered tool fails to execute properly."""
    pass


class ExecutionTimeoutError(HarnessError):
    """Raised when task execution duration exceeds timeout limits."""
    pass


class SessionNotFoundError(HarnessError):
    """Raised when querying a non-existent or expired session."""
    pass


class TaskAbortedError(HarnessError):
    """Raised when task is explicitly cancelled by the user/system."""
    pass
