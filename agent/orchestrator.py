"""
agent/orchestrator.py — Task B

Lightweight orchestration layer for the SC Decision Engine.

Demonstrates:
  - QueryPlan-based intent resolution (planner decides, tools compute)
  - Tool sequencing (inventory always before stockout calculation)
  - State persistence across turns
  - Cache reuse (Turn 2: filter without re-running tools)
  - Cache invalidation (Turn 3: horizon change triggers fresh run)
  - Graceful error handling (RuntimeError surfaces cleanly, no stack trace)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state import ConversationState, Intent, QueryPlan
from tools.stubs import query_inventory_state
from tools.calculate_stockout_risk import calculate_stockout_risk as _real_stockout_risk
from models import StockoutRiskOutput
from utils.intent_parser import parse_intent


class PlanningAssistant:
    """
    Stateful orchestration layer for supply chain planning workflows.

    The orchestrator's job is to:
      1. Convert natural language → QueryPlan (via parse_intent)
      2. Decide whether cached results satisfy the plan
      3. Call tools in the correct sequence when fresh data is needed
      4. Format a planner-friendly response

    The orchestrator does NOT perform any computation itself.
    All numbers come from the tools.
    """

    def __init__(self):
        self.state = ConversationState()

    # ── Public API ────────────────────────────────────────────────────────────

    def handle_query(self, user_message: str) -> str:
        self.state.turn_count += 1

        # Build a structured plan before touching any tool
        plan = parse_intent(
            user_message,
            current_horizon=self.state.current_horizon,
            has_prior_results=self.state.last_output is not None,
        )

        if plan.intent == Intent.FILTER_CORE:
            return self._execute_filter(plan)

        if plan.intent == Intent.CHANGE_HORIZON:
            return self._execute_stockout_query(plan)

        if plan.intent == Intent.STOCKOUT_QUERY:
            # Check cache first — avoid recomputing identical queries
            cached = self.state.get_cached(plan.sku_ids, plan.horizon_days)
            if cached:
                plan.use_cache = True
                plan.reason = (
                    f"Cache hit for {plan.horizon_days}-day horizon. "
                    "Returning cached results without re-running tools."
                )
                self.state.last_output = cached
                return self._format_results(cached, plan)
            return self._execute_stockout_query(plan)

        return (
            "I can help with stockout risk analysis. "
            "Try: 'Which SKUs are at highest risk in the next 30 days?' "
            "or 'Show me only core SKUs' after an initial query."
        )

    # ── Plan execution ────────────────────────────────────────────────────────

    def _execute_stockout_query(self, plan: QueryPlan) -> str:
        """
        Full tool pipeline: inventory query → stockout simulation.
        Tool sequencing is enforced here — inventory always comes first.
        """
        # Step 1: always query inventory before stockout calculation
        try:
            query_inventory_state(sku_ids=plan.sku_ids)
        except Exception as e:
            return (
                f"Unable to fetch inventory state: {e}. "
                "Cannot proceed with stockout analysis."
            )

        # Step 2: run stockout simulation
        try:
            output = _real_stockout_risk(plan.sku_ids, plan.horizon_days)
        except RuntimeError as e:
            # Surface cleanly — no raw exception type, no stack trace
            return (
                f"Stockout risk calculation failed: {e}. "
                "Please verify fixture data and retry."
            )
        except Exception as e:
            return (
                f"An unexpected error occurred during analysis "
                f"({type(e).__name__}). Please retry."
            )

        # Persist to cache and state
        self.state.store(plan.sku_ids, plan.horizon_days, output)
        return self._format_results(output, plan)

    def _execute_filter(self, plan: QueryPlan) -> str:
        """
        Filter cached results by is_core. Never re-runs tools.
        This is the Turn 2 behavior: cache reuse without recalculation.
        """
        if self.state.last_output is None:
            return (
                "No previous results to filter. "
                "Please run a stockout risk query first."
            )

        core_results = [
            r for r in self.state.last_output.results
            if r.is_core
        ]
        if not core_results:
            return "No core SKUs found in the previous results."

        lines = [
            f"Core SKUs from cached results "
            f"(horizon = {self.state.current_horizon} days, no recalculation):",
            "",
        ]
        lines.append(
            f"{'SKU':<10} {'Name':<28} {'Risk %':>7}  {'Tier':<8}  {'Days supply':>11}"
        )
        lines.append("-" * 70)
        for r in core_results:
            lines.append(
                f"{r.sku_id:<10} {r.sku_name:<28} "
                f"{r.stockout_probability * 100:6.1f}%  "
                f"{r.risk_tier:<8}  {r.days_of_supply:>8.1f}d"
            )
        return "\n".join(lines)

    # ── Formatting ────────────────────────────────────────────────────────────

    def _format_results(self, output: StockoutRiskOutput, plan: QueryPlan) -> str:
        cache_note = " (cached)" if plan.use_cache else ""
        lines = [
            f"Stockout risk — {output.horizon_days}-day horizon{cache_note}",
            output.summary,
            "",
            f"{'SKU':<10} {'Name':<28} {'Risk %':>7}  {'Tier':<8}  {'Days supply':>11}  {'Core':>6}",
            "-" * 76,
        ]
        for r in output.results:
            core_flag = "YES" if r.is_core else "-"
            lines.append(
                f"{r.sku_id:<10} {r.sku_name:<28} "
                f"{r.stockout_probability * 100:6.1f}%  "
                f"{r.risk_tier:<8}  {r.days_of_supply:>8.1f}d  "
                f"{core_flag:>6}"
            )
        return "\n".join(lines)