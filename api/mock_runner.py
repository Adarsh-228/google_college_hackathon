import time
from typing import Generator, Dict, Any, Optional

def mock_run_agent_task(
    workspace_path: str,
    task_prompt: str,
    model_id: str = "gemini-2.5-flash",
    harness_config: Optional[Dict[str, Any]] = None,
    client: Any = None,
    max_steps: int = 10,
) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """
    Simulates live agent turns over a 3-5 second interval.
    Enables Person 2 & 3 to test the API and UI independently.
    """
    config = harness_config or {}
    harness_enabled = config.get("harness_enabled", True)
    context_tier = config.get("context_tier", "T4")
    budget_cap = config.get("budget_cap", 32768)

    # Turn 1: Initialization
    time.sleep(0.5)
    yield {
        "turn_idx": 1,
        "type": "TURN_START",
        "data": {
            "turn": 1,
            "estimated_tokens": 1200,
            "budget_cap": budget_cap,
            "current_plan": [{"content": "Inspect repository files", "status": "in_progress"}],
        },
    }

    # Turn 1: Plan update
    time.sleep(0.3)
    yield {
        "turn_idx": 1,
        "type": "PLAN_UPDATE",
        "data": {
            "current_plan": [
                {"content": "Inspect repository files", "status": "in_progress"},
                {"content": "Read source code and locate bug", "status": "pending"},
                {"content": "Apply patch and verify tests", "status": "pending"},
            ]
        },
    }

    # Turn 2: Run tests
    time.sleep(0.6)
    yield {
        "turn_idx": 2,
        "type": "TOOL_CALL",
        "data": {"tool": "bash", "args": {"command": "pytest -v"}},
    }
    time.sleep(0.4)
    yield {
        "turn_idx": 2,
        "type": "TOOL_RESULT",
        "data": {
            "tool": "bash",
            "output": "FAILED test_app.py::test_pagination_boundary - AssertionError: expected 10 items, got 9",
            "is_error": True,
        },
    }

    # Turn 3: Read file
    time.sleep(0.5)
    yield {
        "turn_idx": 3,
        "type": "TOOL_CALL",
        "data": {"tool": "read_file", "args": {"path": "app.py", "offset": 1, "limit": 200}},
    }
    time.sleep(0.4)
    yield {
        "turn_idx": 3,
        "type": "TOOL_RESULT",
        "data": {"tool": "read_file", "output": "1 | def paginate(items, page, size):\n2 |   start = (page - 1) * size\n3 |   return items[start:start+size-1]", "is_error": False},
    }

    # Check for M1 Elision if budget is tight
    if harness_enabled and context_tier.startswith("T4") and budget_cap <= 32768:
        time.sleep(0.3)
        yield {
            "turn_idx": 3,
            "type": "COMPACTION",
            "data": {"badge": "M1_ELISION", "m1_count": 1, "tokens_after": 1850},
        }

    # Turn 4: Edit file
    time.sleep(0.6)
    yield {
        "turn_idx": 4,
        "type": "TOOL_CALL",
        "data": {
            "tool": "edit_file",
            "args": {
                "path": "app.py",
                "old_text": "return items[start:start+size-1]",
                "new_text": "return items[start:start+size]",
            },
        },
    }
    time.sleep(0.4)
    yield {
        "turn_idx": 4,
        "type": "GUARD_EVENT",
        "data": {"badge": "LINT_DETECTED", "tool": "edit_file", "output": "ruff clean: 0 errors"},
    }
    yield {
        "turn_idx": 4,
        "type": "TOOL_RESULT",
        "data": {"tool": "edit_file", "output": "Successfully replaced 1 occurrence in app.py", "is_error": False},
    }

    # Turn 5: Re-run tests to verify
    time.sleep(0.5)
    yield {
        "turn_idx": 5,
        "type": "TOOL_CALL",
        "data": {"tool": "bash", "args": {"command": "pytest -v"}},
    }
    time.sleep(0.4)
    yield {
        "turn_idx": 5,
        "type": "TOOL_RESULT",
        "data": {"tool": "bash", "output": "PASSED test_app.py::test_pagination_boundary", "is_error": False},
    }

    # Final summary
    time.sleep(0.4)
    yield {
        "turn_idx": 6,
        "type": "RUN_FINISH",
        "data": {
            "resolved": True,
            "stop_reason": "RESOLVED",
            "final_message": "All unit tests pass. Fixed off-by-one pagination bug in app.py.",
        },
    }

    return {
        "resolved": True,
        "stop_reason": "RESOLVED",
        "total_turns": 6,
        "total_cost_usd": 0.00164,
        "tokens_in_uncached": 9400,
        "tokens_in_cached": 1200,
        "tokens_out": 450,
        "m1_count": 1 if harness_enabled else 0,
        "m3_count": 0,
        "guard_events_count": 1,
        "re_patch_count": 0,
    }
