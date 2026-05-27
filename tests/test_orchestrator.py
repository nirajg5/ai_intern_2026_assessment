
"""Tests for the lightweight orchestration layer."""

from unittest.mock import patch

from agent.orchestrator import PlanningAssistant


def test_multi_turn_cache_behavior():
    """
    Expected behavior:

    Turn 1:
    - tools called

    Turn 2:
    - cached results reused

    Turn 3:
    - recalculation triggered due to changed horizon
    """

    assistant = PlanningAssistant()

    # Candidate implementation here
    assert assistant is not None


def test_error_handling():
    """
    The orchestrator should surface failures cleanly
    without hallucinating answers or exposing tracebacks.
    """

    assistant = PlanningAssistant()

    with patch(
        "tools.stubs.calculate_stockout_risk",
        side_effect=RuntimeError("Simulation failed"),
    ):
        # Candidate implementation here
        assert assistant is not None
