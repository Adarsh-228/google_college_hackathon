# Integration Guide: Person 3 (Dashboard & Observability)

**Module Consumer**: `apps/dashboard/` (Next.js / Vite / React)  
**Engineer**: Person 3  
**Data Interface**: Consumes WebSocket / SSE / REST endpoints exposed by Person 2's backend.

This guide details the schemas and lifecycle events emitted by the Core Agent Engine (`packages.harness_core`) so that Person 3 can construct the real-time observability dashboard.

---

## 1. Real-Time Telemetry Stream (`AgentEvent`)

Every state change in the engine emits an `AgentEvent` in JSON format:

```typescript
interface AgentEvent {
  event_id: string;          // e.g., "evt_a9b1c2d3e4f5"
  session_id: string;        // e.g., "sess_136667bd3da0"
  task_id: string;           // e.g., "task_456"
  timestamp: string;         // ISO 8601 string
  event_type: EventType;     // Discriminator
  component: string;         // "orchestrator" | "agent_guard" | "context_t4" | "adaptive_harness"
  status: ExecutionStatus;   // "INITIALIZING" | "RUNNING" | "COMPLETED" | "FAILED" | "STALLED"
  duration_ms?: number;      // Step duration in milliseconds
  payload: Record<string, any>;
  metadata: Record<string, any>;
}
```

---

## 2. Event Types & Recommended UI Visualizations

| `event_type` | Emitted When | UI Component to Update | Key Payload Fields |
|---|---|---|---|
| `session_started` | Task submitted | Session Header, Timer | `task`, `workspace` |
| `task_analyzed` | Analysis completes | Task Category Badge | `is_rest_api`, `referenced_files` |
| `model_selected` | Adaptive mode chosen | Harness Mode Card | `model_name`, `harness_mode`, `reasoning` |
| `plan_created` | Step plan generated | Interactive Plan Checklist | `plan: [{step_number, description, status}]` |
| `context_compressed` | ContextT4 compresses history | Context Compression Gauge | `total_tokens`, `tokens_saved_estimate`, `utilization_pct` |
| `tool_call_started` | Tool invoked | Tool Execution Spinner | `tool_name`, `arguments` |
| `tool_call_completed` | Tool finished | Tool Activity Feed | `tool_name`, `success`, `output_snippet` |
| `diagnostic_generated` | AST/Ruff found issues | Diagnostics Alert Drawer | `diagnostics: [{file_path, line_number, message, severity}]` |
| `loop_warning` | 5 repeated calls detected | Loop Warning Toast | `message` |
| `verification_completed`| Workspace verified | Verification Status Card | `success`, `syntax_valid`, `test_output` |
| `session_completed` | Execution succeeded | Final Result Banner, Metrics Card | `metrics: {total_tokens, estimated_cost_usd}` |
| `session_failed` | Task halted / stalled | Error Modal & Failure Reason | `error` |

---

## 3. UI Dashboard Components Specs

### A. ContextT4 Compression Widget
- Display a progress gauge showing current context token utilization (`utilization_pct`).
- Show **Tokens Saved Estimate** badge with count of tokens saved by ContextT4 staged elision and summarization.
- Render the 7-section structured summary when `context_strategy == 'T4_STAGED'`:
  1. *Goal*
  2. *Files Touched*
  3. *Done*
  4. *Pending*
  5. *Errors & Fixes*
  6. *Current State*
  7. *Next Step*

### B. AgentGuard Security & Health Panel
- Display active guardrails:
  - **Read-Before-Write Status**: Checked per file modification.
  - **SHA-256 Hash Drift**: Visual indicator if local files changed externally.
  - **Loop Protection Counter**: Warning at 5 repeats; stalled alarm at 8 repeated failures.
  - **Circuit Breaker Gauge**: `tool_call_count` / `max_tool_calls` (e.g. 2 / 30).

### C. AdaptiveHarness Mode Switcher
- Allow user to toggle between `GUIDED`, `DIRECT`, and `HYBRID` modes.
- Display the selector's reasoning: e.g., *"Selected DIRECT mode due to high model bash proficiency and CLI requirements."*
