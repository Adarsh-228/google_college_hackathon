"""Test verifying the backend integration route example for Person 2."""

import pytest
from packages.harness_core import (
    AgentExecutionRequest,
    AgentExecutionResponse,
    ExecutionStatus,
    HarnessMode,
    MockLLMProvider,
    HarnessEngine,
)
from packages.harness_core.examples.backend_integration_example import (
    app,
    cancel_agent_session,
    get_session_metrics,
    run_agent_task,
    engine,
)


@pytest.mark.asyncio
async def test_backend_route_run_and_serialization(tmp_path):
    """Verify that backend route returns valid serializable response using public contracts."""
    # Ensure offline deterministic test provider
    engine.provider = MockLLMProvider()

    # Create request
    ws_dir = str(tmp_path / "backend_ws")
    request = AgentExecutionRequest(
        task="Create a test module in utils.py",
        session_id="sess_backend_test",
        workspace_dir=ws_dir,
        harness_mode=HarnessMode.HYBRID,
        timeout_seconds=60,
    )

    # Call the FastAPI route handler directly
    response: AgentExecutionResponse = await run_agent_task(request)

    # Verify type and structure
    assert isinstance(response, AgentExecutionResponse)
    assert response.session_id == "sess_backend_test"
    assert response.status == ExecutionStatus.COMPLETED

    # Verify JSON serializability for FastAPI response
    json_data = response.model_dump(mode="json")
    assert isinstance(json_data, dict)
    assert json_data["status"] == "COMPLETED"
    assert "report" in json_data
    assert "metrics" in json_data
    assert "files_created" in json_data["report"]


@pytest.mark.asyncio
async def test_backend_route_metrics_and_cancel():
    """Verify metrics query and cancellation routes."""
    # Query metrics for the completed session
    metrics = await get_session_metrics("sess_backend_test")
    assert metrics is not None
    assert metrics.final_status == ExecutionStatus.COMPLETED

    # Cancel a non-existent or inactive session returns 404 HTTPException
    with pytest.raises(Exception):
        await cancel_agent_session("non_existent_session")
