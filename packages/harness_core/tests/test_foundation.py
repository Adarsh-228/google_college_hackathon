"""Comprehensive tests for the HarnessX foundation layer."""

import os
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from packages.harness_core import (
    AgentEvent,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentState,
    CircuitBreakerError,
    ConfigurationError,
    ContextOverflowError,
    ContextStatistics,
    ContextStrategy,
    DiagnosticResult,
    EngineConfig,
    EventType,
    ExecutionReport,
    ExecutionStatus,
    ExecutionTimeoutError,
    GuardViolationError,
    HarnessError,
    HarnessMode,
    LoopDetectedError,
    ModelAuthenticationError,
    ModelRateLimitError,
    PathTraversalError,
    PerformanceMetrics,
    ProviderError,
    ProviderType,
    SecurityViolationError,
    SessionNotFoundError,
    StaleFileEditError,
    TaskAbortedError,
    TaskAnalysisRequest,
    TaskComplexity,
    TaskPlanStep,
    ToolExecutionError,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolPermission,
    WorkspaceError,
)
from packages.harness_core.config.harness_config import HarnessConfiguration
from packages.harness_core.config.model_config import MODEL_CATALOG, get_model_profile


# ==============================================================================
# 1. Configuration Management Tests
# ==============================================================================

def test_engine_config_defaults():
    cfg = EngineConfig()
    assert cfg.use_vertex is False
    assert cfg.gemini_api_key is None
    assert cfg.google_cloud_project is None
    assert cfg.gcp_region == "us-central1"
    assert cfg.default_harness_mode == HarnessMode.HYBRID
    assert cfg.context_soft_threshold == 0.60
    assert cfg.context_hard_threshold == 0.85
    assert cfg.context_window_limit == 128000
    assert cfg.guard_max_tool_calls == 30
    assert cfg.workspace_base_dir == "./workspaces"


def test_engine_config_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ai-studio-secret-key")
    monkeypatch.setenv("USE_VERTEX", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-gcp-proj")
    monkeypatch.setenv("GCP_REGION", "europe-west1")
    monkeypatch.setenv("HARNESS_DEFAULT_MODE", "DIRECT")
    monkeypatch.setenv("CONTEXT_SOFT_THRESHOLD", "0.55")
    monkeypatch.setenv("GUARD_MAX_TOOL_CALLS", "45")

    cfg = EngineConfig.from_env()
    assert cfg.gemini_api_key == "ai-studio-secret-key"
    assert cfg.use_vertex is True
    assert cfg.google_cloud_project == "test-gcp-proj"
    assert cfg.gcp_region == "europe-west1"
    assert cfg.default_harness_mode == HarnessMode.DIRECT
    assert cfg.context_soft_threshold == 0.55
    assert cfg.guard_max_tool_calls == 45


def test_engine_config_secret_masking():
    cfg = EngineConfig(
        gemini_api_key="secret-api-key-123",
        google_application_credentials="/path/to/creds.json",
    )
    sanitized = cfg.sanitized_dict()
    assert sanitized["gemini_api_key"] == "***MASKED***"
    assert sanitized["google_application_credentials"] == "***MASKED***"
    assert cfg.gemini_api_key == "secret-api-key-123"  # Original remains unmutated


def test_model_catalog_and_profiles():
    profile = get_model_profile("gemini-2.5-flash")
    assert profile.model_name == "gemini-2.5-flash"
    assert profile.context_window >= 1000000
    assert profile.cost_per_1k_input_usd > 0.0

    fallback = get_model_profile("custom-unknown-model")
    assert fallback.model_name == "custom-unknown-model"
    assert fallback.context_window == 128000


# ==============================================================================
# 2. Pydantic Contracts & Schema Tests
# ==============================================================================

def test_agent_execution_request_validation():
    # Valid
    req = AgentExecutionRequest(
        task="Create a Python server",
        harness_mode=HarnessMode.GUIDED,
        context_strategy=ContextStrategy.T4_STAGED,
    )
    assert req.task == "Create a Python server"
    assert req.harness_mode == HarnessMode.GUIDED

    # Invalid (missing required task field)
    with pytest.raises(ValidationError):
        AgentExecutionRequest()


def test_tool_execution_request_and_result():
    req = ToolExecutionRequest(
        tool_name="read_file",
        arguments={"file_path": "README.md"},
        session_id="sess_123",
        step_index=2,
    )
    assert req.tool_name == "read_file"
    assert req.arguments["file_path"] == "README.md"

    diag = DiagnosticResult(
        file_path="main.py",
        line_number=10,
        error_type="SyntaxError",
        message="invalid syntax",
        severity="error",
        source="ast_syntax",
    )

    res = ToolExecutionResult(
        tool_name="edit_file",
        success=False,
        output="",
        error="Syntax error in file",
        duration_ms=12.4,
        files_touched=["main.py"],
        diagnostics=[diag],
    )
    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].error_type == "SyntaxError"


