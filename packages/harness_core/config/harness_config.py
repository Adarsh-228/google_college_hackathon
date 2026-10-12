"""Adaptive Harness configuration structures."""

from typing import List, Optional
from pydantic import BaseModel, Field

from packages.harness_core.contracts.enums import ContextStrategy, HarnessMode


class HarnessConfiguration(BaseModel):
    """Runtime configuration selected for the agent."""
    mode: HarnessMode = Field(HarnessMode.HYBRID, description="Selected harness execution mode.")
    planning_depth: str = Field("adaptive", description="Planning depth: none, lightweight, explicit, adaptive.")
    allowed_tools: List[str] = Field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
            "search_files",
            "run_terminal_command",
        ],
        description="Whitelist of allowed tool names."
    )
    context_strategy: ContextStrategy = Field(
        ContextStrategy.T4_STAGED,
        description="Active context management strategy."
    )
    verify_after_edit: bool = Field(True, description="Run syntax/lint check after file modifications.")
    auto_recover_syntax_errors: bool = Field(True, description="Attempt automated retry if syntax fails.")
    selection_reasoning: str = Field(
        "Default balanced profile.",
        description="Explanation of why this harness configuration was chosen."
    )
