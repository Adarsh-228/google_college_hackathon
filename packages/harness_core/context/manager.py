"""ContextT4 Context Manager orchestrating context lifecycle."""

from typing import Dict, List, Optional

from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import ContextStrategy
from packages.harness_core.contracts.responses import ContextStatistics
from packages.harness_core.context.elision import RuleBasedElider
from packages.harness_core.context.strategies import (
    BaseStrategyHandler,
    T0NoneHandler,
    T1ElisionHandler,
    T2RecallHandler,
    T3SummarizationHandler,
    T4StagedHandler,
)
from packages.harness_core.context.summarizer import ContextSummarizer
from packages.harness_core.context.tokenizer import ContextTokenizer
from packages.harness_core.providers.base import BaseLLMProvider, LLMMessage


class ContextManager:
    """Manages context lifecycle, token measurement, elision, and summarization."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        strategy: ContextStrategy = ContextStrategy.T4_STAGED,
        soft_threshold: float = 0.60,
        hard_threshold: float = 0.85,
        window_limit: int = 128000,
        recent_window_size: int = 4,
    ) -> None:
        self.provider = provider
        self.strategy = strategy
        self.soft_threshold = soft_threshold
        self.hard_threshold = hard_threshold
        self.window_limit = window_limit
        self.recent_window_size = recent_window_size

        self.tokenizer = ContextTokenizer(provider)
        self.elider = RuleBasedElider(max_observation_chars=300)
        self.summarizer = ContextSummarizer(provider)

        self.stats = ContextStatistics(
            total_tokens=0,
            window_limit=self.window_limit,
            utilization_pct=0.0,
            elided_count=0,
            summarized_count=0,
            tokens_saved_estimate=0,
            is_estimated=not self.tokenizer.is_exact(),
        )

        self._handlers: Dict[ContextStrategy, BaseStrategyHandler] = {
            ContextStrategy.T0_NONE: T0NoneHandler(),
            ContextStrategy.T1_ELISION: T1ElisionHandler(),
            ContextStrategy.T2_RECALL: T2RecallHandler(),
            ContextStrategy.T3_SUMMARIZATION: T3SummarizationHandler(),
            ContextStrategy.T4_STAGED: T4StagedHandler(),
        }

    async def prepare_context(self, messages: List[LLMMessage]) -> List[LLMMessage]:
        """Apply active context strategy to return optimal context for model invocation."""
        handler = self._handlers.get(self.strategy, self._handlers[ContextStrategy.T4_STAGED])
        processed = await handler.process(messages, self)

        # Update final statistics
        tokens = await self.tokenizer.count_tokens(processed)
        self.stats.total_tokens = tokens
        self.stats.utilization_pct = min(1.0, tokens / max(1, self.window_limit))
        self.stats.is_estimated = not self.tokenizer.is_exact()

        return processed

    def get_statistics(self) -> ContextStatistics:
        """Return current context statistics."""
        return self.stats.model_copy()

    @classmethod
    def from_config(
        cls,
        config: EngineConfig,
        provider: Optional[BaseLLMProvider] = None,
        strategy_override: Optional[ContextStrategy] = None,
    ) -> "ContextManager":
        """Instantiate ContextManager from EngineConfig."""
        return cls(
            provider=provider,
            strategy=strategy_override or config.context_strategy,
            soft_threshold=config.context_soft_threshold,
            hard_threshold=config.context_hard_threshold,
            window_limit=config.context_window_limit,
        )
