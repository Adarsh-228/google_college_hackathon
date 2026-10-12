"""Comprehensive unit tests for the AgentGuard safety and reliability layer."""

import pytest
from pathlib import Path

from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import HarnessMode, ToolPermission
from packages.harness_core.contracts.requests import ToolExecutionRequest
from packages.harness_core.exceptions.errors import (
    CircuitBreakerError,
    ExecutionTimeoutError,
    LoopDetectedError,
    PathTraversalError,
    TaskAbortedError,
)
from packages.harness_core.execution.runner import MockExecutionRunner
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.guard.circuit_breaker import CircuitBreaker, ExecutionLimitManager
from packages.harness_core.guard.diagnostics import CodeDiagnosticsGuard, PostEditDiagnostics
from packages.harness_core.guard.file_integrity import (
    FileIntegrityGuard,
    FileStateValidator,
    ReadBeforeWriteValidator,
)
from packages.harness_core.guard.interceptor import AgentGuard
from packages.harness_core.guard.loop_detector import LoopDetector, RepeatedCallDetector
from packages.harness_core.guard.permission_manager import PermissionManager
from packages.harness_core.guard.workspace_protection import WorkspaceProtection
from packages.harness_core.tools.base import ToolContext
from packages.harness_core.tools.file_tools import ReadFileTool, WriteFileTool
from packages.harness_core.tools.terminal_tools import RunTerminalCommandTool


# ==============================================================================
# 1. FileStateValidator Tests (Content Hashing & Drift Detection)
# ==============================================================================

