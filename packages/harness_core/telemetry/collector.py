"""Telemetry collector and event broadcaster."""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from packages.harness_core.contracts.enums import EventType, ExecutionStatus
from packages.harness_core.contracts.events import AgentEvent
from packages.harness_core.telemetry.events import create_agent_event
from packages.harness_core.telemetry.metrics import MetricsTracker

logger = logging.getLogger(__name__)

EventHandler = Callable[[AgentEvent], Coroutine[Any, Any, None]]
EventSink = EventHandler


class TelemetryCollector:
    """Collects structured telemetry events and dispatches them to listeners."""

    def __init__(
        self,
        session_id: str,
        task_id: str,
        model_name: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self.task_id = task_id
        self.events: List[AgentEvent] = []
        self.metrics_tracker = MetricsTracker(model_name)
        self._handlers: List[EventHandler] = []

    def register_handler(self, handler: EventHandler) -> None:
        """Register an asynchronous event handler (e.g., Person 2's Firestore/BigQuery pipeline)."""
        self._handlers.append(handler)

    async def emit(
        self,
        event_type: EventType,
        component: str,
        status: ExecutionStatus = ExecutionStatus.RUNNING,
        duration_ms: Optional[float] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentEvent:
        """Construct, record, and asynchronously broadcast an event."""
        event = create_agent_event(
            session_id=self.session_id,
            task_id=self.task_id,
            event_type=event_type,
            component=component,
            status=status,
            duration_ms=duration_ms,
            payload=payload,
            metadata=metadata,
        )

        self.events.append(event)

        # Notify registered listeners
        for h in self._handlers:
            try:
                res = h(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

        return event

    def get_events(self) -> List[AgentEvent]:
        """Return history of all emitted events."""
        return list(self.events)
