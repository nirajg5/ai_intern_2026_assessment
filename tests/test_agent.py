"""
tests/test_agent.py

Bonus task — complete and extend this test file.

We have provided the test structure and helper for building initial state.
Your job is to implement the two required test scenarios below.

All tests must pass with `pytest tests/test_agent.py -v`.

Requires: pip install -r requirements_bonus.txt
"""

import pytest

# Skip this entire file if LangGraph is not installed.
# Run: pip install -r requirements_bonus.txt  to enable the bonus tests.
pytest.importorskip("langgraph", reason="Bonus task — install requirements_bonus.txt to run")

from unittest.mock import patch

from agent.graph import app
from agent.state import AgentState


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_state(message: str, **overrides) -> dict:
    """
    Build a minimal initial state dict for the agent.
    Pass additional keyword arguments to override defaults.
    """
    base: dict = {
        "messages": [],
        "last_user_message": message,
        # Add defaults for any other fields you defined in AgentState here
        # e.g. "horizon_days": 30, "cached_stockout_risk": None, ...
    }
    base.update(overrides)
    return base


# ── Required test 1: three-turn scenario ─────────────────────────────────────

class TestMultiTurn:

    def test_three_turn_scenario(self):
        """
        Simulate the three-turn conversation from the project brief.

        Turn 1: "Which SKUs are at highest risk of stocking out in the next 30 days?"
          - Agent should call both tools.
          - final_response should contain a ranked list of SKUs.
          - cached_stockout_risk should be populated.

        Turn 2: "Now show me only the core SKUs from that list."
          - Agent should NOT re-call the tools (verify by asserting the stub
            call count has not increased, or by checking a flag in state).
          - final_response should only contain SKUs where is_core is True.

        Turn 3: "What would happen if the horizon was 60 days instead?"
          - Agent SHOULD re-call calculate_stockout_risk with horizon_days=60.
          - final_response should reflect the updated horizon.

        Hint: use unittest.mock.patch to count stub calls:
            with patch("tools.stubs.calculate_stockout_risk", wraps=calculate_stockout_risk) as mock_risk:
                ...
                assert mock_risk.call_count == 1  # only called once in turns 1–2
        """
        # TODO: implement this test
        raise NotImplementedError


# ── Required test 2: error handling ──────────────────────────────────────────

class TestErrorHandling:

    def test_tool_error_surfaces_to_user(self):
        """
        Simulate a tool failure and assert the agent handles it gracefully.

        Setup:
          - Patch calculate_stockout_risk (in tools.stubs) to raise RuntimeError("warehouse timeout").
          - Invoke the agent with a standard stockout question.

        Assertions:
          - The agent does not raise an unhandled exception.
          - state["final_response"] contains a human-readable explanation of the failure.
          - state["final_response"] does NOT contain a Python traceback or the word "Traceback".
          - state["final_response"] does NOT appear to fabricate stockout data.

        Hint:
            with patch("tools.stubs.calculate_stockout_risk", side_effect=RuntimeError("warehouse timeout")):
                state = app.invoke(make_state("Which SKUs will stock out?"))
                assert "warehouse timeout" in state["final_response"] or "unavailable" in state["final_response"]
        """
        # TODO: implement this test
        raise NotImplementedError


# ── Your own tests — add at least one below ───────────────────────────────────

class TestAdditional:
    """
    Add any additional agent tests here.
    Ideas:
      - Test that passing an invalid SKU ID produces a useful error message.
      - Test that active_filters persists correctly into the next turn.
      - Test that the summary from the stub is included in final_response.
    """
    pass
