"""Task analysis module."""

import re
from typing import List, Set
from pydantic import BaseModel, Field


class AnalyzedTask(BaseModel):
    """Detailed structural understanding of user task."""
    original_task: str
    target_languages: List[str] = Field(default_factory=list)
    referenced_files: List[str] = Field(default_factory=list)
    is_rest_api: bool = False
    is_cli: bool = False
    has_test_requirements: bool = False


class TaskAnalyzer:
    """Analyzes task description for domain artifacts, languages, and constraints."""

    @staticmethod
    def analyze(task_text: str) -> AnalyzedTask:
        text_lower = task_text.lower()

        # Languages
        langs: List[str] = []
        if "python" in text_lower or ".py" in text_lower:
            langs.append("python")
        if "typescript" in text_lower or "javascript" in text_lower or ".ts" in text_lower or ".js" in text_lower:
            langs.append("javascript")

        # Referenced files
        file_matches = re.findall(r"\b[\w\-./]+\.(?:py|js|ts|json|md|txt|html|css|yaml|yml)\b", task_text)
        referenced_files = sorted(list(set(file_matches)))

        is_api = any(kw in text_lower for kw in ("api", "rest", "endpoint", "fastapi", "flask"))
        is_cli = any(kw in text_lower for kw in ("cli", "command", "script", "terminal"))
        has_tests = any(kw in text_lower for kw in ("test", "pytest", "unit test", "coverage"))

        return AnalyzedTask(
            original_task=task_text,
            target_languages=langs or ["python"],
            referenced_files=referenced_files,
            is_rest_api=is_api,
            is_cli=is_cli,
            has_test_requirements=has_tests,
        )
