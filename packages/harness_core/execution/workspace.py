"""Workspace sandbox isolation and path security."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import os

from packages.harness_core.exceptions.errors import PathTraversalError, WorkspaceError


class WorkspaceManager:
    """Manages an isolated workspace directory, preventing traversal and tracking hashes."""

    def __init__(self, workspace_root: Path) -> None:
        self.root = Path(workspace_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        # In-memory record of file hashes: relative_path -> sha256_hex
        self._file_hashes: Dict[str, str] = {}
        # History of verified reads by the agent: relative_path -> sha256_at_read_time
        self._last_read_hashes: Dict[str, str] = {}

    def resolve_path(self, relative_or_absolute: str) -> Path:
        """Resolve path strictly within the workspace root. Rejects path traversal."""
        clean_str = str(relative_or_absolute).strip()
        # Disallow raw Windows drive roots like C:\ or D:\ if outside workspace
        candidate = (self.root / clean_str).resolve() if not Path(clean_str).is_absolute() else Path(clean_str).resolve()

        try:
            # Check if resolved candidate is relative to workspace root
            candidate.relative_to(self.root)
        except ValueError:
            raise PathTraversalError(
                f"Access denied: Path '{relative_or_absolute}' escapes workspace root '{self.root}'"
            )

        return candidate

    def get_relative_path(self, target_path: Path) -> str:
        """Convert a path into normalized workspace-relative string."""
        resolved = target_path.resolve()
        try:
            return str(resolved.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(resolved).replace("\\", "/")

    def compute_hash(self, rel_path: str) -> Optional[str]:
        """Compute SHA-256 hash of a workspace file."""
        abs_path = self.resolve_path(rel_path)
        if not abs_path.is_file():
            return None
        hasher = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        norm_key = self.normalize_rel_path(rel_path)
        self._file_hashes[norm_key] = digest
        return digest

    def record_read(self, rel_path: str) -> Optional[str]:
        """Record that agent inspected the file at its current hash."""
        digest = self.compute_hash(rel_path)
        norm_key = self.normalize_rel_path(rel_path)
        if digest is not None:
            self._last_read_hashes[norm_key] = digest
        return digest

    def get_last_read_hash(self, rel_path: str) -> Optional[str]:
        """Get the hash recorded when agent last read the file."""
        norm_key = self.normalize_rel_path(rel_path)
        return self._last_read_hashes.get(norm_key)

    def file_exists(self, rel_path: str) -> bool:
        """Check if file exists in workspace."""
        try:
            abs_path = self.resolve_path(rel_path)
            return abs_path.is_file()
        except PathTraversalError:
            return False

    def list_files(self, sub_dir: str = "", recursive: bool = True) -> List[str]:
        """List files relative to workspace root."""
        target_dir = self.resolve_path(sub_dir) if sub_dir else self.root
        if not target_dir.is_dir():
            return []

        rel_paths = []
        if recursive:
            for root, _, files in os.walk(target_dir):
                for f in files:
                    full_p = Path(root) / f
                    rel = self.get_relative_path(full_p)
                    rel_paths.append(rel)
        else:
            for entry in target_dir.iterdir():
                if entry.is_file():
                    rel_paths.append(self.get_relative_path(entry))

        return sorted(rel_paths)

    @staticmethod
    def normalize_rel_path(path_str: str) -> str:
        """Normalize path separators."""
        return path_str.replace("\\", "/").lstrip("/")
