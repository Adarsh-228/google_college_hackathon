# packages/harness_core: Intelligence Engine Documentation & Integration Guide

The core intelligence engine for HarnessX — an adaptive coding-agent infrastructure based on *"An Empirical Study of Harness Design for Coding Agents"*.

This documentation serves as the primary integration contract for **Person 2 (Cloud Backend & Systems Developer)** to incorporate `HarnessEngine` into FastAPI backend routes, Cloud Run services, and pub/sub streaming pipelines without violating team boundaries.

---

## Quick Reference Summary

### Public Import List
Person 2 and Person 3 should strictly import from `packages.harness_core`:
```python
from packages.harness_core import (
    # Core Engine Facade & State
    HarnessEngine,
    EngineConfig,
    AgentState,
    
    # Request & Response Contracts
    AgentExecutionRequest,
    AgentExecutionResponse,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolResult,
    TaskPlanStep,
    ExecutionReport,
    PerformanceMetrics,
    ExecutionMetrics,
    ContextStatistics,
    DiagnosticResult,
    
    # Lifecycle Enums
    ExecutionStatus,
    HarnessMode,
    ContextStrategy,
    EventType,
    ProviderType,
    TaskComplexity,
    ToolPermission,
    
    # Telemetry & Event Streaming
    AgentEvent,
    EventHandler,
    EventSink,
    
    # Model Providers
    BaseModelProvider,
    BaseLLMProvider,
    GeminiProvider,
    VertexAIProvider,
    MockModelProvider,
    MockLLMProvider,
    ProviderFactory,
    
    # Exceptions
    HarnessError,
    ConfigurationError,
    ProviderError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ContextOverflowError,
    GuardViolationError,
    StaleFileEditError,
    SecurityViolationError,
    LoopDetectedError,
    CircuitBreakerError,
    WorkspaceError,
    PathTraversalError,
    ToolExecutionError,
    ExecutionTimeoutError,
    SessionNotFoundError,
    TaskAbortedError,
)
```

### Dependency List
- Python `3.11+`
- `pydantic >= 2.5.0`
- `requests >= 2.31.0`
- Optional cloud / production dependencies:
  - `google-cloud-aiplatform >= 1.40.0` (for Vertex AI production ADC)
- Optional development dependencies:
  - `pytest >= 8.0.0`
  - `pytest-asyncio >= 0.23.0`
  - `ruff >= 0.3.0`

### Expected Installation Command
```bash
# Standard editable installation from repository root
pip install -e packages/harness_core

# Or install with development & testing dependencies
pip install -e "packages/harness_core[dev]"
```

---

## 1. Installation Instructions

The `packages/harness_core` package is structured as a standard PEP 517/621 Python package using `pyproject.toml`.

### Local Development / Monorepo Setup
From the repository root:
```bash
# Editable install
pip install -e packages/harness_core
```

### Docker / Cloud Run Setup (Dockerfile for Person 2)
In the container image for `services/api`:
```dockerfile
# Copy harness_core into the build container
COPY packages/harness_core /app/packages/harness_core

# Install package in non-editable release mode
RUN pip install --no-cache-dir /app/packages/harness_core
```

---

## 2. Environment Configuration

`HarnessEngine` automatically configures itself via `EngineConfig.from_env()`. The following environment variables are recognized:

