"""Workspace protection and boundary enforcement."""

from pathlib import Path
from typing import Optional, Tuple
from packages.harness_core.exceptions.errors import PathTraversalError
from packages.harness_core.execution.workspace import WorkspaceManager


class WorkspaceProtection:
    """Enforces that all file reads, writes, and searches stay strictly within workspace bounds."""

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    def validate_path(self, target_path: str) -> Tuple[bool, Optional[str]]:
        """Verify that a path does not escape the configured workspace.

        Returns (is_valid, error_reason).
        """
        if not target_path or not str(target_path).strip():
            return False, "Path cannot be empty."

        try:
            resolved = self.workspace.resolve_path(target_path)
            # Verify relative to workspace root
            resolved.relative_to(self.workspace.root)
            return True, None
        except PathTraversalError as e:
            return False, f"Security Violation: Path traversal blocked: {str(e)}"
        except Exception as e:
            return False, f"Invalid path resolution: {str(e)}"

    def assert_safe_path(self, target_path: str) -> Path:
        """Resolve path or raise PathTraversalError immediately."""
        return self.workspace.resolve_path(target_path)
