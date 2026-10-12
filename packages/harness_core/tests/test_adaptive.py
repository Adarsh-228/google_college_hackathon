"""Tests for AdaptiveHarness capability profiling and mode selection."""

import pytest
from packages.harness_core.adaptive.capability_profiler import CapabilityProfiler
from packages.harness_core.adaptive.configuration_selector import AdaptiveHarnessSelector
from packages.harness_core.adaptive.task_classifier import TaskClassifier
from packages.harness_core.contracts.enums import HarnessMode, TaskComplexity


def test_task_classifier_complexity():
    # Simple inspection
    c_low = TaskClassifier.classify("Read the readme file and tell me the version")
    assert c_low.complexity == TaskComplexity.LOW
    assert c_low.primary_category == "inspection"

    # High complexity full-stack task
    c_high = TaskClassifier.classify(
        "Build a distributed async backend architecture with migration and security authentication"
    )
    assert c_high.complexity == TaskComplexity.HIGH

    # Terminal command involvement
    c_term = TaskClassifier.classify("Run pytest and install missing requirements via pip")
    assert c_term.involves_terminal_commands is True


def test_capability_profiler_defaults():
    p_known = CapabilityProfiler.get_profile("gemini-2.5-pro")
    assert p_known.bash_proficiency_score >= 0.9

    p_unknown = CapabilityProfiler.get_profile("some-unreleased-custom-model")
    assert p_unknown.recommended_mode == HarnessMode.GUIDED
    assert "Unbenchmarked model" in p_unknown.notes


def test_adaptive_harness_selector_user_override():
    rec = AdaptiveHarnessSelector.select_configuration(
        model_name="gemini-2.5-flash",
        task_description="Build a microservice",
        user_mode_override=HarnessMode.DIRECT,
    )
    assert rec.mode == HarnessMode.DIRECT
    assert rec.is_user_override is True
    assert "User explicitly selected" in rec.reasoning


def test_adaptive_harness_selector_automatic_mode():
    rec_cli = AdaptiveHarnessSelector.select_configuration(
        model_name="gemini-2.5-pro",
        task_description="Run tests and pip install dependencies",
    )
    # Pro model with CLI-oriented task -> DIRECT
    assert rec_cli.mode == HarnessMode.DIRECT
    assert "bash proficiency" in rec_cli.reasoning
