"""Minimal FastAPI Backend Integration Example for Person 2 (Cloud Backend).

This example demonstrates how Person 2's FastAPI service can interface with
packages/harness_core using strictly public contracts and asynchronous execution.

Design Principles:
- Avoid importing private internal modules (only import from packages.harness_core).
- Use only public package interfaces (HarnessEngine, EngineConfig, AgentExecutionRequest/Response).
- Avoid accessing Firestore or BigQuery directly within harness_core (use EventSink).
- Return serializable response data (Pydantic v2 model_dump or FastAPI response_model).
- Support fully asynchronous execution.
"""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

# Strict public contract imports
from packages.harness_core import (
    AgentEvent,
    AgentExecutionRequest,
    AgentExecutionResponse,
    ContextStrategy,
    EngineConfig,
    EventType,
    ExecutionMetrics,
    ExecutionStatus,
    HarnessEngine,
    HarnessError,
    HarnessMode,
)

# 1. Initialize FastAPI Application
app = FastAPI(
    title="HarnessX Cloud Backend API",
    description="Person 2 Cloud Run service integrating with packages/harness_core",
    version="1.0.0",
)

# 2. Initialize HarnessEngine Singleton using environment settings
# (Reads GEMINI_API_KEY, USE_VERTEX, GOOGLE_CLOUD_PROJECT, etc. automatically)
engine_config = EngineConfig.from_env()
engine = HarnessEngine(config=engine_config)

# In-memory pub/sub registry for live WebSocket event streaming (Person 3 Dashboard)
_ws_subscribers: Dict[str, List[WebSocket]] = {}


# 3. Define EventSink Bridge for streaming events to WebSockets and Cloud logging
# (Person 2 can forward events to Cloud Pub/Sub, Firestore, or BigQuery buffer here)
async def backend_event_sink(event: AgentEvent) -> None:
    """Async EventSink implementation forwarding events to dashboard WebSocket clients.
    
    Args:
        event: Emitted telemetry event from HarnessEngine.
    """
    session_id = event.session_id
    subscribers = _ws_subscribers.get(session_id, [])
    if not subscribers:
        return

    # event.model_dump(mode="json") produces a JSON-serializable dictionary
    event_payload = event.model_dump(mode="json")
    
    disconnected: List[WebSocket] = []
    for ws in subscribers:
        try:
            await ws.send_json(event_payload)
        except Exception:
            disconnected.append(ws)
            
    for ws in disconnected:
        if ws in subscribers:
            subscribers.remove(ws)


# Register EventSink with engine
engine.register_event_handler(backend_event_sink)


# 4. Asynchronous Task Execution Route
@app.post(
    "/api/v1/sessions/run",
    response_model=AgentExecutionResponse,
    summary="Execute an autonomous coding task",
)
async def run_agent_task(request: AgentExecutionRequest) -> AgentExecutionResponse:
    """Execute an autonomous coding session.
    
    Accepts an AgentExecutionRequest, runs the task asynchronously through HarnessEngine,
    and returns a serializable AgentExecutionResponse.
    """
    try:
        response: AgentExecutionResponse = await engine.run_task(
            task=request.task,
            session_id=request.session_id,
            workspace_dir=request.workspace_dir,
            mode=request.harness_mode,
            context_strategy=request.context_strategy,
            timeout_seconds=request.timeout_seconds,
        )
        return response

    except HarnessError as err:
        # Structured error handling using harness_core exceptions
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": err.__class__.__name__,
                "message": str(err),
                "session_id": request.session_id,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error_type": "InternalServerError", "message": str(exc)},
        )


# 5. Cooperative Cancellation Route
@app.post(
    "/api/v1/sessions/{session_id}/cancel",
    summary="Cancel a running agent session",
)
async def cancel_agent_session(session_id: str) -> Dict[str, Any]:
    """Signal cooperative cancellation to a running agent session."""
    cancelled = await engine.cancel_session(session_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or already completed.",
        )
    return {"status": "CANCELLED", "session_id": session_id}


# 6. Session Metrics and State Polling Route
@app.get(
    "/api/v1/sessions/{session_id}/metrics",
    response_model=Optional[ExecutionMetrics],
    summary="Get real-time execution metrics for a session",
)
async def get_session_metrics(session_id: str) -> Optional[ExecutionMetrics]:
    """Retrieve execution metrics (tokens, tool calls, costs, duration)."""
    metrics = engine.get_execution_metrics(session_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return metrics


# 7. WebSocket Streaming Route for Real-Time Telemetry (Person 3 Dashboard)
@app.websocket("/api/v1/sessions/{session_id}/stream")
async def websocket_event_stream(websocket: WebSocket, session_id: str):
    """WebSocket endpoint streaming AgentEvents in real-time to Person 3's UI."""
    await websocket.accept()
    if session_id not in _ws_subscribers:
        _ws_subscribers[session_id] = []
    _ws_subscribers[session_id].append(websocket)

    try:
        # Keep socket open and listen for client pings or control messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if session_id in _ws_subscribers and websocket in _ws_subscribers[session_id]:
            _ws_subscribers[session_id].remove(websocket)
            if not _ws_subscribers[session_id]:
                del _ws_subscribers[session_id]
