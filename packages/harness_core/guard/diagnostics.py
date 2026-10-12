"""Post-edit code diagnostics and syntax analysis."""

import ast
import json
import shutil
import subprocess
from typing import List, Optional
from pathlib import Path

from packages.harness_core.contracts.responses import DiagnosticResult
from packages.harness_core.execution.workspace import WorkspaceManager


class PostEditDiagnostics:
    """Performs static syntax verification and optional linting after file edits."""

    def __init__(
        self,
        workspace: WorkspaceManager,
        enable_ruff: bool = True,
    ) -> None:
        self.workspace = workspace
        self.enable_ruff = enable_ruff and bool(shutil.which("ruff"))

    def check_file(self, rel_path: str) -> List[DiagnosticResult]:
        """Run diagnostics on a target file."""
        if not rel_path.endswith(".py"):
            return []

        abs_p = self.workspace.resolve_path(rel_path)
        if not abs_p.is_file():
            return []

        diagnostics: List[DiagnosticResult] = []

        # 1. AST Syntax Check
        try:
            content = abs_p.read_text(encoding="utf-8", errors="replace")
            ast.parse(content, filename=rel_path)
        except SyntaxError as e:
            diagnostics.append(
                DiagnosticResult(
                    file_path=rel_path,
                    line_number=e.lineno,
                    error_type="SyntaxError",
                    message=f"{e.msg} (offset: {e.offset})",
                    severity="error",
                    source="ast_syntax",
                )
            )
            # If syntax fails, no need to run linter
            return diagnostics
        except Exception as e:
            diagnostics.append(
                DiagnosticResult(
                    file_path=rel_path,
                    line_number=None,
                    error_type="ParseError",
                    message=str(e),
                    severity="error",
                    source="ast_syntax",
                )
            )
            return diagnostics

        # 2. Optional Ruff Linter Check
        if self.enable_ruff:
            try:
                cmd = ["ruff", "check", "--output-format=json", str(abs_p)]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.stdout:
                    ruff_issues = json.loads(proc.stdout)
                    for issue in ruff_issues[:5]:  # Limit to 5 issues
                        diagnostics.append(
                            DiagnosticResult(
                                file_path=rel_path,
                                line_number=issue.get("location", {}).get("row"),
                                error_type=issue.get("code", "RuffWarning"),
                                message=issue.get("message", "Lint warning"),
                                severity="warning",
                                source="ruff",
                            )
                        )
            except Exception:
                # Ruff is optional; silently omit on execution failure
                pass

        return diagnostics


# Backward-compatible alias
CodeDiagnosticsGuard = PostEditDiagnostics