| Variable | Type | Default | Required For | Description |
|---|---|---|---|---|
| `GEMINI_API_KEY` | `string` | `""` | Gemini API | Google AI Studio developer API key for direct prototyping. |
| `USE_VERTEX` | `bool` | `false` | Vertex AI | Set `true` to use Google Cloud Vertex AI via ADC instead of AI Studio. |
| `GOOGLE_CLOUD_PROJECT` | `string` | `""` | Vertex AI | Google Cloud Project ID hosting Vertex AI endpoints. |
| `GCP_REGION` | `string` | `us-central1` | Vertex AI | Google Cloud Region for Vertex AI model endpoints. |
| `GOOGLE_APPLICATION_CREDENTIALS` | `string` | `""` | Vertex AI (opt) | Optional path to service account JSON (prefer ADC in Cloud Run). |
| `HARNESS_DEFAULT_MODE` | `string` | `HYBRID` | All | Default execution mode (`GUIDED`, `DIRECT`, or `HYBRID`). |
| `HARNESS_MODEL_NAME` | `string` | `gemini-2.5-flash` | All | Default LLM model identifier. |
| `CONTEXT_SOFT_THRESHOLD` | `float` | `0.60` | ContextT4 | Fraction of context window triggering observation elision (T1/T4). |
| `CONTEXT_HARD_THRESHOLD` | `float` | `0.85` | ContextT4 | Fraction of context window triggering 7-section LLM summarization. |
| `CONTEXT_WINDOW_LIMIT` | `int` | `128000` | ContextT4 | Token window ceiling for context budget tracking. |
| `GUARD_MAX_TOOL_CALLS` | `int` | `30` | AgentGuard | Circuit breaker tool call budget per task. |
| `GUARD_MAX_LOOP_ATTEMPTS` | `int` | `5` | AgentGuard | Identical tool calls triggering warning event. |
| `GUARD_MAX_FAILED_REPEATS` | `int` | `8` | AgentGuard | Identical failing calls triggering `STALLED` state. |
| `GUARD_TIMEOUT_SECONDS` | `int` | `300` | AgentGuard | Global task execution timeout ceiling in seconds. |
| `WORKSPACE_BASE_DIR` | `string` | `./workspaces` | Workspace | Root filesystem directory for isolated agent session directories. |

> **Note on Offline Mode**: If neither `GEMINI_API_KEY` nor `USE_VERTEX=true` is present, `HarnessEngine` automatically initializes with `MockModelProvider` to ensure zero runtime crashes during local offline testing.

---

## 3. HarnessEngine Initialization

The engine is designed as a reusable, thread-safe asynchronous facade:

```python
from packages.harness_core import HarnessEngine, EngineConfig

# Option A: Automatic environment-driven initialization (Recommended)
engine = HarnessEngine()

# Option B: Explicit configuration overrides
config = EngineConfig(
    default_harness_mode="GUIDED",
    guard_max_tool_calls=25,
    guard_timeout_seconds=180,
    workspace_base_dir="/tmp/agent_sandboxes",
)
engine = HarnessEngine(config=config)

# Option C: Dependency injection (e.g. for testing)
from packages.harness_core import MockModelProvider
mock_provider = MockModelProvider()
engine = HarnessEngine(provider=mock_provider)
```

---

## 4. run_task() Usage

`run_task()` is the high-level asynchronous entry point for executing an end-to-end coding cycle:

### Method Signature
```python
async def run_task(
    self,
    task: str,
    session_id: Optional[str] = None,
    workspace_dir: Optional[str] = None,
    mode: Optional[HarnessMode] = None,
    context_strategy: Optional[ContextStrategy] = None,
    timeout_seconds: Optional[int] = None,
) -> AgentExecutionResponse:
```

### Parameters
- `task` (`str`, required): The coding task prompt or requirement description.
- `session_id` (`str`, optional): Unique session identifier. If omitted, a UUID-based ID is automatically generated.
- `workspace_dir` (`str`, optional): Isolated workspace path. Defaults to `{WORKSPACE_BASE_DIR}/{session_id}`.
- `mode` (`HarnessMode`, optional): `GUIDED`, `DIRECT`, or `HYBRID`. If omitted, dynamically classified based on task complexity.
- `context_strategy` (`ContextStrategy`, optional): `T0_NONE`, `T1_ELISION`, `T2_RECALL`, `T3_SUMMARIZATION`, or `T4_STAGED`. Defaults to `T4_STAGED`.
- `timeout_seconds` (`int`, optional): Execution timeout in seconds. Defaults to `config.guard_timeout_seconds` (300s).

