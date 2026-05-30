"""
tests/test_langgraph_bonus.py

Bonus Task Tests

Run:
    pytest tests/test_langgraph_bonus.py -v

Requires:
    pip install -r requirements_bonus.txt
"""

import pytest
from unittest.mock import patch

pytest.importorskip(
    "langgraph",
    reason="Install requirements_bonus.txt to run bonus tests"
)

from bonus.langgraph.graph import graph


# ------------------------------------------------------------------
# Multi-turn scenario
# ------------------------------------------------------------------

class TestMultiTurn:

    def test_stockout_query(self):
        """
        Turn 1:
        Standard stockout analysis.
        """

        result = graph.invoke(
            {
                "user_message":
                "Which SKUs are at highest risk of stocking out in the next 30 days?"
            }
        )

        assert "response" in result
        assert "Stockout risk" in result["response"]
        assert "SKU" in result["response"]

    def test_core_filter(self):
        """
        Turn 2:
        Core SKU filtering.
        """

        result = graph.invoke(
            {
                "user_message":
                "Show me only the core SKUs"
            }
        )

        assert "response" in result

    def test_horizon_change(self):
        """
        Turn 3:
        Horizon changes from 30 → 60.
        """

        result = graph.invoke(
            {
                "user_message":
                "What would happen if the horizon was 60 days instead?"
            }
        )

        assert "response" in result
        assert "60" in result["response"]


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

class TestErrorHandling:

    def test_runtime_error_handling(self):
        """
        RuntimeError should be surfaced cleanly.
        """

        with patch(
            "agent.orchestrator._real_stockout_risk",
            side_effect=RuntimeError("warehouse timeout"),
        ):

            result = graph.invoke(
                {
                    "user_message":
                     "Which SKUs are at risk in the next 30 days?"
                }
            )

            assert "response" in result

            assert "Traceback" not in result["response"]

            assert (
                "failed" in result["response"].lower()
                or "timeout" in result["response"].lower()
                or "error" in result["response"].lower()
            )


# ------------------------------------------------------------------
# Additional tests
# ------------------------------------------------------------------

class TestAdditional:

    def test_unknown_query(self):
        """
        Unknown query should return a helpful message.
        """

        result = graph.invoke(
            {
                "user_message":
                "Hello there"
            }
        )

        assert "response" in result

    def test_graph_returns_intent(self):
        """
        Ensure parse node executed.
        """

        result = graph.invoke(
            {
                "user_message":
                "Which SKUs are at risk in the next 30 days?"
            }
        )

        assert "intent" in result
        assert result["intent"] == "stockout_query"