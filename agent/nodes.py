"""
agent/nodes.py

Bonus task — implement the LangGraph graph nodes here.

Each function takes an AgentState and returns a dict of state updates.
LangGraph merges the returned dict into the current state automatically.

YOUR TASK:
  Implement the five node functions below. Stubs are imported from tools/stubs.py.
  The LLM call in parse_intent is intentionally left flexible — a simple
  keyword-based approach (no API key needed) is completely acceptable.
"""

from agent.state import AgentState
from tools.stubs import query_inventory_state, calculate_stockout_risk


# ── Node: parse_intent ────────────────────────────────────────────────────────

def parse_intent(state: AgentState) -> dict:
    """
    Extract structured intent from the latest user message.

    Should determine:
      - Which SKUs the user is asking about (specific IDs or "ALL")
      - What planning horizon they want (default 30 if not specified)
      - Any filters they want applied (e.g. "only core SKUs")
      - Whether the horizon has changed since the last turn (triggers re-run)

    If you are using a real LLM, prompt it to return a structured JSON object.
    If you are mocking, use keyword matching on state["last_user_message"].

    Returns a dict with state updates (e.g. resolved_sku_ids, horizon_days,
    active_filters).
    """
    # TODO: implement this node
    raise NotImplementedError("parse_intent not yet implemented")


# ── Node: call_inventory ──────────────────────────────────────────────────────

def call_inventory(state: AgentState) -> dict:
    """
    Call query_inventory_state with the SKUs resolved by parse_intent.

    Should use cached_inventory from state if available and the SKU list
    hasn't changed. Store the result in cached_inventory.

    Returns a dict with state updates.
    """
    # TODO: implement this node
    raise NotImplementedError("call_inventory not yet implemented")


# ── Node: call_stockout_risk ──────────────────────────────────────────────────

def call_stockout_risk(state: AgentState) -> dict:
    """
    Call calculate_stockout_risk with the current SKU list and horizon.

    Should re-call the tool when:
      - No cached result exists, OR
      - The horizon_days has changed since the last call, OR
      - The resolved_sku_ids have changed

    Otherwise, reuse cached_stockout_risk.

    Returns a dict with state updates.
    """
    # TODO: implement this node
    raise NotImplementedError("call_stockout_risk not yet implemented")


# ── Node: synthesise ─────────────────────────────────────────────────────────

def synthesise(state: AgentState) -> dict:
    """
    Build the final response from tool outputs stored in state.

    Should:
      - Apply any active_filters to the stockout risk results
      - Format a ranked table of SKUs by stockout_probability
      - Append the summary from the tool output
      - Set state["final_response"] to the assembled string

    Returns a dict with state updates (at minimum: {"final_response": "..."}).
    """
    # TODO: implement this node
    raise NotImplementedError("synthesise not yet implemented")


# ── Node: handle_error ────────────────────────────────────────────────────────

def handle_error(state: AgentState) -> dict:
    """
    Surface a tool failure to the user rather than propagating an exception.

    Should set final_response to a clear explanation of what failed and why,
    without a Python traceback and without fabricating an answer.

    Returns a dict with state updates.
    """
    # TODO: implement this node
    raise NotImplementedError("handle_error not yet implemented")
