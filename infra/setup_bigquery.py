"""
Automated BigQuery Provisioning Script for Harness Kit
Creates the dataset, 4 core telemetry tables, and 5 AgentTrace analytical views.

Usage:
    python infra/setup_bigquery.py
    python infra/setup_bigquery.py --project YOUR_PROJECT_ID
    python infra/setup_bigquery.py --credentials path/to/gcp-key.json
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.config import settings

def main():
    parser = argparse.ArgumentParser(description="Provision Harness Kit BigQuery tables and views.")
    parser.add_argument("--project", default=settings.google_cloud_project, help="Google Cloud Project ID")
    parser.add_argument("--credentials", default=None, help="Path to service account JSON key file")
    parser.add_argument("--region", default=settings.google_cloud_region, help="Dataset location region (default: us-central1)")
    args = parser.parse_args()

    if args.credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(args.credentials)
        print(f"[Setup] Using credentials from: {args.credentials}")

    project_id = args.project
    print(f"[Setup] Connecting to Google Cloud BigQuery for project: {project_id}...")

    try:
        from google.cloud import bigquery
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        print("[Error] 'google-cloud-bigquery' is not installed. Run: pip install google-cloud-bigquery")
        sys.exit(1)

    try:
        client = bigquery.Client(project=project_id)
        print(f"[OK] Authenticated successfully with BigQuery client for project '{project_id}'")
    except DefaultCredentialsError:
        print("\n[Auth Error] No GCP credentials found.")
        print("To authenticate:")
        print("  1. In Cloud Shell: Run this script directly (credentials are automatic).")
        print("  2. Locally with gcloud: Run 'gcloud auth application-default login'")
        print("  3. With service account key: Run 'python infra/setup_bigquery.py --credentials ./gcp-key.json'\n")
        sys.exit(1)
    except Exception as e:
        print(f"[Error] Failed to connect to BigQuery: {e}")
        sys.exit(1)

    dataset_id = settings.bq_dataset
    dataset_ref = f"{project_id}.{dataset_id}"

    # 1. Create dataset
    print(f"\n[1/4] Ensuring dataset '{dataset_ref}' exists...")
    try:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = args.region
        client.create_dataset(dataset, exists_ok=True)
        print(f"  [OK] Dataset '{dataset_id}' ready (location: {args.region})")
    except Exception as e:
        print(f"  [FAILED] Failed to create dataset: {e}")
        sys.exit(1)

    # 2. Tables Schema Definition
    print(f"\n[2/4] Ensuring 4 telemetry tables exist...")

    tables_definitions = {
        settings.bq_runs_table: [
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
            bigquery.SchemaField("is_error", "BOOLEAN"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ],
        settings.bq_turns_table: [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("turn_idx", "INTEGER"),
            bigquery.SchemaField("phase", "STRING"),
            bigquery.SchemaField("tool", "STRING"),
            bigquery.SchemaField("tokens_in", "INTEGER"),
            bigquery.SchemaField("tokens_out", "INTEGER"),
            bigquery.SchemaField("duration_ms", "FLOAT"),
            bigquery.SchemaField("compaction_event", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ],
        settings.bq_tool_calls_table: [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("turn_idx", "INTEGER"),
            bigquery.SchemaField("tool", "STRING"),
            bigquery.SchemaField("args_hash", "STRING"),
            bigquery.SchemaField("target_path", "STRING"),
            bigquery.SchemaField("is_error", "BOOLEAN"),
            bigquery.SchemaField("guard_event", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ],
        settings.bq_judgments_table: [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("failure_stage", "STRING"),
            bigquery.SchemaField("reason", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    }

    for table_name, schema in tables_definitions.items():
        table_id = f"{dataset_ref}.{table_name}"
        try:
            tbl = bigquery.Table(table_id, schema=schema)
            client.create_table(tbl, exists_ok=True)
            print(f"  [OK] Table '{table_name}' verified")
        except Exception as e:
            print(f"  [FAILED] Table '{table_name}' creation error: {e}")

    # 3. Create Views
    print(f"\n[3/4] Creating 5 AgentTrace Analytical Views...")
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
            client.create_table(view, exists_ok=True)
            print(f"  [OK] View '{view_name}' verified")
        except Exception as e:
            print(f"  [FAILED] View '{view_name}' creation error: {e}")

    print("\n[4/4] Verification check...")
    try:
        tables = list(client.list_tables(dataset_ref))
        print(f"  [OK] Total items in dataset '{dataset_id}': {len(tables)}")
        for t in tables:
            print(f"    - {t.table_id} ({t.table_type})")
        print("\n[SUCCESS] BigQuery setup completed successfully!")
    except Exception as e:
        print(f"  Warning: list_tables check: {e}")

if __name__ == "__main__":
    main()
