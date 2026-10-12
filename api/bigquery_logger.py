import os
import sqlite3
import hashlib
from typing import Dict, Any, List, Optional

class BigQueryLogger:
    """
    Data warehouse logger for runs, turns, tool calls, and AgentTrace telemetry.
    Supports Google Cloud BigQuery and offline SQLite fallback.
    """

    def __init__(self, db_path: str = "harness_analytics.db", project_id: Optional[str] = None):
        self.db_path = db_path
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "rbux-37584")
        self._bq_client = None
        self._init_sqlite()
        self._init_bigquery()

    def _init_sqlite(self):
        """Initializes SQLite tables and AgentTrace analytical views."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # 1. runs table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            task_id TEXT,
            model TEXT,
            tool_mode TEXT,
            planning INTEGER,
            context_tier TEXT,
            budget_cap INTEGER,
            resolved INTEGER,
            tokens_in_uncached INTEGER,
            tokens_in_cached INTEGER,
            tokens_out INTEGER,
            cost REAL,
            stop_reason TEXT,
            re_patch_count INTEGER DEFAULT 0,
            m1_count INTEGER DEFAULT 0,
            m3_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. turns table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            run_id TEXT,
            turn_idx INTEGER,
            phase TEXT,
            tool TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            compaction_event TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 3. tool_calls table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            run_id TEXT,
            turn_idx INTEGER,
            tool TEXT,
            args_hash TEXT,
            target_path TEXT,
            is_error INTEGER,
            guard_event TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 4. judgments table (AgentTrace)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS judgments (
            run_id TEXT PRIMARY KEY,
            failure_stage TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # AgentTrace Views
        cur.execute("DROP VIEW IF EXISTS v_harness_comparison_summary")
        cur.execute("""
        CREATE VIEW v_harness_comparison_summary AS
        SELECT 
            context_tier,
            tool_mode,
            planning,
            budget_cap,
            COUNT(*) as total_runs,
            SUM(resolved) * 1.0 / COUNT(*) as pass_rate,
            AVG(tokens_in_uncached + tokens_in_cached + tokens_out) as avg_tokens,
            AVG(cost) as avg_cost,
            AVG(re_patch_count) as avg_re_patches
        FROM runs
        GROUP BY context_tier, tool_mode, planning, budget_cap
        """)

        cur.execute("DROP VIEW IF EXISTS v_failure_stage_attribution")
        cur.execute("""
        CREATE VIEW v_failure_stage_attribution AS
        SELECT 
            r.context_tier,
            r.model,
            j.failure_stage,
            COUNT(*) as count
        FROM runs r
        JOIN judgments j ON r.run_id = j.run_id
        WHERE r.resolved = 0
        GROUP BY r.context_tier, r.model, j.failure_stage
        """)

        conn.commit()
        conn.close()

    def _init_bigquery(self):
        try:
            from google.cloud import bigquery
            if self.project_id:
                self._bq_client = bigquery.Client(project=self.project_id)
        except Exception:
            self._bq_client = None

    def log_run(self, run_data: Dict[str, Any]) -> None:
        """Logs completed run summary to SQLite and BigQuery."""
        # SQLite insertion
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO runs (
            run_id, task_id, model, tool_mode, planning, context_tier,
            budget_cap, resolved, tokens_in_uncached, tokens_in_cached,
            tokens_out, cost, stop_reason, re_patch_count, m1_count, m3_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data.get("run_id"),
            run_data.get("task_id"),
            run_data.get("model", "gemini-2.5-flash"),
            run_data.get("tool_mode", "predefined"),
            1 if run_data.get("planning", True) else 0,
            run_data.get("context_tier", "T4"),
            run_data.get("budget_cap", 32768),
            1 if run_data.get("resolved") else 0,
            run_data.get("tokens_in_uncached", 0),
            run_data.get("tokens_in_cached", 0),
            run_data.get("tokens_out", 0),
            run_data.get("total_cost_usd", 0.0),
            run_data.get("stop_reason", "UNKNOWN"),
            run_data.get("re_patch_count", 0),
            run_data.get("m1_count", 0),
            run_data.get("m3_count", 0),
        ))

        # Log failure stage judgment if unresolved
        if not run_data.get("resolved"):
            stop_reason = run_data.get("stop_reason", "")
            stage = "patch_implementation"
            if stop_reason == "CONTEXT_OVERFLOW":
                stage = "verification"
            elif stop_reason == "CIRCUIT_BREAKER_STUCK":
                stage = "line_localization"
            
            cur.execute("""
            INSERT OR REPLACE INTO judgments (run_id, failure_stage, reason)
            VALUES (?, ?, ?)
            """, (run_data.get("run_id"), stage, f"Terminated by {stop_reason}"))

        conn.commit()
        conn.close()

        # BigQuery insertion if enabled
        if self._bq_client:
            try:
                table_id = f"{self.project_id}.harness_analytics.runs"
                self._bq_client.insert_rows_json(table_id, [run_data])
            except Exception as e:
                print(f"[BigQuery Warning] Failed to log run: {e}")

    def log_turn(self, run_id: str, turn_idx: int, phase: str, tool: str, tokens_in: int, tokens_out: int, compaction_event: Optional[str] = None):
        """Logs turn event."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO turns (run_id, turn_idx, phase, tool, tokens_in, tokens_out, compaction_event)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, turn_idx, phase, tool, tokens_in, tokens_out, compaction_event))
        conn.commit()
        conn.close()

    def log_tool_call(self, run_id: str, turn_idx: int, tool: str, args: Dict[str, Any], is_error: bool, guard_event: Optional[str] = None):
        """Logs tool invocation."""
        args_hash = hashlib.sha256(str(args).encode()).hexdigest()[:8]
        target_path = str(args.get("path", "")) if isinstance(args, dict) else ""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO tool_calls (run_id, turn_idx, tool, args_hash, target_path, is_error, guard_event)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, turn_idx, tool, args_hash, target_path, 1 if is_error else 0, guard_event))
        conn.commit()
        conn.close()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Queries analytical views for dashboard charts."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Overall counts
        cur.execute("SELECT COUNT(*) as total, SUM(resolved) as passed, AVG(cost) as avg_cost FROM runs")
        row = cur.fetchone()
        total_runs = row["total"] or 0
        passed_runs = row["passed"] or 0
        avg_cost = row["avg_cost"] or 0.0

        # Harness vs Baseline comparison
        cur.execute("SELECT * FROM v_harness_comparison_summary")
        comparisons = [dict(r) for r in cur.fetchall()]

        # Failure attribution breakdown
        cur.execute("SELECT * FROM v_failure_stage_attribution")
        failures = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {
            "total_runs": total_runs,
            "pass_rate": (passed_runs / total_runs) if total_runs > 0 else 0.0,
            "avg_cost_usd": avg_cost,
            "comparisons": comparisons,
            "failures": failures,
        }
