import os
import sqlite3
import hashlib
import time
from typing import Dict, Any, List, Optional
from api.config import settings


class BigQueryLogger:
    """
    Data warehouse logger for runs, turns, tool calls, and AgentTrace telemetry.
    Supports Google Cloud BigQuery and offline SQLite fallback.
    """

    def __init__(self, db_path: Optional[str] = None, project_id: Optional[str] = None):
        self.db_path = db_path or settings.sqlite_db_path
        self.project_id = project_id or settings.google_cloud_project
        self.dataset_id = settings.bq_dataset
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
            total_turns INTEGER DEFAULT 0,
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
            duration_ms REAL DEFAULT 0,
            compaction_event TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (run_id, turn_idx)
        )
        """)

        # 3. tool_calls table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # 4. judgments table (AgentTrace failure classification)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS judgments (
            run_id TEXT PRIMARY KEY,
            failure_stage TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ── AgentTrace Analytical Views ──────────────────────────────

        # Harness configuration comparison (the main dashboard chart)
        cur.execute("DROP VIEW IF EXISTS v_harness_comparison_summary")
        cur.execute("""
        CREATE VIEW v_harness_comparison_summary AS
        SELECT 
            context_tier,
            tool_mode,
            planning,
            budget_cap,
            model,
            COUNT(*) as total_runs,
            SUM(resolved) * 1.0 / COUNT(*) as pass_rate,
            AVG(tokens_in_uncached + tokens_in_cached + tokens_out) as avg_tokens,
            AVG(cost) as avg_cost,
            AVG(total_turns) as avg_turns,
            AVG(re_patch_count) as avg_re_patches,
            AVG(m1_count) as avg_m1_compactions,
            AVG(m3_count) as avg_m3_compactions
        FROM runs
        GROUP BY context_tier, tool_mode, planning, budget_cap, model
        """)

        # Failure stage attribution (AgentTrace pipeline)
        cur.execute("DROP VIEW IF EXISTS v_failure_stage_attribution")
        cur.execute("""
        CREATE VIEW v_failure_stage_attribution AS
        SELECT 
            r.context_tier,
            r.model,
            j.failure_stage,
            j.reason,
            COUNT(*) as count
        FROM runs r
        JOIN judgments j ON r.run_id = j.run_id
        WHERE r.resolved = 0
        GROUP BY r.context_tier, r.model, j.failure_stage, j.reason
        """)

        # Phase breakdown (how many turns in each phase)
        cur.execute("DROP VIEW IF EXISTS v_phase_breakdown")
        cur.execute("""
        CREATE VIEW v_phase_breakdown AS
        SELECT
            t.run_id,
            r.context_tier,
            r.model,
            t.phase,
            COUNT(*) as turn_count,
            SUM(t.tokens_in + t.tokens_out) as phase_tokens,
            SUM(t.duration_ms) as phase_duration_ms
        FROM turns t
        JOIN runs r ON t.run_id = r.run_id
        GROUP BY t.run_id, r.context_tier, r.model, t.phase
        """)

        # Tool usage frequency
        cur.execute("DROP VIEW IF EXISTS v_tool_usage")
        cur.execute("""
        CREATE VIEW v_tool_usage AS
        SELECT
            r.context_tier,
            r.model,
            tc.tool,
            COUNT(*) as call_count,
            SUM(tc.is_error) as error_count,
            SUM(CASE WHEN tc.guard_event IS NOT NULL THEN 1 ELSE 0 END) as guarded_count
        FROM tool_calls tc
        JOIN runs r ON tc.run_id = r.run_id
        GROUP BY r.context_tier, r.model, tc.tool
        """)

        # Cost by model comparison
        cur.execute("DROP VIEW IF EXISTS v_cost_by_model")
        cur.execute("""
        CREATE VIEW v_cost_by_model AS
        SELECT
            model,
            context_tier,
            COUNT(*) as runs,
            AVG(cost) as avg_cost,
            MIN(cost) as min_cost,
            MAX(cost) as max_cost,
            SUM(cost) as total_cost,
            AVG(tokens_in_uncached + tokens_in_cached) as avg_input_tokens,
            AVG(tokens_out) as avg_output_tokens
        FROM runs
        GROUP BY model, context_tier
        """)

        conn.commit()
        conn.close()

    def _init_bigquery(self):
        """Initializes BigQuery client and ensures dataset + tables exist."""
        try:
            cred_path = settings.google_application_credentials
            if cred_path and os.path.exists(cred_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(cred_path)

            from google.cloud import bigquery
            if self.project_id:
                self._bq_client = bigquery.Client(project=self.project_id)
                self._ensure_bq_schema()
                print(f"[BigQuery] Connected to project: {self.project_id}")
        except Exception as e:
            self._bq_client = None
            print(f"[BigQuery] Using SQLite fallback: {e}")

    def _ensure_bq_schema(self):
        """Creates BigQuery dataset and tables if they don't exist."""
        if not self._bq_client:
            return

        from google.cloud import bigquery

        dataset_ref = f"{self.project_id}.{self.dataset_id}"

        # Create dataset
        try:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = settings.google_cloud_region
            self._bq_client.create_dataset(dataset, exists_ok=True)
        except Exception as e:
            print(f"[BigQuery Warning] Dataset creation: {e}")

        # Create runs table
        runs_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("task_id", "STRING"),
            bigquery.SchemaField("model", "STRING"),
            bigquery.SchemaField("tool_mode", "STRING"),
            bigquery.SchemaField("planning", "BOOLEAN"),
            bigquery.SchemaField("context_tier", "STRING"),
            bigquery.SchemaField("budget_cap", "INTEGER"),
            bigquery.SchemaField("resolved", "BOOLEAN"),
            bigquery.SchemaField("tokens_in_uncached", "INTEGER"),
            bigquery.SchemaField("tokens_in_cached", "INTEGER"),
            bigquery.SchemaField("tokens_out", "INTEGER"),
            bigquery.SchemaField("total_cost_usd", "FLOAT"),
            bigquery.SchemaField("stop_reason", "STRING"),
            bigquery.SchemaField("total_turns", "INTEGER"),
            bigquery.SchemaField("re_patch_count", "INTEGER"),
            bigquery.SchemaField("m1_count", "INTEGER"),
            bigquery.SchemaField("m3_count", "INTEGER"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        self._create_table_if_not_exists(f"{dataset_ref}.{settings.bq_runs_table}", runs_schema)

        # Create turns table
        turns_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("turn_idx", "INTEGER"),
            bigquery.SchemaField("phase", "STRING"),
            bigquery.SchemaField("tool", "STRING"),
            bigquery.SchemaField("tokens_in", "INTEGER"),
            bigquery.SchemaField("tokens_out", "INTEGER"),
            bigquery.SchemaField("duration_ms", "FLOAT"),
            bigquery.SchemaField("compaction_event", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        self._create_table_if_not_exists(f"{dataset_ref}.{settings.bq_turns_table}", turns_schema)

        # Create tool_calls table
        tool_calls_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("turn_idx", "INTEGER"),
            bigquery.SchemaField("tool", "STRING"),
            bigquery.SchemaField("args_hash", "STRING"),
            bigquery.SchemaField("target_path", "STRING"),
            bigquery.SchemaField("is_error", "BOOLEAN"),
            bigquery.SchemaField("guard_event", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        self._create_table_if_not_exists(f"{dataset_ref}.{settings.bq_tool_calls_table}", tool_calls_schema)

        # Create judgments table
        judgments_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("failure_stage", "STRING"),
            bigquery.SchemaField("reason", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        self._create_table_if_not_exists(f"{dataset_ref}.{settings.bq_judgments_table}", judgments_schema)

        # Create BigQuery Analytical Views
        self._create_or_replace_bq_views(dataset_ref)

    def _create_table_if_not_exists(self, table_id: str, schema):
        """Helper to create a BQ table if it doesn't exist."""
        if not self._bq_client:
            return
        from google.cloud import bigquery
        try:
            table = bigquery.Table(table_id, schema=schema)
            self._bq_client.create_table(table, exists_ok=True)
        except Exception as e:
            print(f"[BigQuery Warning] Table creation for {table_id}: {e}")

    def _create_or_replace_bq_views(self, dataset_ref: str):
        """Creates or updates the 5 AgentTrace analytical views in BigQuery."""
        if not self._bq_client:
            return
        from google.cloud import bigquery

        views = {
            "v_harness_comparison_summary": f"""
                SELECT 
                    context_tier,
                    tool_mode,
                    planning,
                    budget_cap,
                    model,
                    COUNT(*) as total_runs,
                    SUM(CAST(resolved AS INT64)) * 1.0 / COUNT(*) as pass_rate,
                    AVG(tokens_in_uncached + tokens_in_cached + tokens_out) as avg_tokens,
                    AVG(total_cost_usd) as avg_cost,
                    AVG(total_turns) as avg_turns,
                    AVG(re_patch_count) as avg_re_patches,
                    AVG(m1_count) as avg_m1_compactions,
                    AVG(m3_count) as avg_m3_compactions
                FROM `{dataset_ref}.{settings.bq_runs_table}`
                GROUP BY context_tier, tool_mode, planning, budget_cap, model
            """,
            "v_failure_stage_attribution": f"""
                SELECT 
                    r.context_tier,
                    r.model,
                    j.failure_stage,
                    j.reason,
                    COUNT(*) as count
                FROM `{dataset_ref}.{settings.bq_runs_table}` r
                JOIN `{dataset_ref}.{settings.bq_judgments_table}` j ON r.run_id = j.run_id
                WHERE r.resolved = FALSE
                GROUP BY r.context_tier, r.model, j.failure_stage, j.reason
            """,
            "v_phase_breakdown": f"""
                SELECT
                    t.run_id,
                    r.context_tier,
                    r.model,
                    t.phase,
                    COUNT(*) as turn_count,
                    SUM(t.tokens_in + t.tokens_out) as phase_tokens,
                    SUM(t.duration_ms) as phase_duration_ms
                FROM `{dataset_ref}.{settings.bq_turns_table}` t
                JOIN `{dataset_ref}.{settings.bq_runs_table}` r ON t.run_id = r.run_id
                GROUP BY t.run_id, r.context_tier, r.model, t.phase
            """,
            "v_tool_usage": f"""
                SELECT
                    r.context_tier,
                    r.model,
                    tc.tool,
                    COUNT(*) as call_count,
                    SUM(CAST(tc.is_error AS INT64)) as error_count,
                    SUM(CASE WHEN tc.guard_event IS NOT NULL THEN 1 ELSE 0 END) as guarded_count
                FROM `{dataset_ref}.{settings.bq_tool_calls_table}` tc
                JOIN `{dataset_ref}.{settings.bq_runs_table}` r ON tc.run_id = r.run_id
                GROUP BY r.context_tier, r.model, tc.tool
            """,
            "v_cost_by_model": f"""
                SELECT
                    model,
                    context_tier,
                    COUNT(*) as runs,
                    AVG(total_cost_usd) as avg_cost,
                    MIN(total_cost_usd) as min_cost,
                    MAX(total_cost_usd) as max_cost,
                    SUM(total_cost_usd) as total_cost,
                    AVG(tokens_in_uncached + tokens_in_cached) as avg_input_tokens,
                    AVG(tokens_out) as avg_output_tokens
                FROM `{dataset_ref}.{settings.bq_runs_table}`
                GROUP BY model, context_tier
            """
        }

        for view_name, query in views.items():
            view_id = f"{dataset_ref}.{view_name}"
            try:
                view = bigquery.Table(view_id)
                view.view_query = query
                self._bq_client.create_table(view, exists_ok=True)
            except Exception as e:
                print(f"[BigQuery Warning] View creation for {view_name}: {e}")

    # ── Logging Methods ──────────────────────────────────────────────

    def log_run(self, run_data: Dict[str, Any]) -> None:
        """Logs completed run summary to SQLite and BigQuery."""
        # SQLite insertion
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO runs (
            run_id, task_id, model, tool_mode, planning, context_tier,
            budget_cap, resolved, tokens_in_uncached, tokens_in_cached,
            tokens_out, cost, stop_reason, total_turns,
            re_patch_count, m1_count, m3_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            run_data.get("total_turns", 0),
            run_data.get("re_patch_count", 0),
            run_data.get("m1_count", 0),
            run_data.get("m3_count", 0),
        ))

        # Log failure stage judgment if unresolved
        stage = ""
        stop_reason = run_data.get("stop_reason", "")
        if not run_data.get("resolved"):
            stage = self._classify_failure_stage(stop_reason)

            cur.execute("""
            INSERT OR REPLACE INTO judgments (run_id, failure_stage, reason)
            VALUES (?, ?, ?)
            """, (run_data.get("run_id"), stage, f"Terminated by {stop_reason}"))

        conn.commit()
        conn.close()

        # BigQuery insertion if enabled
        if self._bq_client and self.db_path == settings.sqlite_db_path:
            try:
                table_id = f"{self.project_id}.{self.dataset_id}.{settings.bq_runs_table}"
                bq_row = {
                    **run_data,
                    "planning": bool(run_data.get("planning", True)),
                    "resolved": bool(run_data.get("resolved", False)),
                    "is_error": bool(run_data.get("is_error", False)),
                    "created_at": time.time(),
                }
                errors = self._bq_client.insert_rows_json(table_id, [bq_row])
                if errors:
                    print(f"[BigQuery Warning] Row insert errors: {errors}")

                # If failed, also log judgment to BigQuery
                if not run_data.get("resolved") and stage:
                    judgments_table_id = f"{self.project_id}.{self.dataset_id}.{settings.bq_judgments_table}"
                    self._bq_client.insert_rows_json(judgments_table_id, [{
                        "run_id": run_data.get("run_id"),
                        "failure_stage": stage,
                        "reason": f"Terminated by {stop_reason}",
                        "created_at": time.time(),
                    }])
            except Exception as e:
                print(f"[BigQuery Warning] Failed to log run: {e}")

    def log_turn(self, run_id: str, turn_idx: int, phase: str, tool: str,
                 tokens_in: int, tokens_out: int, duration_ms: float = 0,
                 compaction_event: Optional[str] = None):
        """Logs turn event to SQLite and BigQuery."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO turns (run_id, turn_idx, phase, tool, tokens_in, tokens_out, duration_ms, compaction_event)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, turn_idx, phase, tool, tokens_in, tokens_out, duration_ms, compaction_event))
        conn.commit()
        conn.close()

        if self._bq_client and self.db_path == settings.sqlite_db_path:
            try:
                table_id = f"{self.project_id}.{self.dataset_id}.{settings.bq_turns_table}"
                self._bq_client.insert_rows_json(table_id, [{
                    "run_id": run_id, "turn_idx": turn_idx, "phase": phase,
                    "tool": tool, "tokens_in": tokens_in, "tokens_out": tokens_out,
                    "duration_ms": duration_ms, "compaction_event": compaction_event,
                    "created_at": time.time(),
                }])
            except Exception as e:
                print(f"[BigQuery Warning] Failed to log turn: {e}")

    def log_tool_call(self, run_id: str, turn_idx: int, tool: str,
                      args: Dict[str, Any], is_error: bool,
                      guard_event: Optional[str] = None):
        """Logs tool invocation to SQLite and BigQuery."""
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

        if self._bq_client and self.db_path == settings.sqlite_db_path:
            try:
                table_id = f"{self.project_id}.{self.dataset_id}.{settings.bq_tool_calls_table}"
                self._bq_client.insert_rows_json(table_id, [{
                    "run_id": run_id, "turn_idx": turn_idx, "tool": tool,
                    "args_hash": args_hash, "target_path": target_path,
                    "is_error": is_error, "guard_event": guard_event,
                    "created_at": time.time(),
                }])
            except Exception as e:
                print(f"[BigQuery Warning] Failed to log tool call: {e}")

    # ── Query Methods (AgentTrace) ───────────────────────────────────

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Queries analytical views for dashboard charts (BigQuery with SQLite fallback)."""
        if self._bq_client and self.db_path == settings.sqlite_db_path:
            try:
                dataset_ref = f"{self.project_id}.{self.dataset_id}"
                q_overall = f"SELECT COUNT(*) as total, SUM(CAST(resolved AS INT64)) as passed, AVG(total_cost_usd) as avg_cost FROM `{dataset_ref}.{settings.bq_runs_table}`"
                df_overall = list(self._bq_client.query(q_overall).result())
                total_runs = df_overall[0]["total"] or 0
                passed_runs = df_overall[0]["passed"] or 0
                avg_cost = df_overall[0]["avg_cost"] or 0.0

                comparisons = [dict(r) for r in self._bq_client.query(f"SELECT * FROM `{dataset_ref}.v_harness_comparison_summary`").result()]
                failures = [dict(r) for r in self._bq_client.query(f"SELECT * FROM `{dataset_ref}.v_failure_stage_attribution`").result()]
                phases = [dict(r) for r in self._bq_client.query(f"SELECT * FROM `{dataset_ref}.v_phase_breakdown`").result()]
                tools = [dict(r) for r in self._bq_client.query(f"SELECT * FROM `{dataset_ref}.v_tool_usage`").result()]
                costs = [dict(r) for r in self._bq_client.query(f"SELECT * FROM `{dataset_ref}.v_cost_by_model`").result()]

                return {
                    "total_runs": total_runs,
                    "pass_rate": (passed_runs / total_runs) if total_runs > 0 else 0.0,
                    "avg_cost_usd": avg_cost,
                    "comparisons": comparisons,
                    "failures": failures,
                    "phase_breakdown": phases,
                    "tool_usage": tools,
                    "cost_by_model": costs,
                    "data_source": "bigquery",
                }
            except Exception as e:
                print(f"[BigQuery Warning] Query failed, using SQLite fallback: {e}")

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

        # Phase breakdown
        cur.execute("SELECT * FROM v_phase_breakdown")
        phases = [dict(r) for r in cur.fetchall()]

        # Tool usage
        cur.execute("SELECT * FROM v_tool_usage")
        tools = [dict(r) for r in cur.fetchall()]

        # Cost by model
        cur.execute("SELECT * FROM v_cost_by_model")
        costs = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {
            "total_runs": total_runs,
            "pass_rate": (passed_runs / total_runs) if total_runs > 0 else 0.0,
            "avg_cost_usd": avg_cost,
            "comparisons": comparisons,
            "failures": failures,
            "phase_breakdown": phases,
            "tool_usage": tools,
            "cost_by_model": costs,
            "data_source": "sqlite",
        }

    def get_run_analytics(self, run_id: str) -> Dict[str, Any]:
        """Returns per-run analytics: phase breakdown, tool usage, cost."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Turns for this run
        cur.execute("SELECT * FROM turns WHERE run_id = ? ORDER BY turn_idx", (run_id,))
        turns = [dict(r) for r in cur.fetchall()]

        # Tool calls for this run
        cur.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY turn_idx", (run_id,))
        tool_calls = [dict(r) for r in cur.fetchall()]

        # Judgment if failed
        cur.execute("SELECT * FROM judgments WHERE run_id = ?", (run_id,))
        judgment_row = cur.fetchone()
        judgment = dict(judgment_row) if judgment_row else None

        conn.close()
        return {
            "run_id": run_id,
            "turns": turns,
            "tool_calls": tool_calls,
            "judgment": judgment,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _classify_failure_stage(stop_reason: str) -> str:
        """Maps stop_reason to AgentTrace failure stage taxonomy."""
        mapping = {
            "CONTEXT_OVERFLOW": "verification",
            "CIRCUIT_BREAKER_STUCK": "line_localization",
            "CIRCUIT_BREAKER_EMPTY_PATCH": "patch_implementation",
            "MAX_TURNS": "verification",
            "ERROR": "execution_error",
            "CANCELLED": "cancelled",
        }
        return mapping.get(stop_reason, "patch_implementation")
