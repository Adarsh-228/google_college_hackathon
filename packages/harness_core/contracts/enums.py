"""Standard enums for HarnessX core agent contracts."""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Lifecycle status of agent execution."""
    PENDING = "PENDING"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALLED = "STALLED"
    CANCELLED = "CANCELLED"


class HarnessMode(str, Enum):
    """Adaptive harness interaction modes."""
    GUIDED = "GUIDED"       # Dedicated file tools, explicit planning, strong verification
    DIRECT = "DIRECT"       # Terminal-oriented interaction, composite commands, lightweight planning
    HYBRID = "HYBRID"       # Unified toolset, adaptive planning and safety guardrails


class ContextStrategy(str, Enum):
    """Context management strategy based on research paper."""
    T0_NONE = "T0_NONE"                   # No context management
    T1_ELISION = "T1_ELISION"             # Rule-based elision
    T2_RECALL = "T2_RECALL"               # Rule-based elision with external recall index
    T3_SUMMARIZATION = "T3_SUMMARIZATION" # LLM-based rolling summarization
    T4_STAGED = "T4_STAGED"               # Staged rule-based elision followed by LLM summarization (Primary)


class ProviderType(str, Enum):
    """Supported LLM backend providers."""
    GEMINI_STUDIO = "GEMINI_STUDIO"
    VERTEX_AI = "VERTEX_AI"
    MOCK = "MOCK"


class TaskComplexity(str, Enum):
    """Classified complexity level of user task."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolPermission(str, Enum):
    """Permission level required by tool."""
    READ_ONLY = "READ_ONLY"
    WRITE_FILE = "WRITE_FILE"
    EXECUTE_TERMINAL = "EXECUTE_TERMINAL"


class EventType(str, Enum):
    """Structured telemetry event types emitted during agent execution."""
    SESSION_STARTED = "session_started"
    TASK_ANALYZED = "task_analyzed"
    PLAN_CREATED = "plan_created"
    MODEL_SELECTED = "model_selected"
    CONTEXT_COMPRESSED = "context_compressed"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    DIAGNOSTIC_GENERATED = "diagnostic_generated"
    LOOP_WARNING = "loop_warning"
    EXECUTION_RECOVERED = "execution_recovered"
    VERIFICATION_COMPLETED = "verification_completed"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"
    SESSION_CANCELLED = "session_cancelled"
