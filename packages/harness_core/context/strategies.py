"""Implementations of T0 through T4 context management strategies."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Tuple

from packages.harness_core.contracts.enums import ContextStrategy
from packages.harness_core.providers.base import LLMMessage

if TYPE_CHECKING:
    from packages.harness_core.context.manager import ContextManager


class BaseStrategyHandler(ABC):
    """Base interface for a context management strategy."""

    @abstractmethod
    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        pass


class T0NoneHandler(BaseStrategyHandler):
    """T0: No context management. Pass full raw history."""

    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        return list(messages)


class T1ElisionHandler(BaseStrategyHandler):
    """T1: Rule-based elision of bulky tool observations."""

    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        pruned, saved_chars = manager.elider.elide(
            messages, recent_window_size=manager.recent_window_size
        )
        if saved_chars > 0:
            manager.stats.elided_count += 1
            manager.stats.tokens_saved_estimate += saved_chars // 4
        return pruned


class T2RecallHandler(BaseStrategyHandler):
    """T2: Rule-based elision with external recall index."""

    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        # Same as T1, but keeps recall store indexed in manager.elider.recall_store
        pruned, saved_chars = manager.elider.elide(
            messages, recent_window_size=manager.recent_window_size
        )
        if saved_chars > 0:
            manager.stats.elided_count += 1
            manager.stats.tokens_saved_estimate += saved_chars // 4
        return pruned


class T3SummarizationHandler(BaseStrategyHandler):
    """T3: LLM-based rolling summarization of middle turns."""

    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        if len(messages) <= manager.recent_window_size + 2:
            return list(messages)

        # Preserve Turn 0 (or system + Turn 0) and last N messages
        first_idx = 1 if messages[0].role == "system" else 0
        preserved_head = messages[: first_idx + 1]
        preserved_tail = messages[-manager.recent_window_size :]

        # Middle messages to compress
        middle = messages[first_idx + 1 : -manager.recent_window_size]
        if not middle:
            return list(messages)

        goal = preserved_head[-1].content
        summary_text = await manager.summarizer.summarize_history(middle, goal)
        summary_msg = LLMMessage(
            role="user",
            content=f"[SYSTEM CONTEXT COMPRESSION]:\n{summary_text}",
            metadata={"is_summary": True},
        )

        manager.stats.summarized_count += 1
        return preserved_head + [summary_msg] + preserved_tail


class T4StagedHandler(BaseStrategyHandler):
    """T4: Staged rule-based elision followed by LLM summarization if still over threshold."""

    async def process(
        self,
        messages: List[LLMMessage],
        manager: "ContextManager",
    ) -> List[LLMMessage]:
        tokens = await manager.tokenizer.count_tokens(messages)
        utilization = tokens / max(1, manager.window_limit)

        current_messages = list(messages)

        # Stage 1: Soft threshold reached -> Trigger rule-based elision
        if utilization >= manager.soft_threshold:
            pruned, saved_chars = manager.elider.elide(
                current_messages, recent_window_size=manager.recent_window_size
            )
            if saved_chars > 0:
                manager.stats.elided_count += 1
                manager.stats.tokens_saved_estimate += saved_chars // 4
            current_messages = pruned

            # Recalculate utilization after elision
            tokens = await manager.tokenizer.count_tokens(current_messages)
            utilization = tokens / max(1, manager.window_limit)

        # Stage 2: Hard threshold reached -> Trigger LLM summarization
        if utilization >= manager.hard_threshold:
            t3 = T3SummarizationHandler()
            current_messages = await t3.process(current_messages, manager)

        return current_messages
