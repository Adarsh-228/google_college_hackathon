"""Tests for telemetry, metrics collection, and reporting."""

import pytest
from packages.harness_core.contracts.enums import EventType, ExecutionStatus, HarnessMode
from packages.harness_core.contracts.events import AgentEvent
from packages.harness_core.telemetry.collector import TelemetryCollector
from packages.harness_core.telemetry.metrics import MetricsTracker
from packages.harness_core.telemetry.reporter import ExecutionReporter


@pytest.mark.asyncio
async def test_telemetry_collector_broadcast():
    collected = []

    async def sample_handler(evt: AgentEvent):
        collected.append(evt)

    collector = TelemetryCollector(session_id="sess_t1", task_id="task_t1")
    collector.register_handler(sample_handler)

    await collector.emit(
        event_type=EventType.TASK_ANALYZED,
        component="task_analyzer",
        payload={"language": "python"},
    )

    assert len(collector.events) == 1
    assert collector.events[0].event_type == EventType.TASK_ANALYZED


def test_metrics_tracker_cost_and_tokens():
    tracker = MetricsTracker("gemini-2.5-flash")
    tracker.record_inference(in_tokens=10000, out_tokens=2000)
    tracker.record_tool_call(is_repeated=False)
    tracker.record_tool_call(is_repeated=True)
    tracker.record_diagnostic(2)
    tracker.set_duration(12.5)

    metrics = tracker.get_metrics()
    assert metrics.input_tokens == 10000
    assert metrics.output_tokens == 2000
    assert metrics.total_tokens == 12000
    assert metrics.tool_call_count == 2
    assert metrics.repeated_call_count == 1
    assert metrics.diagnostic_count == 2
    assert metrics.estimated_cost_usd > 0.0
    assert metrics.execution_duration_seconds == 12.5
