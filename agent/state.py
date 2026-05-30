"""
agent/state.py — Conversation and cache state for the PlanningAssistant.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import StockoutRiskOutput


class Intent(Enum):
    STOCKOUT_QUERY = "stockout_query"
    FILTER_CORE    = "filter_core"
    CHANGE_HORIZON = "change_horizon"
    UNKNOWN        = "unknown"


@dataclass
class QueryPlan:
    """
    Structured representation of what the orchestrator intends to do
    before any tool is called.

    An explicit QueryPlan (rather than going straight from intent to tool call)
    enables dynamic tool selection, richer multi-step workflows, and easier
    integration of an LLM-based intent parser — keeping the design principle
    intact: the planner decides, tools compute.
    """
    intent: Intent
    sku_ids: list[str]
    horizon_days: int
    filters: dict[str, Any] = field(default_factory=dict)
    use_cache: bool = False
    reason: str = ""


@dataclass
class ConversationState:
    """
    Per-session state for the PlanningAssistant.

    Cache key: (tuple(sorted_sku_ids), horizon_days) → StockoutRiskOutput.
    Changing the horizon creates a new entry rather than evicting the old one,
    so switching back to 30d reuses the earlier result immediately.
    A production system would use Redis with TTLs.
    """
    last_output: StockoutRiskOutput | None = None
    current_horizon: int = 30
    last_sku_ids: list[str] = field(default_factory=list)
    cache: dict[tuple, StockoutRiskOutput] = field(default_factory=dict)
    turn_count: int = 0

    def cache_key(self, sku_ids: list[str], horizon: int) -> tuple:
        return (tuple(sorted(sku_ids)), horizon)

    def get_cached(self, sku_ids: list[str], horizon: int) -> StockoutRiskOutput | None:
        return self.cache.get(self.cache_key(sku_ids, horizon))

    def store(self, sku_ids: list[str], horizon: int, output: StockoutRiskOutput) -> None:
        key = self.cache_key(sku_ids, horizon)
        self.cache[key] = output
        self.last_output = output
        self.last_sku_ids = list(sku_ids)
        self.current_horizon = horizon


# ── Bonus: LangGraph state ────────────────────────────────────────────────────

class AgentState(TypedDict):
    """State TypedDict for the LangGraph bonus task."""
    messages: list[dict]
    last_user_message: str
    query_plan: dict | None
    resolved_sku_ids: list[str] | None
    horizon_days: int
    active_filters: dict
    cached_inventory: dict | None
    cached_stockout_risk: dict | None
    error_message: str | None
    final_response: str