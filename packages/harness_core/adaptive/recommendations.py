"""Recommendation data structures for adaptive harness."""

from typing import List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.config.harness_config import HarnessConfiguration
from packages.harness_core.contracts.enums import ContextStrategy, HarnessMode, TaskComplexity


class HarnessRecommendation(BaseModel):
    """Explicit recommendation payload returned by selector."""
    configuration: HarnessConfiguration
    mode: HarnessMode
    planning_depth: str
    context_strategy: ContextStrategy
    task_complexity: TaskComplexity
    reasoning: str
    is_user_override: bool = False
