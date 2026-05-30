"""
tests/test_orchestrator.py — Task B tests

Covers the required 3-turn conversation scenario plus error handling.

Turn 1: full analysis — tools called, results returned
Turn 2: core filter — cache reused, tools NOT re-run
Turn 3: horizon change — cache invalidated, tools re-run with new horizon
Error:  RuntimeError surfaces as clean message, no stack trace exposed
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.orchestrator import PlanningAssistant
from agent.state import Intent
from utils.intent_parser import parse_intent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def fresh() -> PlanningAssistant:
    return PlanningAssistant()


# ---------------------------------------------------------------------------
# Turn 1 — full stockout query
# ---------------------------------------------------------------------------

def test_turn1_returns_ranked_stockout_results():
    """Turn 1: orchestrator calls tools and returns ranked results."""
    a = fresh()
    result = a.handle_query("Which SKUs are at highest risk of stocking out in the next 30 days?")

    assert "SKU" in result, "Response should include SKU identifiers"
    assert "%" in result, "Response should include probability percentages"
    assert a.state.last_output is not None, "State should have a stored output after Turn 1"
    assert a.state.last_output.skus_evaluated > 0
    assert a.state.current_horizon == 30


def test_turn1_populates_cache():
    """After Turn 1, the cache should have exactly one entry."""
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    assert len(a.state.cache) == 1


def test_turn1_tool_sequence_inventory_before_stockout(monkeypatch):
    """
    Inventory must be queried before stockout calculation.
    If inventory fails, stockout must NOT be called.
    """
    call_order = []

    def fake_inventory(**kwargs):
        call_order.append("inventory")
        return {"status": "success", "sku_ids": kwargs.get("sku_ids", [])}

    def fake_stockout(sku_ids, horizon_days):
        call_order.append("stockout")
        from tools.calculate_stockout_risk import calculate_stockout_risk as real
        return real(sku_ids, horizon_days)

    monkeypatch.setattr("agent.orchestrator.query_inventory_state", fake_inventory)
    monkeypatch.setattr("agent.orchestrator._real_stockout_risk", fake_stockout)

    a = fresh()
    a.handle_query("Which SKUs are at risk?")

    assert call_order[0] == "inventory", "Inventory must be called first"
    assert "stockout" in call_order, "Stockout must be called after inventory"
    assert call_order.index("inventory") < call_order.index("stockout")


# ---------------------------------------------------------------------------
# Turn 2 — core filter (cache reuse)
# ---------------------------------------------------------------------------

def test_turn2_core_filter_uses_cache_not_tools():
    """
    Turn 2: filtering for core SKUs must reuse cached results.
    The cache must not grow (no new tool run).
    """
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    cache_after_turn1 = dict(a.state.cache)

    result = a.handle_query("Now show me only the core SKUs from that list.")

    assert a.state.cache == cache_after_turn1, (
        "Cache must not change on a filter query — no re-run should occur"
    )
    assert "core" in result.lower() or "CORE" in result, (
        "Response should reference core SKUs"
    )


def test_turn2_core_filter_only_shows_core_skus():
    """Core filter result must contain only is_core=True SKUs."""
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    result = a.handle_query("Show me only the core SKUs.")

    # All SKUs in the fixture with is_core=True
    core_ids = {"SKU-001", "SKU-002", "SKU-003", "SKU-004", "SKU-006"}
    non_core_ids = {"SKU-005", "SKU-007", "SKU-008"}

    for non_core in non_core_ids:
        assert non_core not in result, (
            f"{non_core} (non-core) should not appear in core-filter results"
        )


def test_turn2_without_prior_results_gives_helpful_message():
    """Filtering before any query should not crash — return a helpful message."""
    a = fresh()
    result = a.handle_query("Show me only the core SKUs.")
    assert "query" in result.lower() or "first" in result.lower() or "no previous" in result.lower()


# ---------------------------------------------------------------------------
# Turn 3 — horizon change (cache invalidation)
# ---------------------------------------------------------------------------

def test_turn3_horizon_change_creates_new_cache_entry():
    """
    Turn 3: changing the horizon must NOT reuse the 30d cache entry.
    A new entry must be created for the 60d results.
    Both entries should exist after Turn 3 (old cache preserved).
    """
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    assert len(a.state.cache) == 1

    a.handle_query("What would happen if the horizon was 60 days instead?")

    assert a.state.current_horizon == 60, "Horizon should be updated to 60"
    assert len(a.state.cache) == 2, (
        "Both 30d and 60d cache entries should exist after horizon change"
    )


def test_turn3_old_cache_preserved_after_horizon_change():
    """
    The 30-day cache entry should still be valid after switching to 60 days.
    Switching back to 30 days should not re-run tools.
    """
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    key_30 = a.state.cache_key(a.state.last_sku_ids, 30)

    a.handle_query("What if the horizon was 60 days instead?")

    assert key_30 in a.state.cache, (
        "30-day cache entry must be preserved after switching to 60-day horizon"
    )


def test_turn3_result_reflects_new_horizon():
    """Turn 3 result should reference the new horizon, not the old one."""
    a = fresh()
    a.handle_query("Which SKUs are at risk in the next 30 days?")
    result = a.handle_query("What would happen if the horizon was 60 days instead?")
    assert "60" in result, "Response should reference the 60-day horizon"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_runtime_error_surfaces_clean_message():
    """
    RuntimeError from calculate_stockout_risk must produce a clean message.
    No raw exception type, no Traceback, no stack trace in the response.
    """
    a = fresh()
    with patch(
        "agent.orchestrator._real_stockout_risk",
        side_effect=RuntimeError("Fixture file missing"),
    ):
        result = a.handle_query("Which SKUs are at risk?")

    assert len(result) > 0, "Should return a non-empty error message"
    assert "Traceback" not in result, "Raw traceback must not be exposed to user"
    assert "RuntimeError" not in result, "Raw exception class must not be exposed"
    assert any(w in result.lower() for w in ("failed", "error", "unable", "cannot")), (
        "Error message should use plain language"
    )


def test_inventory_failure_prevents_stockout_call(monkeypatch):
    """
    If inventory query raises, stockout must not be called.
    The response should explain the failure cleanly.
    """
    stockout_called = []

    def fail_inventory(**kwargs):
        raise ConnectionError("Warehouse unreachable")

    def track_stockout(sku_ids, horizon_days):
        stockout_called.append(True)
        from tools.calculate_stockout_risk import calculate_stockout_risk as real
        return real(sku_ids, horizon_days)

    monkeypatch.setattr("agent.orchestrator.query_inventory_state", fail_inventory)
    monkeypatch.setattr("agent.orchestrator._real_stockout_risk", track_stockout)

    a = fresh()
    result = a.handle_query("Which SKUs are at risk?")

    assert not stockout_called, "Stockout should not be called if inventory fails"
    assert "inventory" in result.lower() or "unable" in result.lower()


# ---------------------------------------------------------------------------
# Intent parser unit tests
# ---------------------------------------------------------------------------

def test_intent_parser_detects_stockout_query():
    plan = parse_intent("Which SKUs are at risk in the next 30 days?")
    assert plan.intent == Intent.STOCKOUT_QUERY
    assert plan.horizon_days == 30


def test_intent_parser_detects_horizon_change():
    plan = parse_intent(
        "What if the horizon was 60 days instead?",
        current_horizon=30,
        has_prior_results=True,
    )
    assert plan.intent == Intent.CHANGE_HORIZON
    assert plan.horizon_days == 60


def test_intent_parser_detects_core_filter():
    plan = parse_intent(
        "Show me only the core SKUs from that list.",
        current_horizon=30,
        has_prior_results=True,
    )
    assert plan.intent == Intent.FILTER_CORE
    assert plan.use_cache is True


def test_intent_parser_core_filter_requires_prior_results():
    """Core filter intent should not fire if there are no prior results."""
    plan = parse_intent(
        "Show me only the core SKUs.",
        current_horizon=30,
        has_prior_results=False,
    )
    # Without prior results, "core" filter cannot be served — falls to stockout or unknown
    assert plan.intent != Intent.FILTER_CORE


def test_intent_parser_same_horizon_not_change():
    """Mentioning the current horizon should not trigger a horizon change."""
    plan = parse_intent(
        "What would happen over 30 days?",
        current_horizon=30,
        has_prior_results=False,
    )
    assert plan.intent != Intent.CHANGE_HORIZON