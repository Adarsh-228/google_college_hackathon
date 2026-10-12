import os
import shutil
import tempfile
import uuid
from typing import Dict, Any, Optional
from packages.harness_core.runner import run_agent_task
from api.firestore_sync import FirestoreSync
from api.bigquery_logger import BigQueryLogger

class WorkspaceSandbox:
    """
    Sandboxed Task Execution Environment.
    Clones testbed to an isolated directory, drives run_agent_task,
    syncs real-time events to Firestore, and logs analytical traces to BigQuery.
    """

    def __init__(self, testbed_root: str, firestore: FirestoreSync, bq_logger: BigQueryLogger):
        self.testbed_root = os.path.realpath(testbed_root)
        self.firestore = firestore
        self.bq_logger = bq_logger

    def execute_run(
        self,
        task_id: str,
        task_prompt: str,
        run_id: Optional[str] = None,
        model_id: str = "gemini-2.5-flash",
        harness_config: Optional[Dict[str, Any]] = None,
        client: Any = None,
    ) -> Dict[str, Any]:
        """Runs the agent inside an isolated workspace clone."""
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        source_dir = os.path.join(self.testbed_root, task_id)
        if not os.path.exists(source_dir):
            raise FileNotFoundError(f"Task directory '{task_id}' not found at {source_dir}")

        # Create isolated temporary workspace
        temp_dir = tempfile.mkdtemp(prefix=f"harness_{task_id}_")
        shutil.copytree(source_dir, temp_dir, dirs_exist_ok=True)

        config_dict = harness_config or {}
        self.firestore.create_run(run_id, {
            "taskId": task_id,
            "modelId": model_id,
            "harnessConfig": config_dict,
            "workspace": temp_dir,
        })

        turn_events = []
        final_summary = {}

        try:
            generator = run_agent_task(
                workspace_path=temp_dir,
                task_prompt=task_prompt,
                model_id=model_id,
                harness_config=config_dict,
                client=client,
            )

            for event in generator:
                turn_events.append(event)
                # Stream immediately to Firestore
                self.firestore.append_event(run_id, event)
                
                # Update top-level run state
                turn_idx = event.get("turn_idx", 1)
                event_type = event.get("type", "")
                data = event.get("data", {})
                
                if event_type == "PLAN_UPDATE":
                    self.firestore.update_run_state(run_id, {"currentPlan": data.get("current_plan")})
                elif event_type == "COMPACTION":
                    self.firestore.update_run_state(run_id, {"lastCompaction": data.get("badge")})

            # Grab final returned dict
            final_summary = getattr(generator, "value", {}) or {}

        except StopIteration as si:
            final_summary = si.value or {}
        except Exception as e:
            final_summary = {
                "resolved": False,
                "stop_reason": "ERROR",
                "error_message": str(e),
                "total_turns": len(turn_events),
                "total_cost_usd": 0.0,
            }
        finally:
            # Clean up sandbox temp dir
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        # Enrich final summary
        complete_run_record = {
            "run_id": run_id,
            "task_id": task_id,
            "model": model_id,
            "tool_mode": config_dict.get("tool_mode", "predefined"),
            "planning": config_dict.get("enable_planning", True),
            "context_tier": config_dict.get("context_tier", "T4"),
            "budget_cap": config_dict.get("budget_cap", 32768),
            "resolved": final_summary.get("resolved", False),
            "stop_reason": final_summary.get("stop_reason", "UNKNOWN"),
            "total_turns": final_summary.get("total_turns", len(turn_events)),
            "total_cost_usd": final_summary.get("total_cost_usd", 0.0),
            "tokens_in_uncached": final_summary.get("tokens_in_uncached", 0),
            "tokens_in_cached": final_summary.get("tokens_in_cached", 0),
            "tokens_out": final_summary.get("tokens_out", 0),
            "m1_count": final_summary.get("m1_count", 0),
            "m3_count": final_summary.get("m3_count", 0),
            "re_patch_count": final_summary.get("re_patch_count", 0),
        }

        # Update Firestore status
        self.firestore.update_run_state(run_id, {
            "status": "RESOLVED" if complete_run_record["resolved"] else complete_run_record["stop_reason"],
            "summary": complete_run_record,
        })

        # Append to BigQuery Data Warehouse
        self.bq_logger.log_run(complete_run_record)

        return complete_run_record
