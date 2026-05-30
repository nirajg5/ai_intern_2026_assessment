"""
utils/intent_parser.py — Deterministic keyword-based intent parser.

Returns a QueryPlan struct rather than a raw Intent enum. This separation
means the orchestrator never needs to know how intent was detected — it
simply acts on the plan. A future LLM-based parser would produce the same
QueryPlan output, making the swap transparent to the rest of the system.

Documented tradeoff: keyword matching is brittle for ambiguous phrasing
but adds zero latency and zero API dependency during evaluation.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent.state import Intent, QueryPlan

# All SKUs known to the system. In production this would be fetched
# dynamically from the inventory service.
ALL_KNOWN_SKUS = [
    "SKU-001", "SKU-002", "SKU-003", "SKU-004",
    "SKU-005", "SKU-006", "SKU-007", "SKU-008",
]

_STOCKOUT_KEYWORDS = frozenset([
    "stock", "stockout", "risk", "out of stock", "run out",
    "deplete", "shortage", "at risk", "highest risk",
])

_HORIZON_CHANGE_KEYWORDS = frozenset([
    "horizon", "what if", "instead", "change", "if the", "if it was",
    "suppose", "scenario",
])


def parse_intent(
    user_message: str,
    current_horizon: int = 30,
    has_prior_results: bool = False,
) -> QueryPlan:
    """
    Parse a natural-language planning query into a structured QueryPlan.

    Priority order (to avoid mis-classification):
      1. Horizon change — detected first so "what if 60 days" doesn't
         fall through to STOCKOUT_QUERY with the wrong horizon.
      2. Core filter — only valid when prior results exist.
      3. Stockout query — general risk analysis request.
      4. Unknown — surfaces gracefully rather than hallucinating.
    """
    lower = user_message.lower()
    # Extract SKU IDs if explicitly mentioned
    mentioned_skus = re.findall(r"SKU-\d{3}", user_message.upper())
    sku_ids = (
    [sku.upper() for sku in mentioned_skus]
    if mentioned_skus
    else ALL_KNOWN_SKUS
    )

    # Extract horizon mention (e.g. "30 days", "60-day")
    horizon_match = re.search(r"\b(\d{1,3})\s*-?\s*day", lower)
    mentioned_horizon = int(horizon_match.group(1)) if horizon_match else None

    # 1. Horizon change: user mentioned a different horizon AND used change language
    if (
        mentioned_horizon is not None
        and mentioned_horizon != current_horizon
        and any(kw in lower for kw in _HORIZON_CHANGE_KEYWORDS)
    ):
        return QueryPlan(
            intent=Intent.CHANGE_HORIZON,
            sku_ids=ALL_KNOWN_SKUS,
            horizon_days=mentioned_horizon,
            use_cache=False,
            reason=(
                f"User requested horizon change from {current_horizon}d "
                f"to {mentioned_horizon}d. Cache invalidated for new horizon."
            ),
        )

    # 2. Core filter: "core" + prior results exist
    if "core" in lower and has_prior_results:
        return QueryPlan(
            intent=Intent.FILTER_CORE,
            sku_ids=sku_ids,
            horizon_days=current_horizon,
            filters={"is_core": True},
            use_cache=True,
            reason="Filtering cached results for core SKUs only. No tool re-run needed.",
        )

    # 3. Stockout query
    if any(kw in lower for kw in _STOCKOUT_KEYWORDS):
        horizon = mentioned_horizon if mentioned_horizon else current_horizon
        return QueryPlan(
            intent=Intent.STOCKOUT_QUERY,
            sku_ids=sku_ids,
            horizon_days=horizon,
            use_cache=False,
            reason=f"Stockout risk analysis requested for {horizon}-day horizon.",
        )

    # 4. Unknown — surface cleanly
    return QueryPlan(
        intent=Intent.UNKNOWN,
        sku_ids=[],
        horizon_days=current_horizon,
        reason="Could not determine intent from user message.",
    )