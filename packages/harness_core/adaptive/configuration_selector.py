"""Adaptive Harness Configuration Selector."""

from typing import List, Optional

from packages.harness_core.adaptive.capability_profiler import CapabilityProfiler
from packages.harness_core.adaptive.recommendations import HarnessRecommendation
from packages.harness_core.adaptive.task_classifier import TaskClassification, TaskClassifier
from packages.harness_core.config.harness_config import HarnessConfiguration
from packages.harness_core.contracts.enums import ContextStrategy, HarnessMode, TaskComplexity


class AdaptiveHarnessSelector:
    """Selects planning depth, tools, and harness mode based on model capabilities and task."""

    @classmethod
    def select_configuration(
        cls,
        model_name: Optional[str],
        task_description: str,
        user_mode_override: Optional[HarnessMode] = None,
        user_strategy_override: Optional[ContextStrategy] = None,
        workspace_file_count: int = 0,
    ) -> HarnessRecommendation:
        capability = CapabilityProfiler.get_profile(model_name)
        classification = TaskClassifier.classify(task_description, workspace_file_count)

        # 1. Check for explicit user override
        if user_mode_override:
            mode = user_mode_override
            is_override = True
            reasoning = f"User explicitly selected harness mode '{mode.value}'."
        else:
            is_override = False
            # Rule-based adaptation based on capability and task
            if classification.primary_category == "inspection":
                mode = HarnessMode.GUIDED
                reasoning = "Read-only inspection task: guided file tools provide strict safety."
            elif classification.involves_terminal_commands and not classification.involves_multi_file_edits and capability.bash_proficiency_score >= 0.8:
                mode = HarnessMode.DIRECT
                reasoning = (
                    f"Task is execution/CLI focused and model '{capability.model_name}' has high "
                    f"bash proficiency ({capability.bash_proficiency_score:.2f}). Selected DIRECT mode."
                )
            elif classification.complexity == TaskComplexity.HIGH or capability.file_tool_fidelity > 0.9:
                mode = HarnessMode.HYBRID
                reasoning = (
                    f"Balanced HYBRID mode selected for {classification.complexity.value} complexity task "
                    f"with model '{capability.model_name}'."
                )
            else:
                mode = capability.recommended_mode
                reasoning = f"Selected recommended mode '{mode.value}' from model capability profile."

        # Planning depth
        if classification.complexity == TaskComplexity.HIGH:
            planning_depth = "explicit"
        elif classification.complexity == TaskComplexity.LOW and mode == HarnessMode.DIRECT:
            planning_depth = "lightweight"
        else:
            planning_depth = "adaptive"

        # Context strategy
        context_strategy = user_strategy_override or ContextStrategy.T4_STAGED

        # Allowed tools based on mode
        if mode == HarnessMode.GUIDED:
            allowed = ["read_file", "write_file", "edit_file", "list_files", "search_files"]
        elif mode == HarnessMode.DIRECT:
            allowed = ["run_terminal_command", "list_files", "read_file"]
        else:
            allowed = [
                "read_file",
                "write_file",
                "edit_file",
                "list_files",
                "search_files",
                "run_terminal_command",
            ]

        config = HarnessConfiguration(
            mode=mode,
            planning_depth=planning_depth,
            allowed_tools=allowed,
            context_strategy=context_strategy,
            verify_after_edit=True,
            auto_recover_syntax_errors=True,
            selection_reasoning=reasoning,
        )

        return HarnessRecommendation(
            configuration=config,
            mode=mode,
            planning_depth=planning_depth,
            context_strategy=context_strategy,
            task_complexity=classification.complexity,
            reasoning=reasoning,
            is_user_override=is_override,
        )