### Asynchronous Execution Example
```python
import asyncio
from packages.harness_core import HarnessEngine, HarnessMode, ExecutionStatus

async def main():
    engine = HarnessEngine()
    
    response = await engine.run_task(
        task="Create a Python script calculate_tax.py with calculate_total(subtotal, rate)",
        session_id="sess_001",
        mode=HarnessMode.HYBRID,
        timeout_seconds=120,
    )
    
    if response.status == ExecutionStatus.COMPLETED:
        print("Success:", response.final_result)
        print("Files created:", response.report.files_created)
    else:
        print(f"Failed ({response.status.value}):", response.error)

asyncio.run(main())
```

### Session Control & Polling Methods
- `await engine.cancel_session(session_id)`: Signals cooperative cancellation to an active session loop.
- `engine.get_session_state(session_id)`: Returns current `AgentState` snapshot.
- `engine.get_execution_metrics(session_id)`: Returns current `ExecutionMetrics` / `PerformanceMetrics`.

---

## 5. Request Schema (`AgentExecutionRequest`)

The Pydantic v2 request model validated when a client or API submits a task:

### Fields
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `task` | `str` | Yes | — | User coding prompt or specification. |
| `session_id` | `str` | No | `None` | Client-provided session UUID. Generated if omitted. |
| `workspace_dir` | `str` | No | `None` | Target workspace directory path. |
| `harness_mode` | `HarnessMode` | No | `None` | `GUIDED`, `DIRECT`, or `HYBRID` (auto-selected if `None`). |
| `context_strategy` | `ContextStrategy` | No | `None` | Context strategy (defaults to `T4_STAGED`). |
| `model_name` | `str` | No | `None` | Target LLM model name (e.g. `gemini-2.5-flash`). |
| `timeout_seconds` | `int` | No | `300` | Maximum execution duration in seconds. |
| `max_tool_calls` | `int` | No | `30` | Maximum tool calls before circuit breaker trips. |
| `allow_network` | `bool` | No | `false` | Whether network operations are permitted in sandbox. |
| `metadata` | `dict` | No | `{}` | Arbitrary client metadata. |

### JSON Request Payload Example
```json
{
  "task": "Create a FastAPI web service in api.py with a GET /health endpoint that returns JSON status healthy",
  "session_id": "session-prod-9941",
  "workspace_dir": "./workspaces/session-prod-9941",
  "harness_mode": "HYBRID",
  "context_strategy": "T4_STAGED",
  "model_name": "gemini-2.5-flash",
  "timeout_seconds": 300,
  "max_tool_calls": 30,
  "allow_network": false,
  "metadata": {
    "user_id": "usr_abc123",
    "project_id": "hackathon-demo"
  }
}
```

---

## 6. Response Schema (`AgentExecutionResponse`)

The top-level serializable Pydantic v2 response returned by `run_task()`:

### Fields
| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique session ID. |
| `task` | `str` | Original prompt requested. |
| `status` | `ExecutionStatus` | Final execution state (`COMPLETED`, `FAILED`, `STALLED`, `CANCELLED`). |
| `final_result` | `str | null` | Agent's final message or completion summary. |
| `report` | `ExecutionReport | null` | Comprehensive breakdown of plan steps, files touched, errors, and metrics. |
| `metrics` | `PerformanceMetrics` | Aggregated execution telemetry (tokens, tool calls, costs, duration). |
| `error` | `str | null` | Descriptive error message if status is `FAILED` or `STALLED`. |

### ExecutionReport Fields
- `plan`: List of `TaskPlanStep` objects (`step_number`, `description`, `tool_suggested`, `status`, `notes`).
- `completed_steps`: List of completed step descriptions.
- `files_created`: List of newly created workspace files.
- `files_modified`: List of edited workspace files.
- `errors_encountered`: List of string errors encountered and handled during execution.
- `diagnostics_resolved`: Number of syntactic/lint errors fixed by the agent.
- `summary`: High-level summary of actions performed.

