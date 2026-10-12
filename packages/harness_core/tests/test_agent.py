"""Tests for agent state, analyzer, and planner."""

import pytest
from packages.harness_core.agent.planner import TaskPlanner
from packages.harness_core.agent.state import AgentState
from packages.harness_core.agent.task_analyzer import TaskAnalyzer
from packages.harness_core.contracts.enums import ExecutionStatus, HarnessMode


def test_task_analyzer_file_extraction():
    task_str = "Please update server.py and create tests in test_server.py to add FastAPI endpoint"
    analyzed = TaskAnalyzer.analyze(task_str)

    assert "python" in analyzed.target_languages
    assert "server.py" in analyzed.referenced_files
    assert "test_server.py" in analyzed.referenced_files
    assert analyzed.is_rest_api is True


def test_task_planner_step_generation():
    analyzed = TaskAnalyzer.analyze("Create api.py")
    steps = TaskPlanner.create_initial_plan(analyzed, HarnessMode.HYBRID)

    assert len(steps) == 3
    assert steps[0].description.startswith("Inspect")
    assert steps[0].tool_suggested == "list_files"
    assert steps[1].tool_suggested == "write_file"


def test_agent_state_initialization():
    state = AgentState(
        session_id="s_123",
        task_id="t_456",
        user_task="Build calculator",
    )
    assert state.execution_status == ExecutionStatus.PENDING
    assert len(state.conversation_history) == 0
    assert len(state.files_created) == 0
