"""
tests/test_agent.py — Bonus task: LangGraph agent tests

NOTE ON MOCKING STRATEGY:
  agent/nodes.py imports the real calculate_stockout_risk from tools.calculate_stockout_risk.
  tools/stubs.py is intentionally preserved as the original project scaffold
  (returns 42% / is_core=True for all SKUs) and is used only by Task B tests.
  Bonus tests mock agent.nodes.calculate_stockout_risk directly so the
  real tool's is_core flags are used for filter tests.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

pytest.importorskip("langgraph", reason="Bonus task — install requirements_bonus.txt to run")

from unittest.mock import patch, call
from tools.calculate_stockout_risk import calculate_stockout_risk as real_tool
from tools.stubs import query_inventory_state as real_inventory
from agent.graph import app
from agent.state import AgentState


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_state(message: str, **overrides) -> dict:
    """Build a minimal initial AgentState for graph invocation."""
    base: dict = {
        "messages": [],
        "last_user_message": message,
        "horizon_days": 30,
        "resolved_sku_ids": None,
        "active_filters": {},
        "cached_inventory": None,
        "cached_stockout_risk": None,
        "query_plan": None,
        "error_message": None,
        "final_response": "",
    }
    base.update(overrides)
    return base


# ── Required test 1: three-turn scenario ─────────────────────────────────────

class TestMultiTurn:

    def test_three_turn_scenario(self):
        """
        Simulate the required 3-turn conversation from the project brief.

        Turn 1: Full stockout query — both tools called, ranked results returned.
        Turn 2: Core filter — tools NOT re-called, cached results filtered.
        Turn 3: Horizon change — calculate_stockout_risk re-called with horizon=60.
        """

        # ── Turn 1 ───────────────────────────────────────────────────────────
        with patch(
            "agent.nodes.calculate_stockout_risk",
            wraps=real_tool,
        ) as mock_risk, patch(
            "agent.nodes.query_inventory_state",
            wraps=real_inventory,
        ) as mock_inv:
            state1 = app.invoke(make_state(
                "Which SKUs are at highest risk of stocking out in the next 30 days?"
            ))

        assert mock_inv.call_count == 1, "Inventory should be called once in Turn 1"
        assert mock_risk.call_count == 1, "Stockout risk should be called once in Turn 1"
        assert "SKU" in state1["final_response"], "Response should contain SKU identifiers"
        assert "%" in state1["final_response"], "Response should contain risk percentages"
        assert state1["cached_stockout_risk"] is not None, (
            "cached_stockout_risk should be populated after Turn 1"
        )

        # ── Turn 2: core filter — tools must NOT re-run ───────────────────
        turn2_state = make_state(
            "Now show me only the core SKUs from that list.",
            cached_stockout_risk=state1["cached_stockout_risk"],
            cached_inventory=state1.get("cached_inventory"),
            horizon_days=state1["horizon_days"],
        )

        with patch(
            "agent.nodes.calculate_stockout_risk",
            wraps=real_tool,
        ) as mock_risk2:
            state2 = app.invoke(turn2_state)

        assert mock_risk2.call_count == 0, (
            "calculate_stockout_risk must NOT be called in Turn 2 (cache reuse)"
        )
        # Non-core SKUs must not appear in response
        for sku in {"SKU-005", "SKU-007", "SKU-008"}:
            assert sku not in state2["final_response"], (
                f"{sku} (non-core) should not appear in Turn 2 core-filter response"
            )

        # ── Turn 3: horizon change — stockout tool must re-run ────────────
        turn3_state = make_state(
            "What would happen if the horizon was 60 days instead?",
            cached_stockout_risk=state1["cached_stockout_risk"],
            cached_inventory=state1.get("cached_inventory"),
            horizon_days=30,
        )

        with patch(
            "agent.nodes.calculate_stockout_risk",
            wraps=real_tool,
        ) as mock_risk3:
            state3 = app.invoke(turn3_state)

        assert mock_risk3.call_count == 1, (
            "calculate_stockout_risk must be re-called in Turn 3 (horizon changed)"
        )
        # Verify it was called with the new horizon
        called_horizon = mock_risk3.call_args.kwargs.get("horizon_days") or \
                         mock_risk3.call_args.args[1]
        assert called_horizon == 60, (
            f"Tool should be called with horizon_days=60, got {called_horizon}"
        )
        assert "60" in state3["final_response"], (
            "Turn 3 response should reference the 60-day horizon"
        )


# ── Required test 2: error handling ──────────────────────────────────────────

class TestErrorHandling:

    def test_tool_error_surfaces_to_user(self):
        """
        RuntimeError from calculate_stockout_risk must produce a clean,
        human-readable response — no traceback, no fabricated data.
        """
        with patch(
            "agent.nodes.calculate_stockout_risk",
            side_effect=RuntimeError("warehouse timeout"),
        ):
            state = app.invoke(make_state("Which SKUs will stock out?"))

        assert state["final_response"] != "", "final_response must not be empty on error"
        assert "Traceback" not in state["final_response"], (
            "Raw Python traceback must not appear in user-facing response"
        )
        assert "RuntimeError" not in state["final_response"], (
            "Raw exception class must not appear in user-facing response"
        )
        error_indicators = ["failed", "unable", "error", "unavailable", "warehouse timeout"]
        assert any(ind in state["final_response"].lower() for ind in error_indicators), (
            "Response should explain the failure in plain language"
        )
        assert "stockout_probability" not in state["final_response"], (
            "Response must not contain fabricated stockout data"
        )

    def test_inventory_error_prevents_stockout_call(self):
        """
        If inventory query fails, calculate_stockout_risk must not be called.
        """
        with patch(
            "agent.nodes.query_inventory_state",
            side_effect=ConnectionError("warehouse unreachable"),
        ), patch(
            "agent.nodes.calculate_stockout_risk",
            wraps=real_tool,
        ) as mock_risk:
            state = app.invoke(make_state("Which SKUs are at risk?"))

        assert mock_risk.call_count == 0, (
            "calculate_stockout_risk must not be called when inventory fails"
        )
        assert state["final_response"] != ""
        assert "Traceback" not in state["final_response"]


# ── Additional tests ──────────────────────────────────────────────────────────

class TestAdditional:

    def test_final_response_populated_on_success(self):
        """Happy path: final_response must be a non-empty, meaningful string."""
        state = app.invoke(make_state(
            "Which SKUs are at highest risk of stocking out in the next 30 days?"
        ))
        assert isinstance(state["final_response"], str)
        assert len(state["final_response"]) > 50, (
            "final_response should be a meaningful multi-line response"
        )

    def test_active_filters_only_show_core_skus(self):
        """
        When is_core filter is active, non-core SKUs must not appear.
        Uses the real tool output so is_core flags are accurate.
        """
        # Run Turn 1 to get real cached results
        state1 = app.invoke(make_state(
            "Which SKUs are at risk in the next 30 days?"
        ))
        # Turn 2: apply core filter
        state2 = app.invoke(make_state(
            "Show me only the core SKUs from that list.",
            cached_stockout_risk=state1["cached_stockout_risk"],
            cached_inventory=state1.get("cached_inventory"),
            horizon_days=30,
        ))
        for non_core in {"SKU-005", "SKU-007", "SKU-008"}:
            assert non_core not in state2["final_response"], (
                f"{non_core} (non-core) must not appear in core-filtered response"
            )

    def test_horizon_persists_in_state_after_change(self):
        """
        After a horizon-change turn, horizon_days in returned state
        should reflect the new value.
        """
        state1 = app.invoke(make_state(
            "Which SKUs are at risk in the next 30 days?"
        ))
        state2 = app.invoke(make_state(
            "What would happen if the horizon was 60 days instead?",
            cached_stockout_risk=state1["cached_stockout_risk"],
            horizon_days=30,
        ))
        assert state2["horizon_days"] == 60, (
            f"horizon_days should be updated to 60, got {state2['horizon_days']}"
        )

    def test_unknown_intent_does_not_crash(self):
        """An unrecognisable query must not raise — graph must complete cleanly."""
        try:
            state = app.invoke(make_state("Hello, what is the weather today?"))
            assert isinstance(state["final_response"], str)
        except Exception as e:
            pytest.fail(f"Graph raised an unexpected exception: {e}")