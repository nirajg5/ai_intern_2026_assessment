"""
agent/nodes.py — LangGraph graph nodes (Bonus Task)

Each node takes AgentState and returns a dict of state updates.
LangGraph merges the returned dict into the current state automatically.

Design principle: nodes are thin wrappers. They decide WHAT to do
(should I use cache? which tool? which filter?) but delegate all
computation to tools. This keeps the LLM-plans / tools-compute
separation intact even inside a graph.

NOTE ON IMPORTS:
  Nodes import from tools.calculate_stockout_risk (the real Task A tool)
  and tools.stubs.query_inventory_state.
  The stubs.py file is intentionally left as the original project scaffold
  (returning 42% for all SKUs) — it is used by Task B orchestrator tests.
  The bonus graph uses the real simulation tool so results are meaningful.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.stubs import query_inventory_state
from tools.calculate_stockout_risk import calculate_stockout_risk
from agent.state import AgentState

ALL_KNOWN_SKUS = [
    "SKU-001", "SKU-002", "SKU-003", "SKU-004",
    "SKU-005", "SKU-006", "SKU-007", "SKU-008",
]

_STOCKOUT_KEYWORDS = frozenset([
    "stock", "stockout", "risk", "out of stock", "run out",
    "deplete", "shortage", "at risk", "highest risk",
])

_HORIZON_CHANGE_KEYWORDS = frozenset([
    "horizon", "what if", "instead", "change", "if the",
    "suppose", "scenario", "would happen",
])


# ── Node: parse_intent ────────────────────────────────────────────────────────

def parse_intent(state: AgentState) -> dict:
    """
    Convert the latest user message into a structured query plan stored in state.

    Uses deterministic keyword parsing — no API key required.
    A real system would call an LLM here; the output contract
    (resolved_sku_ids, horizon_days, active_filters, query_plan)
    would be identical — keeping the design principle intact:
    the LLM plans, tools compute.

    Returns state updates: resolved_sku_ids, horizon_days,
    active_filters, query_plan, error_message (cleared).
    """
    msg = state.get("last_user_message", "").lower()
    current_horizon = state.get("horizon_days", 30)
    has_prior = state.get("cached_stockout_risk") is not None

    # Extract horizon mention e.g. "60 days", "60-day"
    horizon_match = re.search(r"\b(\d{1,3})\s*-?\s*day", msg)
    mentioned_horizon = int(horizon_match.group(1)) if horizon_match else None

    # Priority 1: horizon change — must check before stockout_query
    # so "what if 60 days" doesn't fall through with wrong horizon
    if (
        mentioned_horizon is not None
        and mentioned_horizon != current_horizon
        and any(kw in msg for kw in _HORIZON_CHANGE_KEYWORDS)
    ):
        intent = "change_horizon"
        new_horizon = mentioned_horizon
        filters = {}

    # Priority 2: core filter — only valid when prior results exist
    elif "core" in msg and has_prior:
        intent = "filter_core"
        new_horizon = current_horizon
        filters = {"is_core": True}

    # Priority 3: general stockout query
    elif any(kw in msg for kw in _STOCKOUT_KEYWORDS):
        intent = "stockout_query"
        new_horizon = mentioned_horizon if mentioned_horizon else current_horizon
        filters = {}

    else:
        intent = "unknown"
        new_horizon = current_horizon
        filters = {}

    plan = {
        "intent": intent,
        "sku_ids": ALL_KNOWN_SKUS,
        "horizon_days": new_horizon,
        "filters": filters,
    }

    return {
        "resolved_sku_ids": ALL_KNOWN_SKUS,
        "horizon_days": new_horizon,
        "active_filters": filters,
        "query_plan": plan,
        "error_message": None,   # clear any prior error at turn start
    }


# ── Node: call_inventory ──────────────────────────────────────────────────────

def call_inventory(state: AgentState) -> dict:
    """
    Call query_inventory_state with resolved SKUs.

    Cache reuse: skip if intent is filter_core and cache already populated.
    Tool sequencing invariant: always runs before call_stockout_risk.
    """
    sku_ids = state.get("resolved_sku_ids") or ALL_KNOWN_SKUS
    intent = (state.get("query_plan") or {}).get("intent", "stockout_query")

    # Filter-only turn — no inventory refresh needed
    if intent == "filter_core" and state.get("cached_inventory") is not None:
        return {}

    try:
        result = query_inventory_state(sku_ids=sku_ids)
        return {"cached_inventory": result}
    except Exception as e:
        return {"error_message": f"Inventory query failed: {e}"}


# ── Node: call_stockout_risk ──────────────────────────────────────────────────

def call_stockout_risk(state: AgentState) -> dict:
    """
    Call calculate_stockout_risk, respecting cache.

    Re-runs when:
      - No cached result exists
      - horizon_days changed since last run
      - resolved_sku_ids changed

    Reuses cache when:
      - intent == filter_core (Turn 2: no re-run)
      - Same SKUs + same horizon as cached result
    """
    intent = (state.get("query_plan") or {}).get("intent", "stockout_query")
    sku_ids = state.get("resolved_sku_ids") or ALL_KNOWN_SKUS
    horizon = state.get("horizon_days", 30)
    cached = state.get("cached_stockout_risk")

    # Turn 2: core filter — reuse cached result, never re-run
    if intent == "filter_core" and cached is not None:
        return {}

    # Cache hit: same horizon and same SKU set
    if (
        cached is not None
        and cached.get("horizon_days") == horizon
        and set(cached.get("sku_ids", [])) == set(sku_ids)
    ):
        return {}

    # Cache miss or assumptions changed — run the real tool
    try:
        result = calculate_stockout_risk(sku_ids=sku_ids, horizon_days=horizon)
        # Serialise the Pydantic output to dict for state storage
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        else:
            result_dict = dict(result)
        # Attach metadata for future cache-hit checks
        result_dict["horizon_days"] = horizon
        result_dict["sku_ids"] = sku_ids
        return {"cached_stockout_risk": result_dict}
    except RuntimeError as e:
        return {"error_message": f"Stockout calculation failed: {e}"}
    except Exception as e:
        return {"error_message": f"Unexpected error ({type(e).__name__}): {e}"}


# ── Node: synthesise ──────────────────────────────────────────────────────────

def synthesise(state: AgentState) -> dict:
    """
    Build the final planner-facing response from tool outputs in state.

    Applies active_filters, formats a ranked table, appends the summary.
    Never performs computation — only formats what tools already produced.
    """
    risk_data = state.get("cached_stockout_risk") or {}
    results = risk_data.get("results", [])
    horizon = state.get("horizon_days", 30)
    filters = state.get("active_filters") or {}

    # Apply is_core filter (Turn 2 behavior)
    if filters.get("is_core"):
        results = [r for r in results if r.get("is_core")]
        filter_note = " (core SKUs only, cached — no recalculation)"
    else:
        filter_note = ""

    if not results:
        return {"final_response": "No SKUs matched the current filters."}

    # Sort highest risk first
    results = sorted(
        results,
        key=lambda r: r.get("stockout_probability", 0),
        reverse=True,
    )

    lines = [
        f"Stockout risk — {horizon}-day horizon{filter_note}",
        "",
        f"{'SKU':<10} {'Name':<28} {'Risk %':>7}  {'Tier':<8}  {'Core':>6}",
        "-" * 64,
    ]
    for r in results:
        prob = r.get("stockout_probability", 0)
        tier = r.get("risk_tier", _prob_to_tier(prob))
        core = "YES" if r.get("is_core") else "-"
        name = r.get("sku_name", r.get("sku_id", "?"))
        lines.append(
            f"{r.get('sku_id','?'):<10} {name:<28} "
            f"{prob * 100:6.1f}%  {tier:<8}  {core:>6}"
        )

    summary = risk_data.get("summary", "")
    if summary:
        lines += ["", summary]

    return {"final_response": "\n".join(lines)}


def _prob_to_tier(prob: float) -> str:
    if prob >= 0.60: return "HIGH"
    if prob >= 0.30: return "MEDIUM"
    if prob >= 0.10: return "LOW"
    return "SAFE"


# ── Node: handle_error ────────────────────────────────────────────────────────

def handle_error(state: AgentState) -> dict:
    """
    Surface a tool failure cleanly to the user.

    Rules enforced:
    - No Python traceback in the response
    - No fabricated stockout data
    - Plain English explanation of what failed
    """
    error = state.get("error_message") or "An unknown error occurred."
    response = (
        f"Unable to complete the analysis: {error} "
        "Please check the data sources and retry. "
        "No stockout estimates have been generated for this query."
    )
    return {"final_response": response}