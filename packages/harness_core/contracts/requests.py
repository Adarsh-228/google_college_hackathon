"""Request schemas for HarnessX agent engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import (
    ContextStrategy,
    HarnessMode,
    TaskComplexity,
)


class AgentExecutionRequest(BaseModel):
    """Client request to start an autonomous agent task."""
    task: str = Field(..., description="User coding task prompt or requirement specification")
    session_id: Optional[str] = Field(None, description="Optional unique session ID. Generated if empty.")
    workspace_dir: Optional[str] = Field(None, description="Relative or absolute target workspace root.")
    harness_mode: Optional[HarnessMode] = Field(None, description="Requested mode (GUIDED, DIRECT, HYBRID). Auto-selected if None.")
    context_strategy: Optional[ContextStrategy] = Field(None, description="Context management strategy (defaults to T4_STAGED).")
    model_name: Optional[str] = Field(None, description="Target LLM model identifier (e.g. gemini-2.5-flash).")
    timeout_seconds: Optional[int] = Field(300, description="Max execution time in seconds before timeout.")
    max_tool_calls: Optional[int] = Field(30, description="Max tool invocations allowed in this session.")
    allow_network: bool = Field(False, description="Whether network commands are allowed in sandbox.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary client metadata.")


class ToolExecutionRequest(BaseModel):
    """Payload for invoking a tool through AgentGuard."""
    tool_name: str = Field(..., description="Registered tool identifier.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool parameter arguments.")
    session_id: str = Field(..., description="Current agent session identifier.")
    step_index: int = Field(0, description="Sequence index of the current execution step.")


class TaskAnalysisRequest(BaseModel):
    """Input payload for analyzing complexity and recommending harness parameters."""
    task_description: str = Field(..., description="Raw task prompt.")
    available_files: List[str] = Field(default_factory=list, description="Existing workspace file listing.")
    preferred_mode: Optional[HarnessMode] = Field(None, description="User preference override.")
