"""
tools/calculate_stockout_risk.py — Task A

Deterministic Monte Carlo stockout risk simulator.
- No LLM dependency.
- Independently testable: _simulate_single_sku is a pure function with no I/O.
- Fixed seed (42) ensures reproducible results across runs.

Design decisions are documented in DECISIONS.md.
"""

import json
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np

# Allow running from repo root or tools/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import SKURiskResult, StockoutRiskOutput

FIXTURES = Path(__file__).parent.parent / "fixtures"
N_TRIALS = 1000
FALLBACK_SAMPLE_THRESHOLD = 3  # use supplier-level fallback if sample_count < this


# ---------------------------------------------------------------------------
# Data loading — pure, no side effects beyond file I/O
# ---------------------------------------------------------------------------

def _load_fixtures() -> tuple[dict, dict, dict, dict]:
    """
    Load all four fixture files.
    Returns dicts keyed by sku_id for O(1) lookup during simulation.

    forecast: sku_id → aggregated daily mean/std across all dates/channels.
    lead_times: sku_id → (mean, std). Falls back to supplier-level row
                when sample_count < FALLBACK_SAMPLE_THRESHOLD (e.g. SKU-007).
    open_pos: sku_id → list of PO dicts (quantity + days_to_delivery).
    inventory: sku_id → inventory dict.
    """
    def _read(name: str) -> list[dict]:
        return json.loads((FIXTURES / name).read_text())

    # ── inventory ────────────────────────────────────────────────────────────
    inventory: dict[str, dict] = {}
    for row in _read("inventory_position.json"):
        sid = row["sku_id"]
        if sid not in inventory:
            inventory[sid] = row
        else:
            # Aggregate across channels: sum available stock
            inventory[sid]["net_available_to_sell"] += row["net_available_to_sell"]
            inventory[sid]["in_transit_qty"] += row["in_transit_qty"]

    # ── forecast — aggregate per SKU across channels and dates ───────────────
    # Strategy: derive daily_mean and daily_std from the CI fields.
    #   mean  = adjusted_forecast_qty
    #   std   = ci_width_80 / (2 * 1.28)   [80% CI ≈ mean ± 1.28σ]
    # Then average across all rows for that SKU to get a single daily figure.
    fc_accum: dict[str, list[float]] = {}
    fc_std_accum: dict[str, list[float]] = {}
    for row in _read("forecast_with_ci.json"):
        sid = row["sku_id"]
        mean = float(row["adjusted_forecast_qty"])
        std = float(row["ci_width_80"]) / (2 * 1.28)
        fc_accum.setdefault(sid, []).append(mean)
        fc_std_accum.setdefault(sid, []).append(std)

    forecasts: dict[str, dict] = {}
    for sid in fc_accum:
        forecasts[sid] = {
            "daily_mean": float(np.mean(fc_accum[sid])),
            "daily_std": float(np.mean(fc_std_accum[sid])),
        }

    # ── lead times — with supplier-level fallback ─────────────────────────
    raw_lt = _read("lead_times.json")
    fallback_lt = next((r for r in raw_lt if r.get("sku_id") is None), None)

    lead_times: dict[str, dict] = {}
    for row in raw_lt:
        sid = row.get("sku_id")
        if sid is None:
            continue
        sample_count = int(row.get("sample_count", 99))
        if sample_count < FALLBACK_SAMPLE_THRESHOLD and fallback_lt:
            # Use supplier-level fallback (e.g. SKU-007 has sample_count=2)
            lt_mean = float(fallback_lt["actual_lead_time_mean"])
            lt_std = float(fallback_lt["actual_lead_time_std"])
        else:
            lt_mean = float(row["actual_lead_time_mean"])
            lt_std = float(row["actual_lead_time_std"])
        # Apply supplier bias (systematic late delivery adjustment)
        lt_mean += float(row.get("lead_time_bias_days", 0.0))
        lead_times[sid] = {"mean": lt_mean, "std": lt_std}

    # ── open POs — only those relevant within a plausible horizon ────────────
    open_pos: dict[str, list[dict]] = {}
    for row in _read("open_pos.json"):
        sid = row["sku_id"]
        open_pos.setdefault(sid, []).append({
            "quantity": float(row["quantity"]),
            "days_to_delivery": float(row["days_to_delivery"]),
        })

    return inventory, open_pos, forecasts, lead_times


# ---------------------------------------------------------------------------
# Simulation — pure function, no I/O, easily unit-tested with injected values
# ---------------------------------------------------------------------------

class _SimResult(NamedTuple):
    stockout_probability: float
    avg_days_of_supply: float


