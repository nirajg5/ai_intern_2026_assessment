"""
tools/stubs.py — Stub tools for orchestration testing.

These functions return deterministic fixture-based outputs.
The real calculate_stockout_risk (Task A) is wired directly into the
orchestrator — see orchestrator.py. These stubs are available for
isolated orchestration tests that don't need the full simulation.
"""


def query_inventory_state(sku_ids: list[str], channel: str | None = None) -> dict:
    """
    Stub: simulates a warehouse inventory lookup.
    In production this would query v_inventory_position.
    Always called before calculate_stockout_risk (tool sequencing invariant).
    """
    return {
        "status": "success",
        "sku_ids": sku_ids,
        "channel": channel,
        "source": "stub",
    }


def calculate_stockout_risk(sku_ids: list[str], horizon_days: int) -> dict:
    """
    Stub: returns a deterministic 42% risk for all SKUs.
    Used in orchestrator tests that mock the tool layer.
    """
    return {
        "status": "success",
        "horizon_days": horizon_days,
        "results": [
            {
                "sku_id": sku_id,
                "stockout_probability": 0.42,
                "risk_tier": "MEDIUM",
                "days_of_supply": 18.0,
                "is_core": True,
            }
            for sku_id in sku_ids
        ],
    }