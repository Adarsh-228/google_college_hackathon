"""ReadBeforeWriteValidator component for enforcing inspection before mutation."""

from typing import Dict, Optional, Tuple
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.guard.file_state_validator import FileStateValidator


class ReadBeforeWriteValidator:
    """Enforces that existing files must be read before any edit or overwrite operation."""

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace
        self.state_validator = FileStateValidator(workspace)
        # Tracks agent read actions: rel_path -> sha256_at_read_time
        self._read_registry: Dict[str, str] = {}

    def record_read(self, rel_path: str) -> Optional[str]:
        """Record that the agent has inspected the file at its current hash."""
        digest = self.workspace.record_read(rel_path)
        norm_key = self.workspace.normalize_rel_path(rel_path)
        if digest is not None:
            self._read_registry[norm_key] = digest
        return digest

    def is_read_recorded(self, rel_path: str) -> bool:
        """Check whether a read has been recorded for the given file."""
        norm_key = self.workspace.normalize_rel_path(rel_path)
        return norm_key in self._read_registry or self.workspace.get_last_read_hash(rel_path) is not None

    def validate_pre_modification(
        self,
        rel_path: str,
        is_new_file_expected: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Verify that an edit/write does not overwrite stale or uninspected state.

        Returns (is_valid, error_reason).
        """
        exists = self.workspace.file_exists(rel_path)

        # 1. Brand new file creation is always permitted
        if not exists:
            return True, None

        # 2. Existing file: verify agent read before modifying
        last_read_hash = self.workspace.get_last_read_hash(rel_path)
        norm_key = self.workspace.normalize_rel_path(rel_path)
        effective_read_hash = last_read_hash or self._read_registry.get(norm_key)

        if effective_read_hash is None:
            return (
                False,
                f"File Integrity Violation: File '{rel_path}' exists but has not been inspected "
                f"via read_file. You must read an existing file before modifying or overwriting it.",
            )

        # 3. Detect drift/modifications on disk since the read operation
        current_hash = self.workspace.compute_hash(rel_path)
        if current_hash != effective_read_hash:
            return (
                False,
                f"Stale Edit Detected: File '{rel_path}' has changed on disk since your last read "
                f"(current hash: {current_hash[:8]}, last read: {effective_read_hash[:8]}). "
                f"Please read the latest contents of '{rel_path}' before attempting modifications.",
            )

        return True, None
