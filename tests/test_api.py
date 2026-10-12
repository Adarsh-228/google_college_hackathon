import os
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.bigquery_logger import BigQueryLogger

client = TestClient(app)

def test_api_health_check():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_api_list_tasks():
    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 5

def test_sqlite_analytics_views():
    db_file = "test_analytics.db"
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
