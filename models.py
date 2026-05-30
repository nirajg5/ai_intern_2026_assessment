"""
models.py — Pydantic input/output models for the SC Decision Engine tools.

These are the typed contracts between the orchestrator and the tool layer.
The LLM sees these schemas when deciding which tool to call and with what arguments.
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class StockoutRiskInput(BaseModel):
    """
    Input to calculate_stockout_risk.

    sku_ids          — list of SKU IDs to evaluate. Must not be empty.
    horizon_days     — planning horizon in calendar days (e.g. 30, 60, 90).
    channel          — optional channel filter (e.g. "CH-DTC"). If None, aggregate across channels.
    confidence_level — CI level to use from the forecast (0.80 uses lower_ci_80 / upper_ci_80).
    """
    sku_ids: list[str] = Field(..., min_length=1)
    horizon_days: int = Field(..., gt=0, le=365)
    channel: str | None = None
    confidence_level: float = Field(default=0.80, ge=0.0, le=1.0)

    @field_validator("sku_ids")
    @classmethod
    def sku_ids_not_empty(cls, v: list[str]) -> list[str]:
        if not all(s.strip() for s in v):
            raise ValueError("sku_ids must not contain empty strings")
        return v


class SKURiskResult(BaseModel):
    """
    Per-SKU result returned by calculate_stockout_risk.

    sku_id               — the SKU identifier (matches input).
    sku_name             — human-readable name from the fixture.
    is_core              — True if product_class is A+ or A.
    stockout_probability — fraction of Monte Carlo trials that stocked out. In [0.0, 1.0].
    days_of_supply       — average days of supply remaining across trials.
                           Gives planners a concrete number: "~4 days before SKU-004 runs out"
                           is more actionable than "84% probability."
    risk_tier            — HIGH / MEDIUM / LOW / SAFE derived from probability.
                           Lets the orchestrator filter without arithmetic.
    """
    sku_id: str
    sku_name: str
    is_core: bool
    stockout_probability: float = Field(..., ge=0.0, le=1.0)
    days_of_supply: float = Field(default=0.0, ge=0.0)
    risk_tier: Literal["HIGH", "MEDIUM", "LOW", "SAFE"] = "SAFE"


class StockoutRiskOutput(BaseModel):
    """
    Full output of calculate_stockout_risk.

    results         — one SKURiskResult per input SKU, sorted by stockout_probability descending.
    summary         — 2–3 sentence plain-English planning summary.
    horizon_days    — echoed from input so consumers know the planning window.
    skus_evaluated  — total SKUs processed (equals len(results)).
    high_risk_count — SKUs with risk_tier == HIGH. Saves the orchestrator a filter pass.
    """
    results: list[SKURiskResult]
    summary: str
    horizon_days: int
    skus_evaluated: int
    high_risk_count: int = 0