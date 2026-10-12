"""Example script demonstrating local HarnessX agent execution."""

import asyncio
import os
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.harness_core import (
    AgentEvent,
    EngineConfig,
    ExecutionStatus,
    HarnessEngine,
    HarnessMode,
    MockLLMProvider,
)


async def event_logger(event: AgentEvent) -> None:
    """Stream events to console in real-time."""
    print(f"[{event.timestamp.strftime('%H:%M:%S')}] [{event.component.upper()}] "
          f"{event.event_type.value}: {event.payload}")


async def main():
    print("=" * 60)
    print(" HarnessX Autonomous Agent Engine: Local Runner")
    print("=" * 60)

    # 1. Determine provider mode
    gemini_key = os.getenv("GEMINI_API_KEY")
    use_vertex = os.getenv("USE_VERTEX", "false").lower() in ("1", "true", "yes")

    if not gemini_key and not use_vertex:
        print("[INFO] No GEMINI_API_KEY or USE_VERTEX detected in environment.")
        print("[INFO] Running in mock simulation mode demonstrating vertical workflow.\n")

        # Set up mock multi-turn simulation
        mock = MockLLMProvider()
        mock.queue_tool_call(
            tool_name="write_file",
            arguments={
                "file_path": "api.py",
                "content": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'status': 'healthy'}\n",
            },
            thought="Step 1: Creating FastAPI application file.",
        )
        mock.queue_tool_call(
            tool_name="read_file",
            arguments={"file_path": "api.py"},
            thought="Step 2: Inspecting created API code.",
        )
        mock.queue_text_response(
            "Task Complete: Created FastAPI service in api.py with a health check route."
        )

        engine = HarnessEngine(provider=mock)
    else:
        print("[INFO] Live provider detected. Initializing engine with environment settings.\n")
        engine = HarnessEngine()

    # Register streaming event handler
    engine.register_event_handler(event_logger)

    # 2. Run coding task
    task_prompt = "Create a FastAPI web service in api.py with a / health check endpoint"
    print(f"Submitting Task: '{task_prompt}'\n")

    response = await engine.run_task(
        task=task_prompt,
        workspace_dir="./workspaces/demo_session",
        mode=HarnessMode.HYBRID,
    )

    # 3. Print Results
    print("\n" + "=" * 60)
    print(f" Execution Finished with Status: {response.status.value}")
    print("=" * 60)
    print(f"Session ID       : {response.session_id}")
    print(f"Files Created    : {response.report.files_created}")
    print(f"Files Modified   : {response.report.files_modified}")
    print(f"Tool Calls Made  : {response.metrics.tool_call_count}")
    print(f"Total Tokens     : {response.metrics.total_tokens}")
    print(f"Estimated Cost   : ${response.metrics.estimated_cost_usd:.6f}")
    print(f"Elapsed Time     : {response.metrics.execution_duration_seconds}s")
    print("\nFinal Result Summary:")
    print(response.final_result)


if __name__ == "__main__":
    asyncio.run(main())