def _simulate_single_sku(
    on_hand: float,
    pos: list[dict],
    daily_mean: float,
    daily_std: float,
    lt_mean: float,
    lt_std: float,
    horizon_days: int,
    n_trials: int = N_TRIALS,
    rng: np.random.Generator | None = None,
) -> _SimResult:
    """
    Monte Carlo simulation for a single SKU.

    Pure function — no file I/O, no global state.
    Accepts an optional RNG for reproducibility in tests.

    Simplifications (see DECISIONS.md):
    - Daily demand drawn from Normal(daily_mean, daily_std), clipped at 0.
    - Lead-time jitter applied independently per open PO using Normal(lt_mean, lt_std).
    - on_hand and in_transit are combined into a single starting stock figure.
    - Demand and lead time modeled independently (no correlation).
    - Returns once stockout occurs in a trial (no backorder modelling).

    Returns: (_SimResult) stockout_probability and avg_days_of_supply.
    """
    if rng is None:
        rng = np.random.default_rng()

    stockout_count = 0
    total_days_survived = 0.0

    for _ in range(n_trials):
        # 1. Draw daily demand — clipped at 0 (no negative demand)
        daily_demand = rng.normal(daily_mean, max(daily_std, 1e-6), horizon_days)
        daily_demand = np.maximum(daily_demand, 0.0)

        # 2. Schedule PO arrivals — add lead-time jitter to expected delivery
        arrivals: dict[int, float] = {}
        for po in pos:
            jitter = rng.normal(lt_mean, max(lt_std, 1e-6))
            # Arrival day = PO's expected days_to_delivery adjusted by lead-time distribution
            # We use days_to_delivery as the base (already accounts for committed shipping date)
            raw_day = po["days_to_delivery"] + (jitter - lt_mean)
            arrival_day = max(0, int(round(raw_day)))
            if arrival_day < horizon_days:
                arrivals[arrival_day] = arrivals.get(arrival_day, 0.0) + po["quantity"]

        # 3. Day-by-day inventory simulation
        stock = on_hand
        stocked_out = False
        for day in range(horizon_days):
            stock += arrivals.get(day, 0.0)
            stock -= daily_demand[day]
            if stock < 0.0:
                stocked_out = True
                total_days_survived += float(day)
                break
        else:
            total_days_survived += float(horizon_days)

        if stocked_out:
            stockout_count += 1

    prob = stockout_count / n_trials
    avg_days = total_days_survived / n_trials
    return _SimResult(stockout_probability=prob, avg_days_of_supply=avg_days)


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def _risk_tier(prob: float) -> str:
    if prob >= 0.60:
        return "HIGH"
    if prob >= 0.30:
        return "MEDIUM"
    if prob >= 0.10:
        return "LOW"
    return "SAFE"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_stockout_risk(
    sku_ids: list[str],
    horizon_days: int,
) -> StockoutRiskOutput:
    """
    Main entry point. Deterministic given fixture data (seed=42).
    Does NOT call any LLM. No external dependencies beyond numpy.

    Always call query_inventory_state before this function (orchestrator
    enforces sequencing — this tool trusts that invariant).
    """
    inventory, open_pos, forecasts, lead_times = _load_fixtures()
    # Fixed seed: makes tests reproducible. Documented tradeoff in DECISIONS.md.
    rng = np.random.default_rng(seed=42)

    results = []
    for sku_id in sku_ids:
        inv = inventory.get(sku_id, {})
        fc = forecasts.get(sku_id, {"daily_mean": 1.0, "daily_std": 0.1})
        lt = lead_times.get(sku_id, {"mean": horizon_days + 1, "std": 0.0})
        pos = open_pos.get(sku_id, [])

        # Combine on_hand + in_transit as starting stock.
        # Documented simplification: in_transit carries its own delivery risk
        # which we do not model separately here.
        on_hand = float(inv.get("net_available_to_sell", 0) + inv.get("in_transit_qty", 0))

        sim = _simulate_single_sku(
            on_hand=on_hand,
            pos=pos,
            daily_mean=fc["daily_mean"],
            daily_std=fc["daily_std"],
            lt_mean=lt["mean"],
            lt_std=lt["std"],
            horizon_days=horizon_days,
            rng=rng,
        )

        results.append(SKURiskResult(
            sku_id=sku_id,
            sku_name=inv.get("sku_name", sku_id),
            is_core=bool(inv.get("is_core", False)),
            stockout_probability=round(sim.stockout_probability, 4),
            days_of_supply=round(sim.avg_days_of_supply, 1),
            risk_tier=_risk_tier(sim.stockout_probability),
        ))

    # Sort by risk descending — highest risk planners see first
    results.sort(key=lambda r: r.stockout_probability, reverse=True)

    high_risk = [r for r in results if r.risk_tier == "HIGH"]
    top_core = next((r for r in results if r.is_core), None)

    summary = (
        f"{len(high_risk)} of {len(results)} SKUs have a stockout probability "
        f"above 60% within the next {horizon_days} days."
    )
    if top_core and top_core.risk_tier in ("HIGH", "MEDIUM"):
        summary += (
            f" {top_core.sku_id} ({top_core.sku_name}) is the highest-risk core SKU "
            f"at {top_core.stockout_probability * 100:.0f}% probability "
            f"with approximately {top_core.days_of_supply:.0f} days of supply remaining."
        )

    return StockoutRiskOutput(
        results=results,
        summary=summary,
        horizon_days=horizon_days,
        skus_evaluated=len(results),
        high_risk_count=len(high_risk),
    )