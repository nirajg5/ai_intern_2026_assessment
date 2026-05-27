
"""Task A implementation scaffold.

Important:
- Simpler approximations are acceptable.
- We care more about directional correctness than statistical sophistication.
- The tool should remain deterministic and independently testable.
"""

from models import StockoutRiskOutput


def calculate_stockout_risk(sku_ids: list[str], horizon_days: int) -> StockoutRiskOutput:
    """
    Suggested implementation steps:

    1. Load fixture data
    2. Simulate demand uncertainty
    3. Model replenishment timing
    4. Estimate stockout probability
    5. Return structured results

    ~1,000 trials per SKU is more than sufficient.

    Fixture reference (all files are JSON arrays, path relative to repo root):

      fixtures/inventory_position.json
          One row per SKU/channel. Key fields:
            sku_id, sku_name, channel_id, product_class, is_core,
            net_available_to_sell, in_transit_qty, snapshot_date

      fixtures/forecast_with_ci.json
          One row per SKU/channel/date. Key fields:
            sku_id, channel_id, forecast_date,
            adjusted_forecast_qty, lower_ci_80, upper_ci_80

      fixtures/open_pos.json
          One row per purchase order. Key fields:
            sku_id, quantity, expected_delivery_date, days_to_delivery, status

      fixtures/lead_times.json
          One row per supplier/SKU pairing. Key fields:
            sku_id, actual_lead_time_mean, actual_lead_time_std
          NOTE: one row has sku_id=null — this is a supplier-level fallback.
          Use it for any SKU whose sku_id-level row has sample_count < 3
          (e.g. SKU-007 has sample_count=2 and should use this fallback).
    """

    raise NotImplementedError("Implement stockout simulation logic.")
