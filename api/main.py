import os
import json
import uuid
import threading
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.firestore_sync import FirestoreSync
from api.bigquery_logger import BigQueryLogger
from api.sandbox import WorkspaceSandbox

# FastAPI app initialization
app = FastAPI(
    title="Harness Kit API",
    description="Evaluation, Observability & Sandboxing Control Plane on Google Cloud",
    version="1.0.0",
)

# Enable CORS for Next.js Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Project paths & singletons
WORKSPACE_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
TESTBEDS_DIR = os.path.join(WORKSPACE_ROOT, "testbeds")

firestore_client = FirestoreSync()
bq_logger = BigQueryLogger()
sandbox = WorkspaceSandbox(testbed_root=TESTBEDS_DIR, firestore=firestore_client, bq_logger=bq_logger)

# Active execution registry
active_executions: Dict[str, threading.Thread] = {}

class RunRequest(BaseModel):
    task_id: str
    model_id: str = "gemini-2.5-flash"
    harness_config: Optional[Dict[str, Any]] = None

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "Harness Kit Control Plane",
        "cloud_run": bool(os.getenv("K_SERVICE")),
    }

@app.get("/api/tasks")
def list_tasks():
    """Reads available evaluation testbeds from testbeds/."""
    tasks = []
    if os.path.exists(TESTBEDS_DIR):
        for task_name in sorted(os.listdir(TESTBEDS_DIR)):
            task_path = os.path.join(TESTBEDS_DIR, task_name)
            meta_path = os.path.join(task_path, "task.json")
            if os.path.isdir(task_path):
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        tasks.append(meta)
                    except Exception:
                        tasks.append({"id": task_name, "title": task_name, "description": ""})
                else:
                    tasks.append({"id": task_name, "title": task_name, "description": ""})
    return {"tasks": tasks}

@app.post("/api/runs")
def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Starts a new agent task execution."""
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
        sandbox.execute_run(
            task_id=req.task_id,
            task_prompt=prompt,
            run_id=run_id,
            model_id=req.model_id,
            harness_config=req.harness_config,
        )

    t = threading.Thread(target=_worker, daemon=True)
    active_executions[run_id] = t
    t.start()

    return {
        "run_id": run_id,
        "task_id": req.task_id,
        "status": "RUNNING",
    }

@app.get("/api/runs")
def list_runs():
    """Lists recent runs."""
    return {"runs": firestore_client.list_runs()}

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Returns run metadata and summary."""
    run = firestore_client.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.get("/api/runs/{run_id}/events")
def get_run_events(run_id: str):
    """Returns streamed events for the given run."""
    events = firestore_client.get_events(run_id)
    return {"run_id": run_id, "events": events}

@app.get("/api/metrics/summary")
def get_metrics_summary():
    """Queries BigQuery/SQLite to feed the dashboard charts."""
    return bq_logger.get_metrics_summary()

@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    """Cancels an in-progress execution."""
    if run_id in active_executions:
        firestore_client.update_run_state(run_id, {"status": "CANCELLED"})
        return {"status": "CANCELLED", "run_id": run_id}
    raise HTTPException(status_code=404, detail="Active run not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
