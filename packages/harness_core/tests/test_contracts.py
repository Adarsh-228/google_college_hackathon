"""Tests for shared integration contracts and schemas."""

import pytest
from packages.harness_core.contracts.enums import (
    ContextStrategy,
    EventType,
    ExecutionStatus,
    HarnessMode,
    ProviderType,
)
from packages.harness_core.contracts.events import AgentEvent
from packages.harness_core.contracts.requests import (
    AgentExecutionRequest,
    ToolExecutionRequest,
)
from packages.harness_core.contracts.responses import (
    AgentExecutionResponse,
    ContextStatistics,
    DiagnosticResult,
    ExecutionReport,
    PerformanceMetrics,
    TaskPlanStep,
    ToolExecutionResult,
)


def test_agent_execution_request_defaults():
    req = AgentExecutionRequest(task="Implement calculator API")
    assert req.task == "Implement calculator API"
    assert req.harness_mode is None
    assert req.context_strategy is None
    assert req.timeout_seconds == 300
    assert req.max_tool_calls == 30


def test_tool_execution_result_serialization():
    diag = DiagnosticResult(
        file_path="src/main.py",
        line_number=12,
        error_type="SyntaxError",
        message="invalid syntax",
        severity="error",
        source="ast_syntax",
    )
    result = ToolExecutionResult(
        tool_name="edit_file",
        success=True,
        output="File edited",
        duration_ms=45.2,
        files_touched=["src/main.py"],
        diagnostics=[diag],
    )
    data = result.model_dump()
    assert data["tool_name"] == "edit_file"
    assert data["success"] is True
    assert len(data["diagnostics"]) == 1
    assert data["diagnostics"][0]["line_number"] == 12


def test_agent_event_creation():
    event = AgentEvent(
        session_id="sess_123",
        task_id="task_456",
        event_type=EventType.TOOL_CALL_COMPLETED,
        component="agent_guard",
        status=ExecutionStatus.RUNNING,
        payload={"tool": "read_file"},
    )
    assert event.event_id.startswith("evt_")
    assert event.session_id == "sess_123"
    assert event.event_type == EventType.TOOL_CALL_COMPLETED


def test_execution_report_structure():
    metrics = PerformanceMetrics(
        input_tokens=1500,
        output_tokens=300,
        total_tokens=1800,
        estimated_cost_usd=0.0003,
        tool_call_count=5,
        final_status=ExecutionStatus.COMPLETED,
    )
    step = TaskPlanStep(
        step_number=1,
        description="Inspect files",
        tool_suggested="list_files",
        status="COMPLETED",
    )
    report = ExecutionReport(
        session_id="sess_abc",
        task="Write test",
        status=ExecutionStatus.COMPLETED,
        harness_mode=HarnessMode.HYBRID,
        context_strategy=ContextStrategy.T4_STAGED,
        plan=[step],
        completed_steps=["Inspect files"],
        files_created=["test_sample.py"],
        files_modified=[],
        errors_encountered=[],
        metrics=metrics,
        summary="Done",
    )
    assert report.status == ExecutionStatus.COMPLETED
    assert len(report.plan) == 1
    assert report.metrics.total_tokens == 1800