---

## 7. Execution Status Values (`ExecutionStatus`)

The engine transitions through well-defined lifecycle states:

| Status | Meaning | Next Possible States |
|---|---|---|
| `PENDING` | Task received and session record registered. | `INITIALIZING`, `FAILED` |
| `INITIALIZING` | Workspace allocated, tools loaded, capability profile selected. | `RUNNING`, `FAILED` |
| `RUNNING` | Active in plan-act iteration loop. | `WAITING_FOR_TOOL`, `RECOVERING`, `COMPLETED`, `FAILED`, `STALLED`, `CANCELLED` |
| `WAITING_FOR_TOOL` | Tool invocation dispatched to AgentGuard interceptor. | `RUNNING`, `RECOVERING`, `FAILED` |
| `RECOVERING` | Tool or diagnostic error reported; agent self-correcting. | `RUNNING`, `FAILED`, `STALLED` |
| `COMPLETED` | Task objectives successfully verified and completed. | Terminal state |
| `FAILED` | Unrecoverable error (e.g. timeout, unrecoverable exception, circuit breaker limit). | Terminal state |
| `STALLED` | Loop detector halted execution after 8 identical consecutive failing tool calls. | Terminal state |
| `CANCELLED` | Execution aborted via `cancel_session()` signal. | Terminal state |

---

## 8. Error Response Format

When execution fails, trips a circuit breaker, or stalls, `HarnessEngine` returns a fully populated `AgentExecutionResponse` with non-null `error` field and terminal status.

### Example: Stalled Execution Response (Loop Detection)
```json
{
  "session_id": "session-prod-9941",
  "task": "Attempt repetitive invalid operation",
  "status": "STALLED",
  "final_result": null,
  "report": {
    "session_id": "session-prod-9941",
    "task": "Attempt repetitive invalid operation",
    "status": "STALLED",
    "harness_mode": "HYBRID",
    "context_strategy": "T4_STAGED",
    "plan": [
      {
        "step_number": 1,
        "description": "Inspect file",
        "tool_suggested": "read_file",
        "status": "FAILED",
        "notes": "Repeated failure"
      }
    ],
    "completed_steps": [],
    "files_created": [],
    "files_modified": [],
    "errors_encountered": [
      "Loop Protection: Tool 'read_file' failed 8 consecutive times with identical arguments. Terminating execution."
    ],
    "diagnostics_resolved": 0,
    "metrics": {
      "input_tokens": 1420,
      "output_tokens": 280,
      "total_tokens": 1700,
      "estimated_cost_usd": 0.000215,
      "tool_call_count": 8,
      "repeated_call_count": 7,
      "diagnostic_count": 0,
      "recovery_count": 0,
      "execution_duration_seconds": 2.15,
      "tokens_saved_estimate": 0,
      "final_status": "STALLED"
    },
    "summary": "Execution halted: repetitive loop detected by AgentGuard."
  },
  "metrics": {
    "input_tokens": 1420,
    "output_tokens": 280,
    "total_tokens": 1700,
    "estimated_cost_usd": 0.000215,
    "tool_call_count": 8,
    "repeated_call_count": 7,
    "diagnostic_count": 0,
    "recovery_count": 0,
    "execution_duration_seconds": 2.15,
    "tokens_saved_estimate": 0,
    "final_status": "STALLED"
  },
  "error": "Loop Protection: Tool 'read_file' failed 8 consecutive times with identical arguments. Terminating execution."
}
```

---

## 9. Telemetry Event Format (`AgentEvent`)

Every significant lifecycle step emits a structured `AgentEvent` that Person 2 can stream via WebSockets or Server-Sent Events (SSE) to Person 3's Dashboard:

