"""HarnessEngine central public orchestrator facade."""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from packages.harness_core.agent.graph import AgentWorkflowGraph
from packages.harness_core.agent.state import AgentState
from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import (
    ContextStrategy,
    ExecutionStatus,
    HarnessMode,
)
from packages.harness_core.contracts.requests import AgentExecutionRequest
from packages.harness_core.contracts.responses import (
    AgentExecutionResponse,
    PerformanceMetrics,
)
from packages.harness_core.exceptions.errors import SessionNotFoundError
from packages.harness_core.execution.runner import (
    BaseExecutionRunner,
    RestrictedSubprocessRunner,
)
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.providers.base import BaseLLMProvider
from packages.harness_core.providers.provider_factory import ProviderFactory
from packages.harness_core.telemetry.collector import (
    EventHandler,
    TelemetryCollector,
)
from packages.harness_core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class HarnessEngine:
    """The central intelligence engine facade for HarnessX.

    Provides a clean, stable interface for Person 2 (Cloud Backend) and Person 3 (Dashboard).
    """

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        provider: Optional[BaseLLMProvider] = None,
        runner: Optional[BaseExecutionRunner] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.config = config or EngineConfig.from_env()
        self.provider = provider or ProviderFactory.create_provider(self.config)
        self.runner = runner or RestrictedSubprocessRunner(
            allow_network=self.config.allow_unsafe_host_execution
        )
        self.tool_registry = tool_registry or ToolRegistry.create_default()

        # In-memory registry of sessions: session_id -> AgentWorkflowGraph
        self._active_graphs: Dict[str, AgentWorkflowGraph] = {}
        self._session_states: Dict[str, AgentState] = {}
        self._global_event_handlers: List[EventHandler] = []

    def register_event_handler(self, handler: EventHandler) -> None:
        """Register a streaming event callback (Person 2's Firestore/BigQuery bridge)."""
        self._global_event_handlers.append(handler)

    async def start_session(self, request: AgentExecutionRequest) -> str:
        """Initialize a new execution session."""
        session_id = request.session_id or f"sess_{uuid4().hex[:12]}"
        task_id = f"task_{uuid4().hex[:8]}"

        # Allocate workspace
        target_ws = (
            Path(request.workspace_dir).resolve()
            if request.workspace_dir
            else (Path(self.config.workspace_base_dir) / session_id).resolve()
        )
        workspace = WorkspaceManager(target_ws)

        telemetry = TelemetryCollector(
            session_id=session_id,
            task_id=task_id,
            model_name=self.provider.model_name,
        )
        for h in self._global_event_handlers:
            telemetry.register_handler(h)

        state = AgentState(
            session_id=session_id,
            task_id=task_id,
            user_task=request.task,
            model_name=self.provider.model_name,
            provider=self.provider.provider_type.value,
            harness_mode=request.harness_mode or self.config.default_harness_mode,
            context_strategy=request.context_strategy or self.config.context_strategy,
            execution_status=ExecutionStatus.PENDING,
        )

        graph = AgentWorkflowGraph(
            state=state,
            config=self.config,
            provider=self.provider,
            workspace=workspace,
            runner=self.runner,
            telemetry=telemetry,
            tool_registry=self.tool_registry,
        )

        self._active_graphs[session_id] = graph
        self._session_states[session_id] = state

        return session_id

    async def run_task(
        self,
        task: str,
        session_id: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        mode: Optional[HarnessMode] = None,
        context_strategy: Optional[ContextStrategy] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AgentExecutionResponse:
        """High-level autonomous execution entry point."""
        req = AgentExecutionRequest(
            task=task,
            session_id=session_id,
            workspace_dir=workspace_dir,
            harness_mode=mode,
            context_strategy=context_strategy,
            timeout_seconds=timeout_seconds or self.config.guard_timeout_seconds,
        )

        sid = await self.start_session(req)
        graph = self._active_graphs[sid]

        report = await graph.execute()
        state = self._session_states[sid]

        err_msg = state.errors[-1] if state.errors else None
        return AgentExecutionResponse(
            session_id=sid,
            task=task,
            status=state.execution_status,
            final_result=state.final_result or report.summary,
            report=report,
            metrics=state.execution_metrics,
            error=err_msg,
        )

    async def cancel_session(self, session_id: str) -> bool:
        """Signal cooperative cancellation to a running session."""
        graph = self._active_graphs.get(session_id)
        if not graph:
            return False
        graph.cancel()
        return True

    def get_session_state(self, session_id: str) -> Optional[AgentState]:
        """Query state snapshot for monitoring and UI updates."""
        return self._session_states.get(session_id)

    def get_execution_metrics(self, session_id: str) -> Optional[PerformanceMetrics]:
        """Retrieve metrics snapshot."""
        state = self._session_states.get(session_id)
        return state.execution_metrics if state else None
