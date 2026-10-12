"""Tests for ContextT4 context management strategies."""

import pytest
from packages.harness_core.contracts.enums import ContextStrategy
from packages.harness_core.context.elision import RuleBasedElider
from packages.harness_core.context.manager import ContextManager
from packages.harness_core.context.preservation import PreservationRules
from packages.harness_core.context.summarizer import ContextSummarizer
from packages.harness_core.providers.base import LLMMessage
from packages.harness_core.providers.mock_provider import MockLLMProvider


def test_preservation_rules():
    messages = [
        LLMMessage(role="system", content="System instruction"),  # idx 0 -> protected
        LLMMessage(role="user", content="Original task"),          # idx 1 -> protected
        LLMMessage(role="tool", content="Older observation"),      # idx 2 -> NOT protected
        LLMMessage(role="model", content="Thinking"),              # idx 3 -> protected by window of 3
        LLMMessage(role="tool", content="Recent obs"),             # idx 4 -> protected
        LLMMessage(role="user", content="Latest query"),           # idx 5 -> protected
    ]

    protected = PreservationRules.identify_protected_indices(messages, recent_window_size=3)
    assert 0 in protected
    assert 1 in protected
    assert 2 not in protected
    assert 3 in protected
    assert 4 in protected
    assert 5 in protected


def test_rule_based_elision_truncates_bulky_observations():
    elider = RuleBasedElider(max_observation_chars=100)
    bulky_text = "X" * 1000

    messages = [
        LLMMessage(role="system", content="System"),
        LLMMessage(role="user", content="Task"),
        LLMMessage(role="tool", tool_name="run_terminal_command", content=bulky_text),
        LLMMessage(role="model", content="Recent turn 1"),
        LLMMessage(role="user", content="Recent turn 2"),
    ]

    pruned, saved = elider.elide(messages, recent_window_size=2)
    assert saved > 500
    assert len(pruned[2].content) < len(bulky_text)
    assert "[ELIDED" in pruned[2].content
    assert pruned[2].metadata["elided"] is True


@pytest.mark.asyncio
async def test_structured_summarizer_headers():
    summarizer = ContextSummarizer(provider=None)
    messages = [
        LLMMessage(role="tool", tool_name="write_file", metadata={"files_touched": ["main.py"]}),
        LLMMessage(role="tool", tool_name="edit_file", content="failed to match line", metadata={"error": True}),
    ]
    summary = await summarizer.summarize_history(messages, original_goal="Build REST API")

    assert "1. **Goal**: Build REST API" in summary
    assert "2. **Files Touched**" in summary
    assert "3. **Done**" in summary
    assert "4. **Pending**" in summary
    assert "5. **Errors & Fixes**" in summary
    assert "6. **Current State**" in summary
    assert "7. **Next Step**" in summary


@pytest.mark.asyncio
async def test_context_manager_t0_vs_t1_vs_t4():
    mock_prov = MockLLMProvider()
    bulky_tool = "A" * 2000

    base_messages = [
        LLMMessage(role="system", content="System"),
        LLMMessage(role="user", content="Task"),
        LLMMessage(role="tool", tool_name="terminal", content=bulky_tool),
        LLMMessage(role="model", content="Recent"),
    ]

    # T0: No management
    mgr_t0 = ContextManager(provider=mock_prov, strategy=ContextStrategy.T0_NONE)
    t0_res = await mgr_t0.prepare_context(base_messages)
    assert len(t0_res[2].content) == 2000

    # T1: Rule-based elision
    mgr_t1 = ContextManager(
        provider=mock_prov, strategy=ContextStrategy.T1_ELISION, recent_window_size=1
    )
    t1_res = await mgr_t1.prepare_context(base_messages)
    assert len(t1_res[2].content) < 2000

    # T4: Staged (threshold-triggered)
    # Set low soft threshold so elision fires
    mgr_t4 = ContextManager(
        provider=mock_prov,
        strategy=ContextStrategy.T4_STAGED,
        soft_threshold=0.01,
        hard_threshold=0.99,
        window_limit=1000,
        recent_window_size=1,
    )
    t4_res = await mgr_t4.prepare_context(base_messages)
    assert len(t4_res[2].content) < 2000
    assert mgr_t4.stats.elided_count >= 1
