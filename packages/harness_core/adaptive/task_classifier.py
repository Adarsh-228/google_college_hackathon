"""Task complexity and type classification."""

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import TaskComplexity


class TaskClassification(BaseModel):
    """Result of task linguistic and structural analysis."""
    complexity: TaskComplexity
    primary_category: str  # feature, bugfix, refactor, inspection, test
    estimated_steps: int
    involves_terminal_commands: bool
    involves_multi_file_edits: bool
    summary: str


class TaskClassifier:
    """Classifies user tasks to inform harness mode and planning depth."""

    TERMINAL_KEYWORDS = [
        "run", "execute", "install", "test", "build", "pip", "pytest", "npm", "start", "docker"
    ]
    MULTI_FILE_KEYWORDS = [
        "refactor", "across", "architecture", "entire", "all files", "module", "restructure"
    ]
    HIGH_COMPLEXITY_KEYWORDS = [
        "full-stack", "async", "distributed", "database", "migration", "architecture",
        "redesign", "security", "framework", "performance", "benchmark"
    ]

    @classmethod
    def classify(
        cls,
        task_description: str,
        workspace_file_count: int = 0,
    ) -> TaskClassification:
        text = task_description.lower()

        # Terminal necessity
        involves_terminal = any(re.search(rf"\b{kw}\b", text) for kw in cls.TERMINAL_KEYWORDS)
        # Multi-file scope
        involves_multi_file = (
            workspace_file_count > 10
            or any(re.search(rf"\b{kw}\b", text) for kw in cls.MULTI_FILE_KEYWORDS)
        )

        # Complexity determination
        high_matches = sum(1 for kw in cls.HIGH_COMPLEXITY_KEYWORDS if re.search(rf"\b{kw}\b", text))
        if high_matches >= 2 or involves_multi_file and len(text) > 300:
            complexity = TaskComplexity.HIGH
            estimated_steps = 7
        elif high_matches == 1 or len(text) > 100 or involves_multi_file:
            complexity = TaskComplexity.MEDIUM
            estimated_steps = 4
        else:
            complexity = TaskComplexity.LOW
            estimated_steps = 2

        # Primary category
        if any(w in text for w in ("fix", "bug", "issue", "error", "broken")):
            category = "bugfix"
        elif any(w in text for w in ("refactor", "clean", "restructure")):
            category = "refactor"
        elif any(w in text for w in ("test", "pytest", "verify")):
            category = "test"
        elif any(w in text for w in ("show", "list", "read", "find", "search")):
            category = "inspection"
        else:
            category = "feature"

        summary = (
            f"Classified as {complexity.value} complexity ({category}), "
            f"estimated ~{estimated_steps} steps."
        )

        return TaskClassification(
            complexity=complexity,
            primary_category=category,
            estimated_steps=estimated_steps,
            involves_terminal_commands=involves_terminal,
            involves_multi_file_edits=involves_multi_file,
            summary=summary,
        )
