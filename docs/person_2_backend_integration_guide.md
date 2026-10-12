# Integration Guide: Person 2 (Cloud Backend & Systems)

**Module Consumer**: `services/api/` (FastAPI / Cloud Run)  
**Package Imported**: `packages.harness_core`  
**Engineer**: Person 2  

This guide provides everything Person 2 needs to integrate the Core Agent Engine (`packages.harness_core`) into the FastAPI backend, connect Firestore for session persistence, forward telemetry to BigQuery, and deploy to Cloud Run.

---

## 1. Importing the Facade

Person 2 should strictly import public entities from the top-level package namespace:

```python
from packages.harness_core import (
    HarnessEngine,
    EngineConfig,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentEvent,
    ExecutionStatus,
    HarnessMode,
    ContextStrategy,
    EventType,
)
```

**Never** import internal submodules (such as `packages.harness_core.agent.graph` or `packages.harness_core.guard.circuit_breaker`).

---

## 2. FastAPI Service Architecture

Below is a complete reference implementation demonstrating how Person 2 can hook `HarnessEngine` into FastAPI with async background processing, real-time WebSocket/SSE streaming, and Firestore persistence.

```python
import os
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket
from packages.harness_core import (
    HarnessEngine,
    EngineConfig,
    AgentExecutionRequest,
    AgentEvent,
)

app = FastAPI(title="HarnessX API Service")

# 1. Initialize Engine once at startup
config = EngineConfig.from_env()
engine = HarnessEngine(config=config)

# Connected WebSocket clients: session_id -> list of WebSockets
connected_sockets: dict[str, list[WebSocket]] = {}

# 2. Register Global Telemetry Event Sink
async def handle_agent_event(event: AgentEvent) -> None:
    # A. Broadcast to connected WebSocket / SSE subscribers (Person 3 Dashboard)
    websockets = connected_sockets.get(event.session_id, [])
    for ws in websockets:
        try:
            await ws.send_json(event.model_dump(mode="json"))
        except Exception:
            pass

    # B. Persist Event to Firestore
    # db.collection("sessions").document(event.session_id).collection("events").add(event.model_dump(mode="json"))

    # C. Stream to BigQuery when session concludes
    # if event.event_type.value in ("session_completed", "session_failed"):
    #     bigquery_client.insert_rows_json("harnessx_metrics.agent_executions", [event.payload])

engine.register_event_handler(handle_agent_event)


@app.post("/api/v1/sessions/run")
async def run_task_endpoint(request: AgentExecutionRequest):
    """Start task and return final execution report."""
    response = await engine.run_task(
        task=request.task,
        session_id=request.session_id,
        workspace_dir=request.workspace_dir,
        mode=request.harness_mode,
        context_strategy=request.context_strategy,
        timeout_seconds=request.timeout_seconds,
    )
    return response


@app.post("/api/v1/sessions/{session_id}/cancel")
async def cancel_session_endpoint(session_id: str):
    """Signal cooperative cancellation to running task."""
    cancelled = await engine.cancel_session(session_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Session not running or not found")
    return {"status": "CANCELLED", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}/state")
async def get_state_endpoint(session_id: str):
    """Query state for live dashboard polling."""
    state = engine.get_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@app.get("/api/v1/sessions/{session_id}/metrics")
async def get_metrics_endpoint(session_id: str):
    """Query metrics snapshot."""
    metrics = engine.get_execution_metrics(session_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics


@app.websocket("/api/v1/sessions/{session_id}/stream")
async def websocket_stream(websocket: WebSocket, session_id: str):
    """Real-time event stream for Person 3's Dashboard."""
    await websocket.accept()
    connected_sockets.setdefault(session_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        connected_sockets[session_id].remove(websocket)
```

---

## 3. Cloud Run Stateless Best Practices

1. **Workspace Ephemeral Storage**: When deployed to Cloud Run, container filesystem writes in `/tmp/workspaces` are fast and memory-backed.
2. **Stateless Scale-to-Zero**: Since each session emits `AgentEvent` updates synchronously, store each event into Firestore as it arrives. If a container restarts, historical states are safe in Firestore.
3. **Environment Setup**:
   ```bash
   USE_VERTEX="true"
   GOOGLE_CLOUD_PROJECT="my-hackathon-project"
   GCP_REGION="us-central1"
   WORKSPACE_BASE_DIR="/tmp/workspaces"
   ```
