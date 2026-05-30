"""
agent/graph.py — LangGraph graph (Bonus Task)

Graph topology:

    parse_intent
         │
    call_inventory ──(error)──► handle_error
         │
    call_stockout_risk ──(error)──► handle_error
         │
      synthesise

Design notes:
- Conditional edges route to handle_error if error_message is set after
  a tool node. This keeps error handling out of the tool nodes themselves.
- synthesise and handle_error are both terminal (→ END).
- The compiled `app` is exported so tests and a future CLI can import it
  with a single `from agent.graph import app`.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def _route_after_inventory(state: AgentState) -> str:
    """Route to handle_error if inventory failed, else continue to stockout."""
    return "handle_error" if state.get("error_message") else "call_stockout_risk"


def _route_after_stockout(state: AgentState) -> str:
    """Route to handle_error if stockout tool failed, else synthesise."""
    return "handle_error" if state.get("error_message") else "synthesise"


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph application.

    Node registration order matches the execution topology above.
    Conditional edges implement error routing without embedding
    error-handling logic inside the tool nodes.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("parse_intent",       parse_intent)
    graph.add_node("call_inventory",     call_inventory)
    graph.add_node("call_stockout_risk", call_stockout_risk)
    graph.add_node("synthesise",         synthesise)
    graph.add_node("handle_error",       handle_error)

    # Entry point
    graph.set_entry_point("parse_intent")

    # Fixed edge: parse_intent → call_inventory (always)
    graph.add_edge("parse_intent", "call_inventory")

    # Conditional edge: after inventory, check for errors
    graph.add_conditional_edges(
        "call_inventory",
        _route_after_inventory,
        {
            "call_stockout_risk": "call_stockout_risk",
            "handle_error":       "handle_error",
        },
    )

    # Conditional edge: after stockout risk, check for errors
    graph.add_conditional_edges(
        "call_stockout_risk",
        _route_after_stockout,
        {
            "synthesise":   "synthesise",
            "handle_error": "handle_error",
        },
    )

    # Terminal nodes → END
    graph.add_edge("synthesise",   END)
    graph.add_edge("handle_error", END)

    return graph.compile()


# Compiled on import — tests and CLI use: from agent.graph import app
app = build_graph()