"""Execution report generator."""

from typing import List, Optional

from packages.harness_core.contracts.enums import (
    ContextStrategy,
    ExecutionStatus,
    HarnessMode,
)
from packages.harness_core.contracts.responses import (
    ExecutionReport,
    PerformanceMetrics,
    TaskPlanStep,
)


class ExecutionReporter:
    """Compiles the final execution report."""

    @staticmethod
    def build_report(
        session_id: str,
        task: str,
        status: ExecutionStatus,
        harness_mode: HarnessMode,
        context_strategy: ContextStrategy,
        plan: List[TaskPlanStep],
        completed_steps: List[str],
        files_created: List[str],
        files_modified: List[str],
        errors_encountered: List[str],
        diagnostics_resolved: int,
        metrics: PerformanceMetrics,
        summary: Optional[str] = None,
    ) -> ExecutionReport:
        clean_summary = summary or (
            f"Execution concluded with status '{status.value}'. "
            f"Completed {len(completed_steps)} of {len(plan)} planned steps. "
            f"Modified {len(files_modified)} files, resolved {diagnostics_resolved} diagnostics."
        )

        return ExecutionReport(
            session_id=session_id,
            task=task,
            status=status,
            harness_mode=harness_mode,
            context_strategy=context_strategy,
            plan=plan,
            completed_steps=completed_steps,
            files_created=files_created,
            files_modified=files_modified,
            errors_encountered=errors_encountered,
            diagnostics_resolved=diagnostics_resolved,
            metrics=metrics,
            summary=clean_summary,
        )
