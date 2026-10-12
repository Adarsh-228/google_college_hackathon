"""Agent state definition."""

from typing import List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import (
    ContextStrategy,
    ExecutionStatus,
    HarnessMode,
)
from packages.harness_core.contracts.responses import (
    ContextStatistics,
    PerformanceMetrics,
    TaskPlanStep,
    ToolExecutionResult,
)
from packages.harness_core.providers.base import LLMMessage


class AgentState(BaseModel):
    """Structured runtime state representing the complete agent lifecycle."""
    session_id: str
    task_id: str
    user_task: str
    model_name: str = "gemini-2.5-flash"
    provider: str = "google"
    harness_mode: HarnessMode = HarnessMode.HYBRID
    context_strategy: ContextStrategy = ContextStrategy.T4_STAGED
    execution_status: ExecutionStatus = ExecutionStatus.PENDING

    plan: List[TaskPlanStep] = Field(default_factory=list)
    completed_steps: List[str] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)

    conversation_history: List[LLMMessage] = Field(default_factory=list)
    tool_history: List[ToolExecutionResult] = Field(default_factory=list)
    files_created: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    recovery_attempts: int = 0

    context_statistics: ContextStatistics = Field(default_factory=ContextStatistics)
    execution_metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    final_result: Optional[str] = None
    selection_reasoning: str = ""
