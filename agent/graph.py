"""
agent/graph.py

Bonus task — wire the LangGraph graph here.

YOUR TASK:
  Build a StateGraph using the nodes from agent/nodes.py.
  The graph must implement the following routing logic:

    parse_intent → call_inventory → call_stockout_risk → synthesise
                                                        ↘ handle_error (on tool failure)

  Routing rules:
    - After call_inventory: if an error occurred, route to handle_error.
      Otherwise route to call_stockout_risk.
    - After call_stockout_risk: if an error occurred, route to handle_error.
      Otherwise route to synthesise.
    - handle_error and synthesise are both terminal nodes.

  The compiled graph is exported as `app` so it can be imported in tests and
  in a future CLI/chat interface.

Usage:
    from agent.graph import app

    state = app.invoke({
        "messages": [],
        "last_user_message": "Which SKUs are at highest risk of stocking out in 30 days?",
        # ... other initial state fields
    })
    print(state["final_response"])
"""

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    raise ImportError(
        "LangGraph is required for the bonus task. "
        "Install it with: pip install -r requirements_bonus.txt"
    )

from agent.state import AgentState
from agent.nodes import (
    parse_intent,
    call_inventory,
    call_stockout_risk,
    synthesise,
    handle_error,
)


def build_graph() -> StateGraph:
    """
    Construct and return the compiled LangGraph application.

    TODO: implement this function.

    Hints:
      - Use StateGraph(AgentState) as the base.
      - Add nodes with graph.add_node("node_name", function).
      - Add edges with graph.add_edge or graph.add_conditional_edges.
      - Set the entry point with graph.set_entry_point("parse_intent").
      - Compile with graph.compile().
    """
    # TODO: implement this function
    raise NotImplementedError("build_graph not yet implemented")


# Compile on import so tests can do: from agent.graph import app
app = build_graph()
