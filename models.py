"""
models.py — Pydantic input/output models for the SC Decision Engine tools.

These are the typed contracts between the LLM orchestrator and the tool layer.
The LLM sees these schemas when deciding which tool to call and with what arguments.

YOUR TASK:
  - The skeletons below are correct as-is for Task A.
  - Do not remove or rename the existing fields.
  - You may add fields to SKURiskResult if your implementation produces them,
    but stockout_probability is the only required output field beyond the identifiers.
  - Update this file if you make model changes, and note them in DECISIONS.md.
"""

from pydantic import BaseModel, Field, field_validator


class StockoutRiskInput(BaseModel):
    """
    Input to calculate_stockout_risk.

    sku_ids       — list of SKU IDs to evaluate. Must not be empty.
    horizon_days  — planning horizon in calendar days (e.g. 30, 60, 90).
    channel       — optional channel filter (e.g. "CH-DTC"). If None, aggregate across channels.
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
    stockout_probability — fraction of Monte Carlo trials in which this SKU stocked out.
                           Must be in [0.0, 1.0].
    """
    sku_id: str
    sku_name: str
    is_core: bool
    stockout_probability: float = Field(..., ge=0.0, le=1.0)

    # ── Optional: add fields here if your implementation produces them ────────
    # Examples you might consider (not required):
    #   expected_days_to_stockout: float | None = None
    #   risk_tier: Literal["high", "medium", "low", "safe"] | None = None
    # ─────────────────────────────────────────────────────────────────────────


class StockoutRiskOutput(BaseModel):
    """
    Full output of calculate_stockout_risk.

    results        — one SKURiskResult per input SKU, sorted by stockout_probability descending.
    summary        — 2–3 sentence plain-English summary suitable for surfacing in a planning UI.
    horizon_days   — echoed from the input so consumers know the planning window.
    skus_evaluated — total number of SKUs processed (should equal len(results)).
    """
    results: list[SKURiskResult]
    summary: str
    horizon_days: int
    skus_evaluated: int
