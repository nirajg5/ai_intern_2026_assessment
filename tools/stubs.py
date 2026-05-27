
"""Stub tools for orchestration testing.

These functions intentionally return deterministic fixture-based outputs.
You may optionally wire your real Task A implementation into the orchestrator.
"""


def query_inventory_state(sku_ids: list[str], channel: str | None = None) -> dict:
    return {
        "status": "success",
        "sku_ids": sku_ids,
        "channel": channel,
    }


def calculate_stockout_risk(sku_ids: list[str], horizon_days: int) -> dict:
    return {
        "status": "success",
        "horizon_days": horizon_days,
        "results": [
            {
                "sku_id": sku_id,
                "stockout_probability": 0.42,
                "is_core": True,
            }
            for sku_id in sku_ids
        ],
    }
