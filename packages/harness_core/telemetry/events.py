"""Event factory and dispatcher helpers."""

from typing import Any, Dict, Optional
from uuid import uuid4

from packages.harness_core.contracts.enums import EventType, ExecutionStatus
from packages.harness_core.contracts.events import AgentEvent


def create_agent_event(
    session_id: str,
    task_id: str,
    event_type: EventType,
    component: str,
    status: ExecutionStatus = ExecutionStatus.RUNNING,
    duration_ms: Optional[float] = None,
    payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentEvent:
    """Helper to construct a validated AgentEvent."""
    return AgentEvent(
        event_id=f"evt_{uuid4().hex[:12]}",
        session_id=session_id,
        task_id=task_id,
        event_type=event_type,
        component=component,
        status=status,
        duration_ms=duration_ms,
        payload=payload or {},
        metadata=metadata or {},
    )