### Schema Fields
- `event_id` (`str`): Unique identifier (`evt_...`).
- `session_id` (`str`): Current session identifier.
- `task_id` (`str`): Identifier of the active task.
- `timestamp` (`datetime`): UTC timestamp of the event.
- `event_type` (`EventType`): Event category enum.
- `component` (`str`): Originating subsystem (`harness_orchestrator`, `agent_guard`, `context_manager`, `planner`, etc.).
- `status` (`ExecutionStatus`): Engine state at time of event.
- `duration_ms` (`float | null`): Duration in milliseconds if timing an operation.
- `payload` (`dict`): Event-specific structured data.
- `metadata` (`dict`): Optional tracking metadata.

### Example JSON Event
```json
{
  "event_id": "evt_7e2a9b31d45c",
  "session_id": "session-prod-9941",
  "task_id": "task_a1f49e0b",
  "timestamp": "2026-10-13T00:30:15.123456Z",
  "event_type": "tool_call_completed",
  "component": "agent_guard",
  "status": "RUNNING",
  "duration_ms": 14.8,
  "payload": {
    "tool_name": "write_file",
    "success": true,
    "output_snippet": "Successfully wrote 120 characters to 'api.py'",
    "error": null
  },
  "metadata": {}
}
```

### Complete List of Event Types (`EventType`)
- `session_started`: Session created and workspace initialized.
- `task_analyzed`: Task complexity classified (`LOW`, `MEDIUM`, `HIGH`).
- `model_selected`: Model provider and model name selected.
- `plan_created`: Step-by-step task execution plan formulated.
- `context_compressed`: Context elision or summarization triggered.
- `tool_call_started`: Tool call requested by model and routed to AgentGuard.
- `tool_call_completed`: Tool executed and validated with diagnostics.
- `diagnostic_generated`: Code syntax or lint diagnostic identified.
- `loop_warning`: AgentGuard warning threshold reached (5 repeated calls).
- `execution_recovered`: Agent recovered from an error using diagnostic feedback.
- `verification_completed`: Task objective verified against criteria.
- `session_completed`: Session terminated successfully (`COMPLETED`).
- `session_failed`: Session terminated with error (`FAILED`).
- `session_cancelled`: Session cooperatively cancelled (`CANCELLED`).

---

## 10. EventSink Interface

The `EventSink` interface decouples the core engine from specific databases or transport protocols:

```python
EventHandler = Callable[[AgentEvent], Coroutine[Any, Any, None]]
EventSink = EventHandler
```

### Registering an EventSink
```python
from packages.harness_core import HarnessEngine, AgentEvent

async def my_cloud_event_sink(event: AgentEvent) -> None:
    # 1. Forward to WebSocket subscribers (Person 3 Dashboard)
    # 2. Asynchronously stream to Firestore or BigQuery buffer
    # 3. Write structured log to Cloud Logging
    print(f"[{event.event_type.value}] {event.component} -> {event.payload}")

engine = HarnessEngine()
engine.register_event_handler(my_cloud_event_sink)
```

`HarnessEngine` awaits each registered coroutine deterministically, guaranteeing ordered delivery to WebSocket streams without race conditions.

---

## 11. Provider Configuration

`harness_core` supports two cloud LLM provider modes:

### Google AI Studio (Local Development / Prototyping)
Connects directly to Google AI Studio's Gemini REST endpoints:
```bash
export GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
export USE_VERTEX="false"
export HARNESS_MODEL_NAME="gemini-2.5-flash"
```

### Google Cloud Vertex AI (Cloud Run / Enterprise Production)
Uses Google Cloud Application Default Credentials (ADC) without requiring hardcoded API keys:
```bash
export USE_VERTEX="true"
export GOOGLE_CLOUD_PROJECT="my-hackathon-gcp-project"
export GCP_REGION="us-central1"
export HARNESS_MODEL_NAME="gemini-2.5-flash"
```

