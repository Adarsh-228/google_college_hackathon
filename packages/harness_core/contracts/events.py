"""Telemetry and streaming event schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import EventType, ExecutionStatus


class AgentEvent(BaseModel):
    """Structured telemetry event emitted during agent lifecycle."""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    session_id: str = Field(..., description="Target agent session ID.")
    task_id: str = Field(..., description="Target task ID.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType = Field(..., description="Type of event occurred.")
    component: str = Field(..., description="Component emitting event (orchestrator, guard, context, provider).")
    status: ExecutionStatus = Field(ExecutionStatus.RUNNING, description="Current execution status.")
    duration_ms: Optional[float] = Field(None, description="Elapsed milliseconds if step completed.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific attributes.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="System metadata.")
