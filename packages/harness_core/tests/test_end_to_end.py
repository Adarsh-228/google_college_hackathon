"""End-to-end integration tests for complete agent execution workflow."""

import pytest
from pathlib import Path
from packages.harness_core.agent.orchestrator import HarnessEngine
from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import ExecutionStatus, HarnessMode
from packages.harness_core.contracts.events import AgentEvent
from packages.harness_core.execution.runner import MockExecutionRunner
from packages.harness_core.providers.base import LLMResponse, LLMToolCall
from packages.harness_core.providers.mock_provider import MockLLMProvider


@pytest.mark.asyncio
async def test_end_to_end_successful_task_flow(tmp_path: Path):
    """Test full vertical execution cycle from task prompt to verified completion."""
    # 1. Setup mock LLM simulating agent reasoning and tool usage
    mock_llm = MockLLMProvider()

    # Turn 1: Model calls write_file to create calc.py
    mock_llm.queue_tool_call(
        tool_name="write_file",
        arguments={
            "file_path": "calc.py",
            "content": "def add(a: int, b: int) -> int:\n    return a + b\n",
        },
        thought="I will write the calculator function to calc.py.",
    )

    # Turn 2: Model inspects file
    mock_llm.queue_tool_call(
        tool_name="read_file",
        arguments={"file_path": "calc.py"},
        thought="I will inspect the created file to verify content.",
    )

    # Turn 3: Final completion message
    mock_llm.queue_text_response(
        "Successfully implemented and verified the calculator function in calc.py."
    )

    runner = MockExecutionRunner(default_stdout="pytest: 1 passed", default_exit_code=0)
    config = EngineConfig(workspace_base_dir=str(tmp_path))

    engine = HarnessEngine(config=config, provider=mock_llm, runner=runner)

    events_received = []

    async def log_event(evt: AgentEvent):
        events_received.append(evt)

    engine.register_event_handler(log_event)

    # 2. Run Task
    response = await engine.run_task(
        task="Create a Python calculator function in calc.py",
        workspace_dir=str(tmp_path / "ws_e2e"),
        mode=HarnessMode.HYBRID,
    )

    # 3. Assertions
    assert response.status == ExecutionStatus.COMPLETED
    assert "calc.py" in response.report.files_created
    assert response.metrics.tool_call_count == 2
    assert response.metrics.total_tokens > 0

    # Verify real file on disk in workspace
    created_file = tmp_path / "ws_e2e" / "calc.py"
    assert created_file.exists()
    assert "def add" in created_file.read_text(encoding="utf-8")

    # Verify telemetry stream
    event_types = [e.event_type.value for e in events_received]
    assert "session_started" in event_types
    assert "task_analyzed" in event_types
    assert "model_selected" in event_types
    assert "plan_created" in event_types
    assert "tool_call_started" in event_types
    assert "tool_call_completed" in event_types
    assert "verification_completed" in event_types
    assert "session_completed" in event_types


@pytest.mark.asyncio
async def test_end_to_end_loop_detection_stalls(tmp_path: Path):
    """Test that consecutive identical failing calls terminate execution with STALLED status."""
    mock_llm = MockLLMProvider()

    # Queue 10 identical failing calls
    for _ in range(10):
        mock_llm.queue_tool_call(
            tool_name="read_file",
            arguments={"file_path": "nonexistent_loop_file.txt"},
            thought="Retrying read...",
        )

    runner = MockExecutionRunner()
    config = EngineConfig(
        workspace_base_dir=str(tmp_path),
        guard_max_loop_attempts=3,
        guard_max_failed_repeats=4,
    )

    engine = HarnessEngine(config=config, provider=mock_llm, runner=runner)

    response = await engine.run_task(
        task="Attempt reading a missing file in a loop",
        workspace_dir=str(tmp_path / "ws_loop"),
    )

    assert response.status == ExecutionStatus.STALLED
    assert "Loop Protection" in str(response.error)