On Cloud Run, ADC is automatically provisioned via the attached Service Account. For local development with Vertex AI:
```bash
gcloud auth application-default login
gcloud config set project my-hackathon-gcp-project
```

---

## 12. Mock Provider Usage

`MockModelProvider` allows zero-credential, offline execution for unit testing, CI pipelines, and automated integration validation:

```python
from packages.harness_core import HarnessEngine, MockModelProvider

mock = MockModelProvider()

# Queue multi-turn simulation responses
mock.queue_tool_call(
    tool_name="write_file",
    arguments={"file_path": "hello.py", "content": "print('hello world')"},
    thought="Step 1: Write script",
)
mock.queue_tool_call(
    tool_name="read_file",
    arguments={"file_path": "hello.py"},
    thought="Step 2: Inspect script",
)
mock.queue_text_response("Task completed successfully!")

# Inject into engine
engine = HarnessEngine(provider=mock)
```

You can also simulate provider failures to test error handling:
```python
mock.queue_error(RuntimeError("Simulated upstream quota exceeded"))
```

---

## 13. Context Strategy Configuration

Configured via `context_strategy` argument on `run_task()` or `EngineConfig`:

| Strategy | Enum Value | Mechanism | Best Use Case |
|---|---|---|---|
| **T0: Raw** | `ContextStrategy.T0_NONE` | Full raw chat history passed uncompressed. | Short tasks (< 3 steps). |
| **T1: Elision** | `ContextStrategy.T1_ELISION` | Rule-based elision: truncates bulky/stale tool observations beyond 3 turns. | Medium terminal-heavy tasks. |
| **T2: Recall** | `ContextStrategy.T2_RECALL` | Elision with indexed reference pointers to past outputs. | Large workspace searches. |
| **T3: Summarization** | `ContextStrategy.T3_SUMMARIZATION` | Rolling LLM-generated summaries replacing older turns. | Long multi-file debugging. |
| **T4: Staged (Primary)** | `ContextStrategy.T4_STAGED` | **Two-stage hybrid**: Rule elision at 60% window (`CONTEXT_SOFT_THRESHOLD`), followed by 7-section structured LLM summary at 85% window (`CONTEXT_HARD_THRESHOLD`). Preserves task goals, recent errors, and file state map. | Default for all production tasks. |

---

## 14. Execution Mode Configuration

Configured via `mode` argument on `run_task()` or `EngineConfig`:

| Mode | Enum Value | Permitted Tools | Behavior |
|---|---|---|---|
| **GUIDED** | `HarnessMode.GUIDED` | Dedicated file tools only: `read_file`, `write_file`, `edit_file`, `list_files`, `search_files`. (Terminal blocked). | Explicit planning, strict read-before-write, and verification for precision coding. |
| **DIRECT** | `HarnessMode.DIRECT` | Terminal-centric: `run_terminal_command`, `list_files`. | Fast command execution, scripts, tests, and build execution. |
| **HYBRID** | `HarnessMode.HYBRID` | All registered tools (`read_file`, `write_file`, `edit_file`, `list_files`, `search_files`, `run_terminal_command`). | Adaptive fallback: starts with structured file tools, adapts dynamically. |

When `mode=None` is passed to `run_task()`, `TaskComplexityAnalyzer` inspects the task text and automatically selects the optimal mode.

---

## 15. Limitations and Security Considerations