def test_context_statistics_model():
    stats = ContextStatistics(
        total_tokens=15000,
        window_limit=128000,
        utilization_pct=0.117,
        elided_count=2,
        summarized_count=1,
        tokens_saved_estimate=4500,
        is_estimated=True,
    )
    assert stats.total_tokens == 15000
    assert stats.tokens_saved_estimate == 4500
    assert stats.is_estimated is True


def test_agent_state_model():
    state = AgentState(
        session_id="s_test_1",
        task_id="t_test_1",
        user_task="Create CLI tool",
        execution_status=ExecutionStatus.RUNNING,
    )
    assert state.session_id == "s_test_1"
    assert state.execution_status == ExecutionStatus.RUNNING
    assert state.harness_mode == HarnessMode.HYBRID
    assert state.context_strategy == ContextStrategy.T4_STAGED
    assert len(state.conversation_history) == 0


def test_agent_event_model():
    evt = AgentEvent(
        session_id="s_event_test",
        task_id="t_event_test",
        event_type=EventType.TOOL_CALL_STARTED,
        component="agent_guard",
        status=ExecutionStatus.RUNNING,
        payload={"tool_name": "list_files"},
    )
    assert evt.event_id.startswith("evt_")
    assert evt.event_type == EventType.TOOL_CALL_STARTED
    assert isinstance(evt.timestamp, datetime)
    assert evt.payload["tool_name"] == "list_files"


def test_execution_report_and_metrics():
    metrics = PerformanceMetrics(
        input_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        estimated_cost_usd=0.00018,
        tool_call_count=3,
        final_status=ExecutionStatus.COMPLETED,
    )
    step = TaskPlanStep(
        step_number=1,
        description="Inspect files",
        tool_suggested="list_files",
        status="COMPLETED",
    )
    report = ExecutionReport(
        session_id="s_rep_1",
        task="Test task",
        status=ExecutionStatus.COMPLETED,
        harness_mode=HarnessMode.HYBRID,
        context_strategy=ContextStrategy.T4_STAGED,
        plan=[step],
        completed_steps=["Inspect files"],
        files_created=["out.py"],
        files_modified=[],
        errors_encountered=[],
        metrics=metrics,
        summary="Completed successfully.",
    )
    resp = AgentExecutionResponse(
        session_id="s_rep_1",
        task="Test task",
        status=ExecutionStatus.COMPLETED,
        report=report,
        metrics=metrics,
        final_result="Output ready.",
    )
    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.report.summary == "Completed successfully."
    assert resp.metrics.total_tokens == 1500


# ==============================================================================
# 3. Common Exceptions Hierarchy Tests
# ==============================================================================

def test_exception_hierarchy():
    # Base
    base_err = HarnessError("base failure", details={"key": "val"})
    assert isinstance(base_err, Exception)
    assert base_err.details["key"] == "val"

    # Configuration error
    cfg_err = ConfigurationError("missing key")
    assert isinstance(cfg_err, HarnessError)

    # Provider errors
    auth_err = ModelAuthenticationError("bad key")
    assert isinstance(auth_err, ProviderError)
    assert isinstance(auth_err, HarnessError)

    rate_err = ModelRateLimitError("quota exceeded")
    assert isinstance(rate_err, ProviderError)

    # Guard errors
    stale_err = StaleFileEditError("file modified on disk")
    assert isinstance(stale_err, GuardViolationError)
    assert isinstance(stale_err, HarnessError)

    sec_err = SecurityViolationError("forbidden command")
    assert isinstance(sec_err, GuardViolationError)

    loop_err = LoopDetectedError("loop stalled")
    assert isinstance(loop_err, GuardViolationError)

    cb_err = CircuitBreakerError("budget exhausted")
    assert isinstance(cb_err, GuardViolationError)

    # Workspace & path errors
    path_err = PathTraversalError("attempted escape")
    assert isinstance(path_err, WorkspaceError)
    assert isinstance(path_err, SecurityViolationError)
    assert isinstance(path_err, HarnessError)
