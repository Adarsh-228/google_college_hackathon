from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

class CircuitBreakerError(Exception):
    """Raised when an identical tool call streak violates circuit breaker constraints."""
    pass

class ContextOverflowError(Exception):
    """Raised when context exceeds budget without management enabled (T0)."""
    pass

@dataclass
class HarnessConfig:
    # AgentGuard toggles
    enable_rbw: bool = True
    enable_lint: bool = True
    enable_streak_breaker: bool = True
    
    # Context Management toggles
    context_tier: str = "T4"  # T0 (none), T1 (elision), T2 (elision+recall), T3 (summary), T4 (staged)
    budget_cap: int = 32768
    enable_m2: bool = False   # Recoverable external storage (recall_event)
    
    # Paper-grounded constants (§2.3 / §3.1)
    soft_threshold_ratio: float = 0.60   # B1
    hard_threshold_ratio: float = 0.85   # B2
    recent_window_ratio: float = 0.30
    min_recent_turns: int = 2
    max_tool_output_chars: int = 24000
    
    # Action space & planning
    tool_mode: str = "predefined"        # "predefined" | "bash_only"
    enable_planning: bool = True
    max_turns: int = 40

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "HarnessConfig":
        if not data:
            return cls()
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

@dataclass
class TurnEvent:
    turn_idx: int
    type: str  # "TURN_START" | "TOOL_CALL" | "TOOL_RESULT" | "GUARD_EVENT" | "COMPACTION" | "PLAN_UPDATE" | "RUN_FINISH" | "ERROR"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_idx": self.turn_idx,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
        }

@dataclass
class RunResult:
    run_id: str
    task_id: str
    resolved: bool
    stop_reason: str  # "RESOLVED" | "MAX_TURNS" | "CONTEXT_OVERFLOW" | "CIRCUIT_BREAKER_STUCK" | "ERROR"
    total_turns: int
    total_cost_usd: float
    tokens_in_uncached: int
    tokens_in_cached: int
    tokens_out: int
    m1_count: int = 0
    m3_count: int = 0
    guard_events_count: int = 0
    re_patch_count: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "resolved": self.resolved,
            "stop_reason": self.stop_reason,
            "total_turns": self.total_turns,
            "total_cost_usd": self.total_cost_usd,
            "tokens_in_uncached": self.tokens_in_uncached,
            "tokens_in_cached": self.tokens_in_cached,
            "tokens_out": self.tokens_out,
            "m1_count": self.m1_count,
            "m3_count": self.m3_count,
            "guard_events_count": self.guard_events_count,
            "re_patch_count": self.re_patch_count,
            "metrics": self.metrics,
        }
