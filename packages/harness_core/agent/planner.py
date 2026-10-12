"""Task planner module."""

from typing import List
from packages.harness_core.agent.task_analyzer import AnalyzedTask
from packages.harness_core.contracts.enums import HarnessMode
from packages.harness_core.contracts.responses import TaskPlanStep


class TaskPlanner:
    """Generates structured execution plan steps."""

    @staticmethod
    def create_initial_plan(
        analyzed_task: AnalyzedTask,
        mode: HarnessMode,
    ) -> List[TaskPlanStep]:
        steps: List[TaskPlanStep] = []

        # Step 1: Inspection
        steps.append(
            TaskPlanStep(
                step_number=1,
                description="Inspect existing workspace and check project files",
                tool_suggested="list_files",
                status="PENDING",
            )
        )

        # Step 2: Implementation
        if mode == HarnessMode.DIRECT:
            steps.append(
                TaskPlanStep(
                    step_number=2,
                    description="Execute terminal script or build command to construct solution",
                    tool_suggested="run_terminal_command",
                    status="PENDING",
                )
            )
        else:
            files_desc = (
                f"Create target source files ({', '.join(analyzed_task.referenced_files)})"
                if analyzed_task.referenced_files
                else "Write source implementation files"
            )
            steps.append(
                TaskPlanStep(
                    step_number=2,
                    description=files_desc,
                    tool_suggested="write_file",
                    status="PENDING",
                )
            )

        # Step 3: Verification & Validation
        steps.append(
            TaskPlanStep(
                step_number=3,
                description="Verify code syntax, run tests or execute verification checks",
                tool_suggested="run_terminal_command" if mode != HarnessMode.GUIDED else "read_file",
                status="PENDING",
            )
        )

        return steps
