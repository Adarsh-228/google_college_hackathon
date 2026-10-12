# Harness Kit on Google Cloud
*Based on arXiv:2609.20804 — An Empirical Study of Harness Design for Coding Agents*

> **"Don't guess your agent's harness. Measure it."**

Harness Kit is a modular, production-ready framework for Gemini-based coding agents on Google Cloud. It provides drop-in harness modules (`ContextT4`, `AgentGuard`, `AdaptiveHarness`, `AgentTrace`) and an evaluation layer that measures which configuration wins for a given model, budget, and task.

---

## 3-Person Architecture & Sub-Project Ownership

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              HARNESS KIT ARCHITECTURE                                  │
├────────────────────────────┬────────────────────────────┬──────────────────────────────┤
│    PERSON 1 (Engineer A)   │    PERSON 2 (Engineer B)   │     PERSON 3 (Engineer C)    │
│    Core Agent Harness &    │  Cloud Backend, Sandboxing │    Next.js Grey Dashboard,   │
│   Vertex AI Intelligence   │   & BigQuery Data Pipeline │    Eval Testbeds & Demo Kit  │
├────────────────────────────┼────────────────────────────┼──────────────────────────────┤
│ • ContextT4 (M1/M3, ±M2)   │ • Cloud Run FastAPI Server │ • Next.js 14 Dashboard App   │
│ • AgentGuard (RBW, Lint)   │ • Cloud Run Sandbox Runner │ • Minimalist Grey-Scale UI   │
│ • Streak Circuit Breaker   │ • Firestore Live Sync      │ • Dual-Pane Live Comparator  │
│ • Predefined / Bash Modes  │ • BigQuery Data Warehouse  │ • AgentTrace Metric Charts   │
│ • Vertex AI / AI Studio    │ • Cache-Aware Token Logs   │ • 5 Buggy Eval Testbeds      │
│ • Mock LLM Replayer        │ • AgentTrace SQL Views     │ • Firebase Auth & Hosting    │
└────────────────────────────┴────────────────────────────┴──────────────────────────────┘
```

### Folder Structure

```
googleXrbu/
├── packages/harness_core/       # [Person 1] Core ReAct harness, ContextT4, AgentGuard, Vertex AI
│   ├── guard.py                 # Read-Before-Write, Zero-Turn Linter, Streak Circuit Breaker
│   ├── context_t4.py            # Staged compaction (M1 elision @ 60%, M3 summary @ 85%)
│   ├── tools.py                 # ToolRegistry (predefined tools & bash + diff linter)
│   ├── planning.py              # Dynamic plan injection outside history
│   ├── providers.py             # Vertex AI Gemini adapter + deterministic MockLLMClient
│   └── runner.py                # Public generator contract: run_agent_task()
├── api/                         # [Person 2] Cloud Run control plane, sandboxing & data pipelines
│   ├── main.py                  # FastAPI service (POST /api/runs, GET /api/metrics/summary)
│   ├── sandbox.py               # Temporary directory cloning and run driver
│   ├── firestore_sync.py        # Real-time Firestore document & subcollection streaming
│   ├── bigquery_logger.py       # BigQuery analytics warehouse + offline SQLite fallback
│   └── mock_runner.py           # Offline mock generator for isolated API/UI verification
├── testbeds/                    # [Person 3] 5 Reproducible buggy benchmark repositories
│   ├── task_01_off_by_one/      # Pagination off-by-one boundary bug
│   ├── task_02_auth_token_leak/ # Plain-text Bearer token leak in logs
│   ├── task_03_stuck_loop_api/  # Flaky retry loop (triggers 5-streak warning & 8-streak halt)
│   ├── task_04_verbose_log_overflow/ # 3000-line log output (overflows T0, compacts via T4)
│   └── task_05_circular_dependency/  # Broken imports (caught by zero-turn linter)
├── web/                         # [Person 3] Next.js 14 grey-themed dashboard & live comparator
│   ├── app/page.tsx             # Dual-Pane comparator, BigQuery scorecard, testbed selector
│   ├── components/              # TokenMeter, TurnStream, Badges, MetricsScorecard
│   ├── lib/api.ts & mockData.ts # Dual-mode API client with seamless offline mock fallback
│   └── firebase.json            # Firebase Hosting configuration
├── tests/                       # Unit & integration test suites
│   ├── test_harness_core.py     # Tests for RBW, linter, streak breaker, and ContextT4
│   ├── test_api.py              # Tests for FastAPI endpoints and SQLite views
│   └── test_end_to_end.py       # End-to-end task execution with mock replayer
├── requirements.txt
└── Dockerfile
```

---

## Quickstart Guide

### 1. Run Unit Tests (Person 1 & 2 Verification)
```bash
# Install dependencies
pip install -r requirements.txt

# Run all test suites
pytest -v
```

### 2. Start Backend API (Person 2)
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
Endpoints:
- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/api/tasks` (5 Benchmark testbeds)
- `http://localhost:8000/api/metrics/summary` (BigQuery/SQLite analytical views)

### 3. Start Next.js Dashboard (Person 3)
```bash
cd web
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Live A/B Demo Walkthrough

1. Open the dashboard at `http://localhost:3000`.
2. Click **"⚡ Run Demo (Task 04 Overflow)"**:
   - **Left Pane (Baseline Agent)**: Runs unmanaged ($T0$) at a 32k window cap. The verbose 3000-line test log fills the context window up to 34,100 tokens. The agent **crashes with `[CONTEXT OVERFLOW]` failure**.
   - **Right Pane (Harness Kit Agent)**: Runs $T4$ staged compaction. At 60% of budget ($B_1$), **`[M1 ELISION]` fires automatically**, substituting the 3000-line output with a lightweight stub at zero model cost. The agent stays well under budget (4,120 tokens), applies the surgical IPv4 regex fix, and **resolves the task with `[RESOLVED]`**.
3. Switch to the **"AgentTrace BigQuery Analytics"** tab to view pass rate deltas (+70% at 32k cap), token savings (75%), cost delta, and failure stage attribution breakdowns.

---

## Google Cloud Deployment

### Deploy Backend to Cloud Run
```bash
gcloud run deploy harness-kit-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=your-gcp-project,GEMINI_API_KEY=your-api-key
```

### Deploy Dashboard to Firebase Hosting
```bash
cd web
npm run build
firebase deploy --only hosting
```
