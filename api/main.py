import os
import json
import uuid
import asyncio
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from pydantic import BaseModel

from api.config import settings
from api.firestore_sync import FirestoreSync
from api.bigquery_logger import BigQueryLogger
from api.sandbox import WorkspaceSandbox

# ── Lifespan ──────────────────────────────────────────────────────────

WORKSPACE_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
TESTBEDS_DIR = os.path.join(WORKSPACE_ROOT, "testbeds")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[Harness Kit API] Starting on port {settings.api_port}")
    print(f"[Harness Kit API] Engine mode: {settings.engine_mode}")
    print(f"[Harness Kit API] Project: {settings.google_cloud_project}")
    print(f"[Harness Kit API] Testbeds: {TESTBEDS_DIR}")
    task_count = len(os.listdir(TESTBEDS_DIR)) if os.path.exists(TESTBEDS_DIR) else 0
    print(f"[Harness Kit API] Available tasks: {task_count}")
    yield
    # Shutdown
    print("[Harness Kit API] Shutting down...")


# ── FastAPI App ───────────────────────────────────────────────────────

app = FastAPI(
    title="Harness Kit API",
    description="Evaluation, Observability & Sandboxing Control Plane on Google Cloud",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ────────────────────────────────────────────────────────

firestore_client = FirestoreSync()
bq_logger = BigQueryLogger()
sandbox = WorkspaceSandbox(
    testbed_root=TESTBEDS_DIR,
    firestore=firestore_client,
    bq_logger=bq_logger,
)

# Active execution registry
active_executions: Dict[str, threading.Thread] = {}


# ── Request / Response Models ─────────────────────────────────────────

class RunRequest(BaseModel):
    task_id: str
    model_id: str = "gemini-2.5-flash"
    harness_config: Optional[Dict[str, Any]] = None

class CreateTaskRequest(BaseModel):
    id: str
    title: str
    category: str = "Custom Evaluation"
    description: str = ""
    prompt: str
    eval_command: str = "pytest"
    expected_behavior: str = ""
    source_filename: str = "app.py"
    source_code: str
    fixed_code: Optional[str] = None
    test_filename: str = "test_app.py"
    test_code: str
    diff: Optional[str] = None

class CompareRequest(BaseModel):
    task_id: str
    model_id: str = "gemini-2.5-flash"
    harness_config: Optional[Dict[str, Any]] = None
    baseline_config: Optional[Dict[str, Any]] = None


# ── Health & Info ─────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "Harness Kit Control Plane",
        "version": "1.0.0",
        "engine_mode": settings.engine_mode,
        "cloud_run": bool(os.getenv("K_SERVICE")),
        "project": settings.google_cloud_project,
    }


# ── Task Endpoints ────────────────────────────────────────────────────