1. **Workspace Boundary Containment**: All file operations (`read_file`, `write_file`, `edit_file`, `list_files`, `search_files`) are strictly jailed within `workspace_dir`. Path traversal attacks (e.g. `../../etc/passwd`) are detected and blocked with `PathTraversalError`.
2. **Subprocess Execution Notice**: `RestrictedSubprocessRunner` enforces working-directory containment, execution timeouts, and destructive command blocks (e.g. `rm -rf /`, `mkfs`). It is a development-grade containment layer and **not** an enterprise multi-tenant security sandbox. In multi-tenant cloud deployments, Person 2 should back execution with containerized microVMs (e.g. gVisor / Cloud Run isolated jobs).
3. **Strict Decoupling Contract**: `packages/harness_core` does not connect to Firestore, BigQuery, or Firebase Auth. All external data flows through the public `EventSink` interface and return models.
4. **Read-Before-Write Integrity**: `ReadBeforeWriteValidator` prevents the agent from overwriting or modifying files without first reading them. Attempting to edit an uninspected file raises a safety block.
5. **Circuit Breaker Budgets**: Execution is bounded by `MAX_TOOL_CALLS` (default 30) and `GUARD_TIMEOUT_SECONDS` (default 300s) to prevent runaway cloud inference costs.

---

## 16. Minimal Person 2 Integration Example

Person 2 can integrate `HarnessEngine` into FastAPI using this complete, production-ready route template:

```python
"""FastAPI Backend Integration Route for Person 2 (Cloud Backend).

Location: services/api/routes/agent_routes.py (owned by Person 2)
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

# Import strictly from the public packages.harness_core interface
from packages.harness_core import (
    AgentEvent,
    AgentExecutionRequest,
    AgentExecutionResponse,
    ExecutionMetrics,
    ExecutionStatus,
    HarnessEngine,
    HarnessError,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["Agent Execution"])

# Initialize engine singleton from environment
engine = HarnessEngine()

# Active WebSocket subscribers: session_id -> list of WebSockets
_subscribers: Dict[str, List[WebSocket]] = {}


async def cloud_event_bridge(event: AgentEvent) -> None:
    """Async EventSink bridge forwarding events to connected dashboard WebSockets."""
    sockets = _subscribers.get(event.session_id, [])
    if not sockets:
        return
        
    payload = event.model_dump(mode="json")
    for ws in list(sockets):
        try:
            await ws.send_json(payload)
        except Exception:
            sockets.remove(ws)


# Register event bridge
engine.register_event_handler(cloud_event_bridge)


@router.post("/run", response_model=AgentExecutionResponse)
async def run_session(request: AgentExecutionRequest) -> AgentExecutionResponse:
    """Execute coding task and return serializable Pydantic response."""
    try:
        response = await engine.run_task(
            task=request.task,
            session_id=request.session_id,
            workspace_dir=request.workspace_dir,
            mode=request.harness_mode,
            context_strategy=request.context_strategy,
            timeout_seconds=request.timeout_seconds,
        )
        return response
    except HarnessError as err:
        raise HTTPException(
            status_code=500,
            detail={"error_type": err.__class__.__name__, "message": str(err)},
        )


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str):
    """Cooperative cancellation endpoint."""
    cancelled = await engine.cancel_session(session_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not active")
    return {"status": "CANCELLED", "session_id": session_id}


@router.get("/{session_id}/metrics", response_model=Optional[ExecutionMetrics])
async def get_metrics(session_id: str) -> Optional[ExecutionMetrics]:
    """Retrieve execution metrics snapshot."""
    metrics = engine.get_execution_metrics(session_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return metrics


@router.websocket("/{session_id}/stream")
async def stream_session_events(websocket: WebSocket, session_id: str):
    """Real-time event stream for Person 3 Dashboard."""
    await websocket.accept()
    _subscribers.setdefault(session_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if session_id in _subscribers and websocket in _subscribers[session_id]:
            _subscribers[session_id].remove(websocket)
```

---

## 17. Example Successful Response

