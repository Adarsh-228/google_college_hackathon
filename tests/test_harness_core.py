import os
import tempfile
import pytest
from packages.harness_core.types import HarnessConfig, CircuitBreakerError, ContextOverflowError
from packages.harness_core.guard import AgentGuard
from packages.harness_core.context_t4 import ContextT4Manager
from packages.harness_core.planning import PlanningEngine
from packages.harness_core.tools import ToolRegistry
from packages.harness_core.runner import run_agent_task
from packages.harness_core.providers import MockLLMClient

def test_rbw_read_before_write_enforcement():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = HarnessConfig(enable_rbw=True)
        guard = AgentGuard(tmpdir, config)
        tool_reg = ToolRegistry(tmpdir, guard)

        # Create an existing file directly on disk
        target_file = os.path.join(tmpdir, "test.py")
        with open(target_file, "w") as f:
            f.write("a = 1\n")

        # Attempting edit WITHOUT read MUST be blocked by RBW!
        out, is_err, badge = tool_reg.execute_tool("edit_file", {
            "path": "test.py",
            "old_text": "a = 1",
            "new_text": "a = 2",
        })
        assert is_err is True
        assert badge == "RBW_BLOCKED"
        assert "has not been read in this session" in out

        # Now perform a full read
        read_out, read_err, _ = tool_reg.execute_tool("read_file", {
            "path": "test.py",
            "offset": 1,
            "limit": 100,
        })
        assert read_err is False

        # Now edit MUST succeed!
        edit_out, edit_err, _ = tool_reg.execute_tool("edit_file", {
            "path": "test.py",
            "old_text": "a = 1",
            "new_text": "a = 2",
        })
        assert edit_err is False
        assert "Successfully replaced 1 occurrence" in edit_out

def test_zero_turn_linter_catches_syntax_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = HarnessConfig(enable_rbw=False, enable_lint=True)
        guard = AgentGuard(tmpdir, config)
        tool_reg = ToolRegistry(tmpdir, guard)

        # Write invalid Python syntax
        out, is_err, badge = tool_reg.execute_tool("write_file", {
            "path": "bad_syntax.py",
            "content": "def broken_func(\n  print('missing paren'",
        })
        assert badge == "LINT_DETECTED"
        assert "AgentGuard Linter" in out

def test_streak_circuit_breaker():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = HarnessConfig(enable_streak_breaker=True)
        guard = AgentGuard(tmpdir, config)

        # 1-4 calls: no warning
        for _ in range(4):
            warn, term = guard.evaluate_streak("test_tool", {"arg": 1}, is_error=True)
            assert warn is None
            assert term is False

        # 5th call: Warning injected!
        warn5, term5 = guard.evaluate_streak("test_tool", {"arg": 1}, is_error=True)
        assert warn5 is not None
        assert "system-reminder" in warn5
        assert term5 is False

        # 6-7 calls: continue
        for _ in range(2):
            guard.evaluate_streak("test_tool", {"arg": 1}, is_error=True)

        # 8th call: Circuit breaker terminates!
        warn8, term8 = guard.evaluate_streak("test_tool", {"arg": 1}, is_error=True)
        assert term8 is True
        assert "STUCK LOOP HALT" in warn8

def test_context_t4_staged_compaction():
    config = HarnessConfig(
        context_tier="T4",
        budget_cap=1000,
        soft_threshold_ratio=0.60,
        hard_threshold_ratio=0.85,
    )
    mgr = ContextT4Manager(config)

    # Build messages that exceed B1 (600 tokens approx 2400 chars)
    bulky_tool_output = "Line data log output\n" * 150  # ~3000 chars
    messages = [
        {"role": "system", "content": "Preamble system prompt"},
        {"role": "user", "content": "Task description"},
        {"role": "assistant", "content": "Middle turn reasoning"},
        {"role": "tool", "content": bulky_tool_output, "type": "tool_result"},
        {"role": "assistant", "content": "Middle turn 2 reasoning"},
        {"role": "tool", "content": bulky_tool_output, "type": "tool_result"},
        {"role": "assistant", "content": "Recent turn 1"},
        {"role": "user", "content": "Recent turn 1 observation"},
        {"role": "assistant", "content": "Recent turn 2"},
        {"role": "user", "content": "Recent turn 2 observation"},
    ]

    compacted, badge = mgr.process_turn(messages, preamble_count=2)
    assert badge is not None
    assert "M1_ELISION" in badge
    # Middle bulky outputs must be replaced by stubs
    assert "[tool output elided:" in compacted[3]["content"]

def test_context_t0_overflow_raises_error():
    config = HarnessConfig(context_tier="T0", budget_cap=200)
    mgr = ContextT4Manager(config)
    messages = [
        {"role": "system", "content": "A" * 1000},
    ]
    with pytest.raises(ContextOverflowError):
        mgr.process_turn(messages)