def test_file_state_validator_hash_and_drift(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    validator = FileStateValidator(ws)

    f = tmp_path / "code.py"
    f.write_text("print('v1')", encoding="utf-8")

    # Compute baseline hash
    h1 = validator.compute_file_hash("code.py")
    assert h1 is not None
    assert validator.has_file_changed("code.py", h1) is False

    # Simulate modification on disk
    f.write_text("print('v2 modified')", encoding="utf-8")
    assert validator.has_file_changed("code.py", h1) is True


# ==============================================================================
# 2. ReadBeforeWriteValidator Tests
# ==============================================================================

def test_read_before_write_enforcement(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    validator = ReadBeforeWriteValidator(ws)

    # 1. New file creation: allowed without prior read
    ok_new, err_new = validator.validate_pre_modification("brand_new.py")
    assert ok_new is True
    assert err_new is None

    # 2. Existing file created on disk: modifying without read is blocked
    existing = tmp_path / "existing.py"
    existing.write_text("data = 1", encoding="utf-8")

    ok_uninspected, err_uninspected = validator.validate_pre_modification("existing.py")
    assert ok_uninspected is False
    assert "has not been inspected" in err_uninspected

    # 3. Read recorded: now permitted
    validator.record_read("existing.py")
    assert validator.is_read_recorded("existing.py") is True

    ok_read, err_read = validator.validate_pre_modification("existing.py")
    assert ok_read is True
    assert err_read is None

    # 4. External modification between read and write: detected as stale edit
    existing.write_text("data = 2 # changed externally", encoding="utf-8")
    ok_stale, err_stale = validator.validate_pre_modification("existing.py")
    assert ok_stale is False
    assert "Stale Edit Detected" in err_stale


# ==============================================================================
# 3. PostEditDiagnostics Tests (Python Syntax & AST Checks)
# ==============================================================================

def test_post_edit_diagnostics_syntax_error(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    diagnostics = PostEditDiagnostics(ws, enable_ruff=False)

    bad_syntax_file = tmp_path / "invalid_syntax.py"
    bad_syntax_file.write_text("def missing_colon()\n    return 10\n", encoding="utf-8")

    issues = diagnostics.check_file("invalid_syntax.py")
    assert len(issues) == 1
    assert issues[0].error_type == "SyntaxError"
    assert issues[0].line_number == 1
    assert issues[0].severity == "error"
    assert issues[0].source == "ast_syntax"


def test_post_edit_diagnostics_clean_file(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    diagnostics = PostEditDiagnostics(ws, enable_ruff=False)

    clean_file = tmp_path / "valid.py"
    clean_file.write_text("def valid_func():\n    return 42\n", encoding="utf-8")

    issues = diagnostics.check_file("valid.py")
    assert len(issues) == 0


# ==============================================================================
# 4. RepeatedCallDetector Tests (Loops, Warnings, Stalls)
# ==============================================================================

def test_repeated_call_detector_thresholds():
    detector = RepeatedCallDetector(warning_threshold=3, stall_threshold=5)

    # 1. Distinct calls
    r1 = detector.record_call("read_file", {"file_path": "a.py"}, success=True)
    assert r1.is_repeated is False
    assert r1.is_warning is False

    # 2. Consecutive identical calls up to warning threshold
    r2 = detector.record_call("read_file", {"file_path": "a.py"}, success=True)
    assert r2.is_repeated is True
    assert r2.is_warning is False

    r3 = detector.record_call("read_file", {"file_path": "a.py"}, success=True)
    assert r3.is_warning is True
    assert "Loop Warning" in r3.message

    # 3. Repeated identical failures triggering stall
    detector.record_call("edit_file", {"file_path": "err.py"}, success=False)
    detector.record_call("edit_file", {"file_path": "err.py"}, success=False)
    detector.record_call("edit_file", {"file_path": "err.py"}, success=False)
    detector.record_call("edit_file", {"file_path": "err.py"}, success=False)

    with pytest.raises(LoopDetectedError) as exc_info:
        detector.record_call("edit_file", {"file_path": "err.py"}, success=False)
    assert "Loop Protection" in str(exc_info.value)


# ==============================================================================
# 5. ExecutionLimitManager Tests (Budgets, Timeouts, Retries)
# ==============================================================================

def test_execution_limit_manager_tool_calls():
    manager = ExecutionLimitManager(max_tool_calls=2)
    manager.record_tool_call()
    manager.record_tool_call()

    # 3rd call exceeds budget
    with pytest.raises(CircuitBreakerError) as exc_info:
        manager.record_tool_call()
    assert "Tool call budget exhausted" in str(exc_info.value)


def test_execution_limit_manager_iterations():
    manager = ExecutionLimitManager(max_iterations=3)
    manager.record_iteration()
    manager.record_iteration()
    manager.record_iteration()

    with pytest.raises(CircuitBreakerError) as exc_info:
        manager.record_iteration()
    assert "Maximum iterations exceeded" in str(exc_info.value)


def test_execution_limit_manager_cancellation():
    manager = ExecutionLimitManager()
    manager.cancel()

    with pytest.raises(TaskAbortedError) as exc_info:
        manager.check_limits()
    assert "cancelled" in str(exc_info.value)


# ==============================================================================
# 6. WorkspaceProtection Tests (Boundary Enforcement)
# ==============================================================================

def test_workspace_protection_boundary_checks(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    protection = WorkspaceProtection(ws)

    # Safe inside
    ok, err = protection.validate_path("sub/file.txt")
    assert ok is True
    assert err is None

    # Escape attempt: relative
    ok_esc, err_esc = protection.validate_path("../../etc/passwd")
    assert ok_esc is False
    assert "Security Violation" in err_esc

    # Escape attempt: parent
    ok_parent, err_parent = protection.validate_path("../outside.txt")
    assert ok_parent is False
    assert "Security Violation" in err_parent


# ==============================================================================
# 7. PermissionManager Tests
# ==============================================================================

def test_permission_manager_guided_vs_hybrid():
    pm = PermissionManager()

    # In GUIDED mode: terminal is blocked
    ok_term, err_term = pm.check_permission(
        ToolPermission.EXECUTE_TERMINAL, harness_mode=HarnessMode.GUIDED
    )
    assert ok_term is False
    assert "Terminal execution is disabled in GUIDED mode" in err_term

    # In HYBRID mode: terminal is allowed
    ok_hybrid, err_hybrid = pm.check_permission(
        ToolPermission.EXECUTE_TERMINAL, harness_mode=HarnessMode.HYBRID
    )
    assert ok_hybrid is True
    assert err_hybrid is None


def test_permission_manager_read_only_mode():
    pm = PermissionManager(read_only_mode=True)

    ok_read, _ = pm.check_permission(ToolPermission.READ_ONLY)
    assert ok_read is True

    ok_write, err_write = pm.check_permission(ToolPermission.WRITE_FILE)
    assert ok_write is False
    assert "read-only mode" in err_write


# ==============================================================================
# 8. AgentGuard Integrated Interception
# ==============================================================================

@pytest.mark.asyncio
async def test_agent_guard_blocks_uninspected_write(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    guard = AgentGuard(ws, harness_mode=HarnessMode.HYBRID)
    runner = MockExecutionRunner()

    context = ToolContext(
        session_id="guard_test",
        step_index=1,
        workspace=ws,
        runner=runner,
    )

    # File exists on disk
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")

    tool = WriteFileTool()
    req = ToolExecutionRequest(
        tool_name="write_file",
        arguments={"file_path": "config.json", "content": '{"updated": true}'},
        session_id="guard_test",
        step_index=1,
    )

    # Interception blocks modification because file has not been read
    result = await guard.execute_guarded(req, tool, context)
    assert result.success is False
    assert "has not been inspected" in result.error
    assert result.metadata["guard_blocked"] is True


@pytest.mark.asyncio
async def test_agent_guard_blocks_workspace_escape(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    guard = AgentGuard(ws)
    runner = MockExecutionRunner()

    context = ToolContext(
        session_id="guard_test",
        step_index=1,
        workspace=ws,
        runner=runner,
    )

    tool = ReadFileTool()
    req = ToolExecutionRequest(
        tool_name="read_file",
        arguments={"file_path": "../../secret.txt"},
        session_id="guard_test",
        step_index=1,
    )

    result = await guard.execute_guarded(req, tool, context)
    assert result.success is False
    assert "Security Violation" in result.error
    assert result.metadata["guard_blocked"] is True
