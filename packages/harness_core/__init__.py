"""HarnessX Core Intelligence Engine.

Provides adaptive harness orchestration, ContextT4, AgentGuard, tool management,
and telemetry for autonomous coding agents.
"""

from packages.harness_core.agent.orchestrator import HarnessEngine
from packages.harness_core.agent.state import AgentState
from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import (
    ContextStrategy,
    EventType,
    ExecutionStatus,
    HarnessMode,
    ProviderType,
    TaskComplexity,
    ToolPermission,
)
from packages.harness_core.contracts.events import AgentEvent
from packages.harness_core.telemetry.collector import EventHandler, EventSink
from packages.harness_core.contracts.requests import (
    AgentExecutionRequest,
    TaskAnalysisRequest,
    ToolExecutionRequest,
)
from packages.harness_core.contracts.responses import (
    AgentExecutionResponse,
    ContextStatistics,
    DiagnosticResult,
    ExecutionMetrics,
    ExecutionReport,
    PerformanceMetrics,
    TaskPlanStep,
    ToolExecutionResult,
    ToolResult,
)
from packages.harness_core.exceptions.errors import (
    CircuitBreakerError,
    ConfigurationError,
    ContextOverflowError,
    ExecutionTimeoutError,
    GuardViolationError,
    HarnessError,
    LoopDetectedError,
    ModelAuthenticationError,
    ModelRateLimitError,
    PathTraversalError,
    ProviderError,
    SecurityViolationError,
    SessionNotFoundError,
    StaleFileEditError,
    TaskAbortedError,
    ToolExecutionError,
    WorkspaceError,
)
from packages.harness_core.guard.circuit_breaker import (
    CircuitBreaker,
    ExecutionLimitManager,
)
from packages.harness_core.guard.diagnostics import (
    CodeDiagnosticsGuard,
    PostEditDiagnostics,
)
from packages.harness_core.guard.file_integrity import (
    FileIntegrityGuard,
    FileStateValidator,
    ReadBeforeWriteValidator,
)
from packages.harness_core.guard.interceptor import AgentGuard
from packages.harness_core.guard.loop_detector import (
    LoopCheckResult,
    LoopDetector,
    RepeatedCallDetector,
)
from packages.harness_core.guard.permission_manager import PermissionManager
from packages.harness_core.guard.workspace_protection import WorkspaceProtection
from packages.harness_core.providers.base import (
    BaseLLMProvider,
    BaseModelProvider,
)
from packages.harness_core.providers.gemini_provider import GeminiProvider
from packages.harness_core.providers.mock_provider import MockLLMProvider, MockModelProvider
from packages.harness_core.providers.provider_factory import ProviderFactory
from packages.harness_core.providers.vertex_provider import VertexAIProvider
from packages.harness_core.tools.file_tools import (
    EditFileTool,
    ListDirectoryTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from packages.harness_core.tools.registry import ToolRegistry
from packages.harness_core.tools.terminal_tools import (
    RunTerminalCommandTool,
    RunTerminalTool,
)

__version__ = "0.1.0"

__all__ = [
    # Facade
    "HarnessEngine",
    "EngineConfig",
    "AgentState",
    # Enums
    "ExecutionStatus",
    "HarnessMode",
    "ContextStrategy",
    "EventType",
    "ProviderType",
    "TaskComplexity",
    "ToolPermission",
    # Contracts
    "AgentExecutionRequest",
    "AgentExecutionResponse",
    "ToolExecutionRequest",
    "ToolExecutionResult",
    "TaskAnalysisRequest",
    "DiagnosticResult",
    "ContextStatistics",
    "PerformanceMetrics",
    "ExecutionMetrics",
    "TaskPlanStep",
    "ExecutionReport",
    "AgentEvent",
    "EventHandler",
    "EventSink",
    # Providers
    "BaseModelProvider",
    "BaseLLMProvider",
    "GeminiProvider",
    "VertexAIProvider",
    "MockModelProvider",
    "MockLLMProvider",
    "ProviderFactory",
    # Tools & Registry
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListFilesTool",
    "ListDirectoryTool",
    "SearchFilesTool",
    "RunTerminalCommandTool",
    "RunTerminalTool",
    "ToolRegistry",
    # AgentGuard Safety & Reliability Components
    "AgentGuard",
    "FileStateValidator",
    "ReadBeforeWriteValidator",
    "FileIntegrityGuard",
    "PostEditDiagnostics",
    "CodeDiagnosticsGuard",
    "RepeatedCallDetector",
    "LoopDetector",
    "LoopCheckResult",
    "ExecutionLimitManager",
    "CircuitBreaker",
    "WorkspaceProtection",
    "PermissionManager",
    # Exceptions
    "HarnessError",
    "ConfigurationError",
    "ProviderError",
    "ModelAuthenticationError",
    "ModelRateLimitError",
    "ContextOverflowError",
    "GuardViolationError",
    "StaleFileEditError",
    "SecurityViolationError",
    "LoopDetectedError",
    "CircuitBreakerError",
    "WorkspaceError",
    "PathTraversalError",
    "ToolExecutionError",
    "ExecutionTimeoutError",
    "SessionNotFoundError",
    "TaskAbortedError",
]
