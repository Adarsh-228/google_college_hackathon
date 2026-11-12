# HarnessX: Team Work Division & Interface Contracts

**Project**: HarnessX – Adaptive Coding Agent Infrastructure  
**Foundation**: Based on *"An Empirical Study of Harness Design for Coding Agents"*  
**Repository Pattern**: Monorepo with modular packages  

---

## 1. Team Ownership & Responsibilities

| Role | Engineer | Module Ownership | Core Responsibilities |
|---|---|---|---|
| **Person 1** | **Core Agent Engine Developer** | `packages/harness_core/` | - Core Intelligence Engine & LangGraph agent orchestration<br>- Multi-provider LLM abstraction (Gemini 2.5/Vertex AI/Mocks)<br>- ContextT4 staged context management (T0-T4)<br>- AdaptiveHarness mode & capability selection (Guided, Direct, Hybrid)<br>- AgentGuard safety interceptor (file integrity, loop detection, syntax diagnostics)<br>- Sandboxed workspace & tool execution registry<br>- Structured telemetry events & performance metrics collector |
| **Person 2** | **Cloud Backend & Systems Developer** | `services/api/` & Cloud Infrastructure | - FastAPI service exposing agent session endpoints<br>- Cloud Run stateless deployment & scale-to-zero management<br>- Firestore persistence for sessions, checkpoints, and event logs<br>- BigQuery pipeline for agent execution telemetry & evaluation metrics<br>- Firebase Authentication integration & session isolation<br>- Event pub/sub bridge consuming `HarnessEngine` event handlers |
| **Person 3** | **Dashboard & Observability Developer** | `apps/dashboard/` | - Real-time agent monitoring dashboard (Next.js / Vite)<br>- Live execution stream visualization (events, steps, plans, tool calls)<br>- ContextT4 compression visualizer (before/after token savings)<br>- AgentGuard security alerts (loop warnings, file integrity blocks)<br>- AdaptiveHarness profile switcher & benchmark comparison UI |

---

## 2. Shared Integration Contracts (Person 1 ⟷ Person 2 & 3)

The package `packages/harness_core` exposes high-level, stable Pydantic v2 schemas and an orchestration facade `HarnessEngine`. Person 2 and Person 3 do **not** import internal modules; they rely strictly on `packages.harness_core`:

```python
from packages.harness_core import (
    HarnessEngine,
    EngineConfig,
    AgentExecutionRequest,
    AgentExecutionResponse,
    ExecutionStatus,
    HarnessMode,
    ContextStrategy,
    AgentEvent,
    EventType,
    ExecutionReport,
    ExecutionMetrics,
)
```

### 2.1 Public Engine Facade API

```python
class HarnessEngine:
    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        """Initialize engine with validated settings and provider."""
        ...

    async def start_session(self, request: AgentExecutionRequest) -> str:
        """Create session, register event listeners, allocate workspace."""
        ...

    async def run_task(
        self,
        task: str,
        session_id: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        mode: Optional[HarnessMode] = None,
        context_strategy: Optional[ContextStrategy] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AgentExecutionResponse:
        """Execute full autonomous coding cycle and return structured response."""
        ...

    async def cancel_session(self, session_id: str) -> bool:
        """Signal cooperative cancellation to running agent graph."""
        ...

    def get_session_state(self, session_id: str) -> Optional[AgentState]:
        """Query current execution state for live polling / check-pointing."""
        ...

    def get_execution_metrics(self, session_id: str) -> Optional[ExecutionMetrics]:
        """Retrieve aggregated token, latency, and tool metrics."""
        ...

    def register_event_handler(self, handler: Callable[[AgentEvent], Coroutine[Any, Any, None]]) -> None:
        """Register async listener for streaming telemetry events (Person 2 forwarder)."""
        ...
```

---

## 3. Data Contracts & Schemas

### 3.1 Execution Status (`ExecutionStatus`)
- `PENDING`: Task queued.
- `INITIALIZING`: Workspace, tools, and capability profile loading.
- `RUNNING`: Agent active in plan-act loop.
- `WAITING_FOR_TOOL`: Guard validating tool execution.
- `RECOVERING`: Error encountered; self-correction in progress.
- `COMPLETED`: Objective verified and finished successfully.
- `FAILED`: Execution terminated with unrecoverable error.
- `STALLED`: Loop detector or circuit breaker halted repeated failures.
- `CANCELLED`: Aborted via external request.

### 3.2 Harness Mode (`HarnessMode`)
- `GUIDED`: Dedicated file tools (`read_file`, `edit_file`, `write_file`), explicit step planning, strict integrity guards.
- `DIRECT`: Terminal-centric interaction (`run_terminal_command`), fast batch commands, streamlined planning.
- `HYBRID`: Unified tool access with adaptive fallback based on tool safety class.

### 3.3 Context Strategy (`ContextStrategy`)
- `T0_NONE`: Full raw history passed.
- `T1_ELISION`: Rule-based truncation of bulky/stale tool outputs.
- `T2_RECALL`: Rule-based elision with reference index.
- `T3_SUMMARIZATION`: LLM-generated rolling summary.
- `T4_STAGED`: Staged rule-based elision followed by LLM summarization (HarnessX primary).

### 3.4 Telemetry Event Format (`AgentEvent`)
Every lifecycle step emits an `AgentEvent` consumed by Person 2 to stream over WebSocket/SSE to Person 3:

```json
{
  "event_id": "evt_abc123",
  "session_id": "sess_xyz789",
  "task_id": "task_456",
  "timestamp": "2026-10-12T18:30:00Z",
  "event_type": "tool_call_completed",
  "component": "agent_guard",
  "status": "COMPLETED",
  "duration_ms": 142.5,
  "payload": {
    "tool_name": "edit_file",
    "file_path": "src/api.py",
    "syntax_valid": true,
    "diagnostics": []
  }
}
```

---

## 4. Environment Variables Contract

| Variable | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `GEMINI_API_KEY` | string | `""` | Person 1, Person 2 | Google AI Studio local prototyping key |
| `USE_VERTEX` | bool | `false` | Person 1, Person 2 | Flag: `false` = AI Studio Gemini API, `true` = Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | string | `""` | Person 1, Person 2 | GCP Project ID for Vertex AI & Cloud Run |
| `GCP_REGION` | string | `us-central1` | Person 1, Person 2 | GCP Region for Vertex AI endpoints & services |
| `GOOGLE_APPLICATION_CREDENTIALS` | string | `""` | Person 1, Person 2 | Optional path to service account JSON (prefer ADC) |
| `HARNESS_DEFAULT_MODE` | string | `HYBRID` | Person 1 | Default harness strategy (`GUIDED`, `DIRECT`, `HYBRID`) |
| `CONTEXT_SOFT_THRESHOLD` | float | `0.60` | Person 1 | Context trigger for elision |
| `CONTEXT_HARD_THRESHOLD` | float | `0.85` | Person 1 | Context trigger for LLM summarization |
| `MAX_TOOL_CALLS` | int | `30` | Person 1 | Circuit breaker tool call budget per task |
| `WORKSPACE_BASE_DIR` | string | `./workspaces` | Person 1, Person 2 | Isolated sandbox directory for agent file execution |
