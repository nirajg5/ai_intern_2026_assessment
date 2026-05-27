
"""Simple deterministic intent parsing helpers.

A lightweight keyword-based implementation is completely acceptable.

You do NOT need a real LLM for this assignment.
"""

import re


def parse_intent(user_message: str) -> dict:
    """
    Example return shape:

    {
        "requested_core_only": False,
        "horizon_days": 30,
        "requires_recalculation": True
    }
    """

    lowered = user_message.lower()

    horizon_match = re.search(r"(\d+)\s*day", lowered)
    horizon_days = int(horizon_match.group(1)) if horizon_match else 30

    return {
        "raw_query": user_message,
        "horizon_days": horizon_days,
        "requested_core_only": "core" in lowered,
    }
