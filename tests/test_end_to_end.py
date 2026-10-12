import os
import shutil
import tempfile
import pytest
from packages.harness_core.runner import run_agent_task
from packages.harness_core.providers import MockLLMClient

def test_full_react_agent_loop_resolution():
    workspace_root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
    task_source = os.path.join(workspace_root, "testbeds", "task_01_off_by_one")

    with tempfile.TemporaryDirectory() as temp_dir:
        shutil.copytree(task_source, temp_dir, dirs_exist_ok=True)

        mock_client = MockLLMClient(scenario="task_01_off_by_one")
        generator = run_agent_task(
            workspace_path=temp_dir,
            task_prompt="Fix the off-by-one pagination bug in app.py",
            model_id="gemini-2.5-flash",
            harness_config={
                "context_tier": "T4",
                "budget_cap": 32768,
                "enable_rbw": True,
                "enable_lint": True,
                "enable_planning": True,
            },
            client=mock_client,
            max_steps=10,
        )

        events = []
        for evt in generator:
            events.append(evt)

        # Confirm turn events were yielded
        event_types = [e["type"] for e in events]
        assert "TURN_START" in event_types
        assert "TOOL_CALL" in event_types
        assert "TOOL_RESULT" in event_types

        # Check final outcome
        final_run_finish = [e for e in events if e["type"] == "RUN_FINISH"]
        assert len(final_run_finish) > 0
        assert final_run_finish[0]["data"]["resolved"] is True