@app.get("/api/tasks")
def list_tasks():
    """Reads available evaluation testbeds from testbeds/."""
    tasks = []
    if os.path.exists(TESTBEDS_DIR):
        for task_name in sorted(os.listdir(TESTBEDS_DIR)):
            task_path = os.path.join(TESTBEDS_DIR, task_name)
            meta_path = os.path.join(task_path, "task.json")
            if os.path.isdir(task_path):
                meta = {"id": task_name, "title": task_name, "description": "", "category": "Benchmark"}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                
                # Auto-read python files in testbed
                files = []
                for fname in sorted(os.listdir(task_path)):
                    if fname.endswith(".py"):
                        fpath = os.path.join(task_path, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                files.append({"name": fname, "language": "python", "content": f.read()})
                        except Exception:
                            pass
                diff_path = os.path.join(task_path, "gold_patch.diff")
                diff_content = ""
                if os.path.exists(diff_path):
                    try:
                        with open(diff_path, "r", encoding="utf-8") as f:
                            diff_content = f.read()
                    except Exception:
                        pass
                if files:
                    meta["files"] = files
                if diff_content:
                    meta["diff"] = diff_content
                tasks.append(meta)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/tasks")
def create_task(req: CreateTaskRequest):
    """Creates a new evaluation testbed directory in testbeds/."""
    import re
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", req.id.strip().lower())
    if not safe_id:
        safe_id = f"custom_task_{uuid.uuid4().hex[:6]}"
    task_dir = os.path.join(TESTBEDS_DIR, safe_id)
    os.makedirs(task_dir, exist_ok=True)

    meta = {
        "id": safe_id,
        "title": req.title or safe_id,
        "category": req.category,
        "description": req.description,
        "prompt": req.prompt,
        "expected_behavior": req.expected_behavior,
        "eval_command": req.eval_command,
    }
    with open(os.path.join(task_dir, "task.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    with open(os.path.join(task_dir, req.source_filename), "w", encoding="utf-8") as f:
        f.write(req.source_code)

    with open(os.path.join(task_dir, req.test_filename), "w", encoding="utf-8") as f:
        f.write(req.test_code)

    diff_text = req.diff or f"--- a/{req.source_filename}\n+++ b/{req.source_filename}\n@@ -1 +1 @@\n# Reference fix patch"
    with open(os.path.join(task_dir, "gold_patch.diff"), "w", encoding="utf-8") as f:
        f.write(diff_text)

    meta["files"] = [
        {"name": req.source_filename, "language": "python", "content": req.source_code, "fixedContent": req.fixed_code or req.source_code},
        {"name": req.test_filename, "language": "python", "content": req.test_code},
    ]
    meta["diff"] = diff_text
    return {"status": "created", "task": meta, "task_id": safe_id}


# ── Run Endpoints ─────────────────────────────────────────────────────

@app.post("/api/runs")
def start_run(req: RunRequest):
    """Starts a new agent task execution in a background thread."""
    task_meta_path = os.path.join(TESTBEDS_DIR, req.task_id, "task.json")
    prompt = f"Fix the failing test in {req.task_id}"
    if os.path.exists(task_meta_path):
        try:
            with open(task_meta_path, "r", encoding="utf-8") as f:
                prompt = json.load(f).get("prompt", prompt)
        except Exception:
            pass

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    def _worker():
        try:
            sandbox.execute_run(
                task_id=req.task_id,
                task_prompt=prompt,
                run_id=run_id,
                model_id=req.model_id,
                harness_config=req.harness_config,
            )
        except Exception as e:
            print(f"[Worker] Run {run_id} failed: {e}")
            firestore_client.update_run_state(run_id, {
                "status": "ERROR",
                "error": str(e),
            })
        finally:
            active_executions.pop(run_id, None)

    t = threading.Thread(target=_worker, daemon=True)
    active_executions[run_id] = t
    t.start()

    return {
        "run_id": run_id,
        "task_id": req.task_id,
        "model_id": req.model_id,
        "status": "RUNNING",
    }


@app.get("/api/runs")
def list_runs(limit: int = Query(default=50, le=200)):
    """Lists recent runs."""
    return {"runs": firestore_client.list_runs(limit=limit)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Returns run metadata and summary."""
    run = firestore_client.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/runs/{run_id}/events")
def get_run_events(run_id: str):
    """Returns all events for the given run (polling mode)."""
    events = firestore_client.get_events(run_id)
    return {"run_id": run_id, "events": events, "count": len(events)}


@app.get("/api/runs/{run_id}/analytics")
def get_run_analytics(run_id: str):
    """Returns per-run analytics: turn breakdown, tool usage, failure judgment."""
    return bq_logger.get_run_analytics(run_id)


# ── SSE Streaming ─────────────────────────────────────────────────────

@app.get("/api/runs/{run_id}/stream")
async def stream_run_events(run_id: str):
    """
    Server-Sent Events endpoint for real-time event streaming.
    The frontend connects here to get live turn-by-turn updates.
    """
    queue = firestore_client.subscribe(run_id)

    async def event_generator():
        try:
            while True:
                try:
                    # Wait for events with a timeout (sends keepalive)
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"

                    # Check if run is finished
                    event_type = event.get("type", "")
                    if event_type == "RUN_FINISH":
                        yield f"data: {json.dumps({'type': 'STREAM_END'})}\n\n"
                        break
                    # Also check for terminal run updates
                    if event_type == "RUN_UPDATE":
                        status = event.get("data", {}).get("status", "")
                        if status in ("RESOLVED", "ERROR", "CANCELLED", "CONTEXT_OVERFLOW"):
                            yield f"data: {json.dumps({'type': 'STREAM_END', 'status': status})}\n\n"
                            break
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            firestore_client.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Comparison Endpoint ───────────────────────────────────────────────

@app.post("/api/compare")
def start_comparison(req: CompareRequest):
    """
    Runs the SAME task twice — once with harness, once baseline (T0 / no planning).
    Returns both run_ids so the dashboard can show side-by-side.
    """
    task_meta_path = os.path.join(TESTBEDS_DIR, req.task_id, "task.json")
    prompt = f"Fix the failing test in {req.task_id}"
    if os.path.exists(task_meta_path):
        try:
            with open(task_meta_path, "r", encoding="utf-8") as f:
                prompt = json.load(f).get("prompt", prompt)
        except Exception:
            pass

    # Harness run config (T4 + planning + predefined tools)
    harness_config = req.harness_config or {
        "context_tier": "T4",
        "enable_planning": True,
        "tool_mode": "predefined",
        "budget_cap": 32768,
        "harness_enabled": True,
    }

    # Baseline run config (T0 / no context management, no planning)
    baseline_config = req.baseline_config or {
        "context_tier": "T0",
        "enable_planning": False,
        "tool_mode": "bash_only",
        "budget_cap": 131072,
        "harness_enabled": False,
    }

    harness_run_id = f"run_h_{uuid.uuid4().hex[:6]}"
    baseline_run_id = f"run_b_{uuid.uuid4().hex[:6]}"

    def _run_variant(run_id, config, label):
        try:
            sandbox.execute_run(
                task_id=req.task_id,
                task_prompt=prompt,
                run_id=run_id,
                model_id=req.model_id,
                harness_config=config,
            )
        except Exception as e:
            print(f"[Compare] {label} run {run_id} failed: {e}")
            firestore_client.update_run_state(run_id, {"status": "ERROR", "error": str(e)})
        finally:
            active_executions.pop(run_id, None)

    t1 = threading.Thread(target=_run_variant, args=(harness_run_id, harness_config, "Harness"), daemon=True)
    t2 = threading.Thread(target=_run_variant, args=(baseline_run_id, baseline_config, "Baseline"), daemon=True)

    active_executions[harness_run_id] = t1
    active_executions[baseline_run_id] = t2
    t1.start()
    t2.start()

    return {
        "task_id": req.task_id,
        "harness_run_id": harness_run_id,
        "baseline_run_id": baseline_run_id,
        "status": "RUNNING",
    }


# ── Metrics / Analytics ──────────────────────────────────────────────

@app.get("/api/metrics/summary")
def get_metrics_summary():
    """Queries BigQuery/SQLite to feed the dashboard overview charts."""
    return bq_logger.get_metrics_summary()


@app.get("/api/metrics/compare/{harness_run_id}/{baseline_run_id}")
def get_comparison_metrics(harness_run_id: str, baseline_run_id: str):
    """Side-by-side metrics for two runs (harness vs baseline)."""
    harness = firestore_client.get_run(harness_run_id)
    baseline = firestore_client.get_run(baseline_run_id)

    if not harness or not baseline:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    harness_analytics = bq_logger.get_run_analytics(harness_run_id)
    baseline_analytics = bq_logger.get_run_analytics(baseline_run_id)

    h_summary = harness.get("summary", {})
    b_summary = baseline.get("summary", {})

    return {
        "harness": {
            "run_id": harness_run_id,
            "status": harness.get("status"),
            "resolved": h_summary.get("resolved", False),
            "total_turns": h_summary.get("total_turns", 0),
            "total_cost_usd": h_summary.get("total_cost_usd", 0),
            "tokens_total": (
                h_summary.get("tokens_in_uncached", 0)
                + h_summary.get("tokens_in_cached", 0)
                + h_summary.get("tokens_out", 0)
            ),
            "context_tier": h_summary.get("context_tier", "T4"),
            "m1_count": h_summary.get("m1_count", 0),
            "re_patch_count": h_summary.get("re_patch_count", 0),
            "analytics": harness_analytics,
        },
        "baseline": {
            "run_id": baseline_run_id,
            "status": baseline.get("status"),
            "resolved": b_summary.get("resolved", False),
            "total_turns": b_summary.get("total_turns", 0),
            "total_cost_usd": b_summary.get("total_cost_usd", 0),
            "tokens_total": (
                b_summary.get("tokens_in_uncached", 0)
                + b_summary.get("tokens_in_cached", 0)
                + b_summary.get("tokens_out", 0)
            ),
            "context_tier": b_summary.get("context_tier", "T0"),
            "m1_count": b_summary.get("m1_count", 0),
            "re_patch_count": b_summary.get("re_patch_count", 0),
            "analytics": baseline_analytics,
        },
    }


# ── Run Control ───────────────────────────────────────────────────────

@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    """Cancels an in-progress execution."""
    if run_id in active_executions:
        firestore_client.update_run_state(run_id, {"status": "CANCELLED"})
        active_executions.pop(run_id, None)
        return {"status": "CANCELLED", "run_id": run_id}
    raise HTTPException(status_code=404, detail="Active run not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=settings.api_port, reload=True)