```json
{
  "session_id": "session-prod-9941",
  "task": "Create a FastAPI web service in api.py with a GET /health endpoint",
  "status": "COMPLETED",
  "final_result": "Successfully created FastAPI web service in api.py with /health endpoint.",
  "report": {
    "session_id": "session-prod-9941",
    "task": "Create a FastAPI web service in api.py with a GET /health endpoint",
    "status": "COMPLETED",
    "harness_mode": "HYBRID",
    "context_strategy": "T4_STAGED",
    "plan": [
      {
        "step_number": 1,
        "description": "Inspect workspace files",
        "tool_suggested": "list_files",
        "status": "COMPLETED",
        "notes": "Workspace checked"
      },
      {
        "step_number": 2,
        "description": "Write FastAPI code to api.py",
        "tool_suggested": "write_file",
        "status": "COMPLETED",
        "notes": "File created"
      },
      {
        "step_number": 3,
        "description": "Verify file syntax and content",
        "tool_suggested": "read_file",
        "status": "COMPLETED",
        "notes": "Clean syntax"
      }
    ],
    "completed_steps": [
      "Inspect workspace files",
      "Write FastAPI code to api.py",
      "Verify file syntax and content"
    ],
    "files_created": ["api.py"],
    "files_modified": [],
    "errors_encountered": [],
    "diagnostics_resolved": 0,
    "metrics": {
      "input_tokens": 1850,
      "output_tokens": 420,
      "total_tokens": 2270,
      "estimated_cost_usd": 0.000282,
      "tool_call_count": 3,
      "repeated_call_count": 0,
      "diagnostic_count": 0,
      "recovery_count": 0,
      "execution_duration_seconds": 2.45,
      "tokens_saved_estimate": 450,
      "final_status": "COMPLETED"
    },
    "summary": "Task completed successfully."
  },
  "metrics": {
    "input_tokens": 1850,
    "output_tokens": 420,
    "total_tokens": 2270,
    "estimated_cost_usd": 0.000282,
    "tool_call_count": 3,
    "repeated_call_count": 0,
    "diagnostic_count": 0,
    "recovery_count": 0,
    "execution_duration_seconds": 2.45,
    "tokens_saved_estimate": 450,
    "final_status": "COMPLETED"
  },
  "error": null
}
```

---

## 18. Example Failed Response

```json
{
  "session_id": "session-prod-9941",
  "task": "Run command with invalid syntax and repeated attempts",
  "status": "FAILED",
  "final_result": null,
  "report": {
    "session_id": "session-prod-9941",
    "task": "Run command with invalid syntax and repeated attempts",
    "status": "FAILED",
    "harness_mode": "DIRECT",
    "context_strategy": "T4_STAGED",
    "plan": [
      {
        "step_number": 1,
        "description": "Run terminal build",
        "tool_suggested": "run_terminal_command",
        "status": "FAILED",
        "notes": "Timeout tripped"
      }
    ],
    "completed_steps": [],
    "files_created": [],
    "files_modified": [],
    "errors_encountered": [
      "ExecutionTimeoutError: Task exceeded maximum execution timeout of 300s."
    ],
    "diagnostics_resolved": 0,
    "metrics": {
      "input_tokens": 2400,
      "output_tokens": 310,
      "total_tokens": 2710,
      "estimated_cost_usd": 0.000345,
      "tool_call_count": 5,
      "repeated_call_count": 0,
      "diagnostic_count": 0,
      "recovery_count": 1,
      "execution_duration_seconds": 300.2,
      "tokens_saved_estimate": 0,
      "final_status": "FAILED"
    },
    "summary": "Execution terminated due to timeout."
  },
  "metrics": {
    "input_tokens": 2400,
    "output_tokens": 310,
    "total_tokens": 2710,
    "estimated_cost_usd": 0.000345,
    "tool_call_count": 5,
    "repeated_call_count": 0,
    "diagnostic_count": 0,
    "recovery_count": 1,
    "execution_duration_seconds": 300.2,
    "tokens_saved_estimate": 0,
    "final_status": "FAILED"
  },
  "error": "ExecutionTimeoutError: Task exceeded maximum execution timeout of 300s."
}
```
