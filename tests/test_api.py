import os
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.bigquery_logger import BigQueryLogger
from api.firestore_sync import FirestoreSync
from api.sandbox import WorkspaceSandbox

client = TestClient(app)

# ── API Endpoint Tests ────────────────────────────────────────────────

def test_api_health_check():
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["engine_mode"] in ("mock", "live")

def test_api_list_tasks():
    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.json()
    assert "tasks" in data
    assert "count" in data
    assert data["count"] >= 5

def test_api_start_run():
    res = client.post("/api/runs", json={
        "task_id": "task_01_off_by_one",
        "model_id": "gemini-2.5-flash",
    })
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    assert data["status"] == "RUNNING"

def test_api_list_runs():
    res = client.get("/api/runs")
    assert res.status_code == 200
    data = res.json()
    assert "runs" in data

def test_api_start_comparison():
    res = client.post("/api/compare", json={
        "task_id": "task_01_off_by_one",
    })
    assert res.status_code == 200
    data = res.json()
    assert "harness_run_id" in data
    assert "baseline_run_id" in data
    assert data["harness_run_id"].startswith("run_h_")
    assert data["baseline_run_id"].startswith("run_b_")

def test_api_metrics_summary():
    res = client.get("/api/metrics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_runs" in data
    assert "pass_rate" in data
    assert "comparisons" in data
    assert "failures" in data
    assert "phase_breakdown" in data
    assert "tool_usage" in data


# ── BigQuery Logger / SQLite Tests ────────────────────────────────────

def test_sqlite_run_logging():
    """Tests that run data is properly stored and queryable."""
    db_file = "test_analytics_runs.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    logger = BigQueryLogger(db_path=db_file)
    logger.log_run({
        "run_id": "test_run_1",
        "task_id": "task_01_off_by_one",
        "model": "gemini-2.5-flash",
        "tool_mode": "predefined",
        "planning": True,
        "context_tier": "T4",
        "budget_cap": 32768,
        "resolved": True,
        "tokens_in_uncached": 5000,
        "tokens_in_cached": 1000,
        "tokens_out": 300,
        "total_cost_usd": 0.0008,
        "total_turns": 6,
        "stop_reason": "RESOLVED",
        "re_patch_count": 1,
        "m1_count": 1,
        "m3_count": 0,
    })

    metrics = logger.get_metrics_summary()
    assert metrics["total_runs"] == 1
    assert metrics["pass_rate"] == 1.0
    assert len(metrics["comparisons"]) == 1

    if os.path.exists(db_file):
        os.remove(db_file)


def test_sqlite_turn_and_tool_logging():
    """Tests per-turn and per-tool-call logging."""
    db_file = "test_analytics_turns.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    logger = BigQueryLogger(db_path=db_file)

    # Log a run first
    logger.log_run({
        "run_id": "test_run_2",
        "task_id": "task_02_auth_token_leak",
        "resolved": False,
        "stop_reason": "CONTEXT_OVERFLOW",
        "total_cost_usd": 0.05,
        "total_turns": 3,
    })

    # Log turns
    logger.log_turn("test_run_2", 1, "exploration", "read_file", 500, 100, 120.5)
    logger.log_turn("test_run_2", 2, "localization", "grep", 400, 80, 95.0)
    logger.log_turn("test_run_2", 3, "patch_implementation", "edit_file", 600, 200, 200.0)

    # Log tool calls
    logger.log_tool_call("test_run_2", 1, "read_file", {"path": "app.py"}, False)
    logger.log_tool_call("test_run_2", 2, "grep", {"pattern": "token"}, False)
    logger.log_tool_call("test_run_2", 3, "edit_file", {"path": "app.py"}, True, "LINT_DETECTED")

    # Verify analytics
    analytics = logger.get_run_analytics("test_run_2")
    assert len(analytics["turns"]) == 3
    assert len(analytics["tool_calls"]) == 3
    assert analytics["judgment"] is not None
    assert analytics["judgment"]["failure_stage"] == "verification"

    # Verify summary views
    metrics = logger.get_metrics_summary()
    assert metrics["total_runs"] == 1
    assert metrics["pass_rate"] == 0.0
    assert len(metrics["failures"]) >= 1
    assert len(metrics["phase_breakdown"]) >= 1
    assert len(metrics["tool_usage"]) >= 1

    if os.path.exists(db_file):
        os.remove(db_file)


def test_sqlite_failure_classification():
    """Tests that failure stages are correctly classified."""
    db_file = "test_analytics_failures.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    logger = BigQueryLogger(db_path=db_file)

    test_cases = [
        ("run_a", "CONTEXT_OVERFLOW", "verification"),
        ("run_b", "CIRCUIT_BREAKER_STUCK", "line_localization"),
        ("run_c", "ERROR", "execution_error"),
        ("run_d", "UNKNOWN", "patch_implementation"),
    ]

    for run_id, stop_reason, expected_stage in test_cases:
        logger.log_run({
            "run_id": run_id,
            "task_id": "task_01",
            "resolved": False,
            "stop_reason": stop_reason,
        })

    # Check each judgment
    for run_id, _, expected_stage in test_cases:
        analytics = logger.get_run_analytics(run_id)
        assert analytics["judgment"] is not None, f"No judgment for {run_id}"
        assert analytics["judgment"]["failure_stage"] == expected_stage, \
            f"Expected {expected_stage}, got {analytics['judgment']['failure_stage']} for {run_id}"

    if os.path.exists(db_file):
        os.remove(db_file)


# ── Firestore Sync Tests ─────────────────────────────────────────────

def test_firestore_local_crud():
    """Tests Firestore in-memory fallback CRUD."""
    fs = FirestoreSync()

    fs.create_run("test_run_fs", {"taskId": "task_01", "modelId": "flash"})
    assert fs.get_run("test_run_fs") is not None
    assert fs.get_run("test_run_fs")["status"] == "RUNNING"

    fs.update_run_state("test_run_fs", {"status": "RESOLVED"})
    assert fs.get_run("test_run_fs")["status"] == "RESOLVED"

    fs.append_event("test_run_fs", {"type": "TOOL_CALL", "data": {"tool": "bash"}})
    events = fs.get_events("test_run_fs")
    assert len(events) == 1
    assert events[0]["type"] == "TOOL_CALL"

    runs = fs.list_runs()
    assert len(runs) >= 1


# ── Sandbox Tests ─────────────────────────────────────────────────────

def test_sandbox_mock_execution():
    """Tests full sandbox execution with mock runner."""
    db_file = "test_sandbox.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    fs = FirestoreSync()
    bq = BigQueryLogger(db_path=db_file)
    testbed_root = os.path.join(os.path.dirname(__file__), "..", "testbeds")
    sb = WorkspaceSandbox(testbed_root=testbed_root, firestore=fs, bq_logger=bq)

    result = sb.execute_run(
        task_id="task_01_off_by_one",
        task_prompt="Fix the off-by-one bug",
        model_id="gemini-2.5-flash",
    )

    assert result["run_id"].startswith("run_")
    assert result["task_id"] == "task_01_off_by_one"
    assert "resolved" in result
    assert "total_cost_usd" in result
    assert "duration_ms" in result
    assert result["duration_ms"] > 0

    # Verify events were streamed to Firestore
    events = fs.get_events(result["run_id"])
    assert len(events) > 0

    # Verify run was logged to BigQuery/SQLite
    metrics = bq.get_metrics_summary()
    assert metrics["total_runs"] >= 1

    if os.path.exists(db_file):
        os.remove(db_file)
