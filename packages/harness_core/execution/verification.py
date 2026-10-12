"""Verification engine to validate task completion and test assertions."""

import ast
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.execution.runner import BaseExecutionRunner
from packages.harness_core.execution.workspace import WorkspaceManager


class VerificationOutcome(BaseModel):
    """Structured report of verification checks."""
    success: bool
    summary: str
    files_checked: List[str] = Field(default_factory=list)
    tests_passed: Optional[bool] = None
    syntax_valid: bool = True
    test_output: str = ""
    issues: List[str] = Field(default_factory=list)


class TaskVerifier:
    """Verifies workspace state, syntax integrity, and automated tests."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        execution_runner: BaseExecutionRunner,
    ) -> None:
        self.workspace = workspace_manager
        self.runner = execution_runner

    async def verify_task(
        self,
        expected_files: Optional[List[str]] = None,
        test_command: Optional[str] = None,
    ) -> VerificationOutcome:
        """Run comprehensive verification on workspace."""
        issues: List[str] = []
        files_checked: List[str] = []
        syntax_valid = True

        # 1. Check expected files existence
        if expected_files:
            for f in expected_files:
                files_checked.append(f)
                if not self.workspace.file_exists(f):
                    issues.append(f"Expected file '{f}' was not created or found.")
                else:
                    path = self.workspace.resolve_path(f)
                    if path.stat().st_size == 0:
                        issues.append(f"Expected file '{f}' is empty.")

        # 2. Check syntax of all python files in workspace
        py_files = [f for f in self.workspace.list_files() if f.endswith(".py")]
        for pf in py_files:
            abs_p = self.workspace.resolve_path(pf)
            try:
                content = abs_p.read_text(encoding="utf-8", errors="replace")
                ast.parse(content, filename=pf)
            except SyntaxError as e:
                syntax_valid = False
                issues.append(f"Syntax error in '{pf}' at line {e.lineno}: {e.msg}")

        # 3. Run automated tests if command given or test files present
        tests_passed: Optional[bool] = None
        test_output = ""

        effective_test_cmd = test_command
        if not effective_test_cmd:
            # Check if any test files exist
            if any("test" in f.lower() and f.endswith(".py") for f in py_files):
                effective_test_cmd = "python -m pytest"

        if effective_test_cmd:
            try:
                code, stdout, stderr = await self.runner.run_command(
                    effective_test_cmd,
                    cwd=self.workspace.root,
                    timeout_seconds=60,
                )
                test_output = stdout + ("\n" + stderr if stderr else "")
                tests_passed = (code == 0)
                if not tests_passed:
                    issues.append(f"Verification test command failed (exit code {code}).")
            except Exception as e:
                tests_passed = False
                issues.append(f"Test execution error: {str(e)}")

        overall_success = len(issues) == 0 and syntax_valid and (tests_passed is None or tests_passed)
        summary = "Verification succeeded." if overall_success else f"Verification found {len(issues)} issue(s)."

        return VerificationOutcome(
            success=overall_success,
            summary=summary,
            files_checked=files_checked,
            tests_passed=tests_passed,
            syntax_valid=syntax_valid,
            test_output=test_output,
            issues=issues,
        )
