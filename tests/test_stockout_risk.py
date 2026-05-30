"""
tests/test_stockout_risk.py — Task A tests

Test categories:
  1. Boundary/invariant  — probability always in [0.0, 1.0]
  2. Degenerate input    — zero inventory + no PO → near-certain stockout
  3. Directional         — high inventory → lower risk than low inventory
  4. Monotonicity        — longer horizon → same or higher risk for same SKU
  5. PO effect           — arriving PO reduces risk vs no PO
  6. Output schema       — all required fields populated with sensible values
  7. Fallback lead time  — SKU-007 (sample_count=2) uses supplier fallback, still runs cleanly
  8. Sorting             — results returned highest-risk first
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.calculate_stockout_risk import _simulate_single_sku, calculate_stockout_risk

# Shared RNG for pure-function tests — isolated from the main simulation seed
_RNG = np.random.default_rng(seed=99)

ALL_SKUS = ["SKU-001", "SKU-002", "SKU-003", "SKU-004",
            "SKU-005", "SKU-006", "SKU-007", "SKU-008"]


# ---------------------------------------------------------------------------
# 1. Boundary / invariant
# ---------------------------------------------------------------------------

def test_probability_always_between_0_and_1():
    """Stockout probability must always be in [0.0, 1.0] for every SKU."""
    output = calculate_stockout_risk(ALL_SKUS, 30)
    for r in output.results:
        assert 0.0 <= r.stockout_probability <= 1.0, (
            f"{r.sku_id}: probability {r.stockout_probability} is out of [0, 1]"
        )


# ---------------------------------------------------------------------------
# 2. Degenerate input
# ---------------------------------------------------------------------------

def test_zero_inventory_no_po_gives_near_certain_stockout():
    """
    Zero on_hand, no open POs, positive daily demand.
    Stockout probability should be very high (>= 0.95).
    """
    sim = _simulate_single_sku(
        on_hand=0.0,
        pos=[],
        daily_mean=10.0,
        daily_std=1.0,
        lt_mean=999.0,
        lt_std=0.0,
        horizon_days=30,
        n_trials=500,
        rng=np.random.default_rng(0),
    )
    assert sim.stockout_probability >= 0.95, (
        f"Zero inventory + no PO should be near-certain stockout, got {sim.stockout_probability:.3f}"
    )


def test_massive_inventory_no_po_gives_near_zero_risk():
    """
    Very large on_hand relative to demand — stockout should be near zero.
    """
    sim = _simulate_single_sku(
        on_hand=100_000.0,
        pos=[],
        daily_mean=5.0,
        daily_std=1.0,
        lt_mean=999.0,
        lt_std=0.0,
        horizon_days=30,
        n_trials=500,
        rng=np.random.default_rng(1),
    )
    assert sim.stockout_probability <= 0.02, (
        f"Massive inventory should be near-zero risk, got {sim.stockout_probability:.3f}"
    )


# ---------------------------------------------------------------------------
# 3. Directional behavior
# ---------------------------------------------------------------------------

def test_high_inventory_sku_has_lower_risk_than_low_inventory_sku():
    """
    SKU-001 (net_available=142, two large POs) should have lower risk
    than SKU-004 (net_available=8, POs arriving after 27+ days).
    """
    output = calculate_stockout_risk(["SKU-001", "SKU-004"], 30)
    sku001 = next(r for r in output.results if r.sku_id == "SKU-001")
    sku004 = next(r for r in output.results if r.sku_id == "SKU-004")
    assert sku001.stockout_probability < sku004.stockout_probability, (
        f"SKU-001 ({sku001.stockout_probability:.3f}) should be lower risk "
        f"than SKU-004 ({sku004.stockout_probability:.3f})"
    )


def test_incoming_large_po_reduces_stockout_risk():
    """
    Adding a large PO arriving early in the horizon should reduce risk
    compared to the identical scenario with no PO.
    """
    rng_no_po = np.random.default_rng(42)
    rng_with_po = np.random.default_rng(42)

    no_po = _simulate_single_sku(
        on_hand=20.0, pos=[],
        daily_mean=5.0, daily_std=1.0,
        lt_mean=5.0, lt_std=1.0,
        horizon_days=30, n_trials=800,
        rng=rng_no_po,
    )
    with_po = _simulate_single_sku(
        on_hand=20.0, pos=[{"quantity": 500.0, "days_to_delivery": 5.0}],
        daily_mean=5.0, daily_std=1.0,
        lt_mean=5.0, lt_std=1.0,
        horizon_days=30, n_trials=800,
        rng=rng_with_po,
    )
    assert with_po.stockout_probability < no_po.stockout_probability, (
        f"Large early PO should reduce risk: no_po={no_po.stockout_probability:.3f}, "
        f"with_po={with_po.stockout_probability:.3f}"
    )


# ---------------------------------------------------------------------------
# 4. Monotonicity — longer horizon → same or higher risk
# ---------------------------------------------------------------------------

def test_longer_horizon_does_not_decrease_risk():
    """
    For a given SKU, stockout probability over 60 days should be >= 30 days.
    Risk cannot decrease as the horizon extends.
    """
    out_30 = calculate_stockout_risk(["SKU-004"], 30)
    out_60 = calculate_stockout_risk(["SKU-004"], 60)
    p30 = out_30.results[0].stockout_probability
    p60 = out_60.results[0].stockout_probability
    assert p60 >= p30 - 0.05, (  # small tolerance for Monte Carlo variance
        f"Risk should not decrease with longer horizon: 30d={p30:.3f}, 60d={p60:.3f}"
    )


# ---------------------------------------------------------------------------
# 5. Output schema completeness
# ---------------------------------------------------------------------------

def test_output_fields_are_fully_populated():
    """All required output fields must be present and semantically valid."""
    output = calculate_stockout_risk(["SKU-001", "SKU-004"], 30)

    assert output.skus_evaluated == 2
    assert output.horizon_days == 30
    assert len(output.results) == 2
    assert len(output.summary) > 30, "Summary should be a meaningful sentence"
    assert isinstance(output.high_risk_count, int)
    assert 0 <= output.high_risk_count <= output.skus_evaluated

    for r in output.results:
        assert r.risk_tier in ("HIGH", "MEDIUM", "LOW", "SAFE"), (
            f"{r.sku_id}: unexpected risk_tier '{r.risk_tier}'"
        )
        assert r.days_of_supply >= 0.0, (
            f"{r.sku_id}: days_of_supply should be non-negative"
        )
        assert r.sku_name != "", f"{r.sku_id}: sku_name should not be empty"


# ---------------------------------------------------------------------------
# 6. Results are sorted highest-risk first
# ---------------------------------------------------------------------------

def test_results_sorted_by_probability_descending():
    """Results must be sorted by stockout_probability descending."""
    output = calculate_stockout_risk(ALL_SKUS, 30)
    probs = [r.stockout_probability for r in output.results]
    assert probs == sorted(probs, reverse=True), (
        f"Results not sorted descending: {probs}"
    )


# ---------------------------------------------------------------------------
# 7. SKU-007 uses lead-time fallback (sample_count=2) without crashing
# ---------------------------------------------------------------------------

def test_sku007_fallback_lead_time_runs_cleanly():
    """
    SKU-007 has sample_count=2 in lead_times.json, below the fallback threshold.
    The simulation must use the supplier-level fallback and return a valid result.
    """
    output = calculate_stockout_risk(["SKU-007"], 30)
    assert len(output.results) == 1
    r = output.results[0]
    assert r.sku_id == "SKU-007"
    assert 0.0 <= r.stockout_probability <= 1.0
    # SKU-007: net_available=8, no POs, daily_mean=5.0 — expect high risk
    assert r.stockout_probability >= 0.5, (
        f"SKU-007 (low stock, no PO) should be high risk, got {r.stockout_probability:.3f}"
    )


# ---------------------------------------------------------------------------
# 8. days_of_supply is consistent with stockout_probability
# ---------------------------------------------------------------------------

def test_days_of_supply_consistent_with_probability():
    """
    A very high-risk SKU should have low days_of_supply.
    A very low-risk SKU should have days_of_supply close to the horizon.
    """
    sim_high = _simulate_single_sku(
        on_hand=0.0, pos=[],
        daily_mean=10.0, daily_std=1.0,
        lt_mean=999.0, lt_std=0.0,
        horizon_days=30, n_trials=500,
        rng=np.random.default_rng(5),
    )
    sim_low = _simulate_single_sku(
        on_hand=100_000.0, pos=[],
        daily_mean=5.0, daily_std=1.0,
        lt_mean=999.0, lt_std=0.0,
        horizon_days=30, n_trials=500,
        rng=np.random.default_rng(6),
    )
    assert sim_high.avg_days_of_supply < sim_low.avg_days_of_supply, (
        f"High-risk SKU should have lower days_of_supply than low-risk SKU: "
        f"high={sim_high.avg_days_of_supply:.1f}, low={sim_low.avg_days_of_supply:.1f}"
    )
    # Low-risk should survive nearly the full horizon
    assert sim_low.avg_days_of_supply >= 28.0, (
        f"Low-risk SKU should survive nearly the full horizon, got {sim_low.avg_days_of_supply:.1f}"
    )