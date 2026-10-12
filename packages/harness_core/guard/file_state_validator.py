"""FileStateValidator component for tracking on-disk file state and content hashes."""

from typing import Dict, Optional
from packages.harness_core.execution.workspace import WorkspaceManager


class FileStateValidator:
    """Monitors file hash states and detects unexpected content drift."""

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace
        # Historical hashes recorded on disk: rel_path -> sha256_hash
        self._recorded_hashes: Dict[str, str] = {}

    def compute_file_hash(self, rel_path: str) -> Optional[str]:
        """Compute SHA-256 hash of a file within the workspace."""
        digest = self.workspace.compute_hash(rel_path)
        if digest is not None:
            norm_key = self.workspace.normalize_rel_path(rel_path)
            self._recorded_hashes[norm_key] = digest
        return digest

    def has_file_changed(self, rel_path: str, baseline_hash: str) -> bool:
        """Return True if the current on-disk hash differs from the baseline hash."""
        current = self.compute_file_hash(rel_path)
        if current is None:
            # File deleted
            return True
        return current != baseline_hash

    def get_last_known_hash(self, rel_path: str) -> Optional[str]:
        """Retrieve the last recorded hash for a workspace file."""
        norm_key = self.workspace.normalize_rel_path(rel_path)
        return self._recorded_hashes.get(norm_key)
