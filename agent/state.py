
from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass
class AssistantState:
    """
    Suggested orchestration state container for Task B (PlanningAssistant).

    Candidates may modify this structure if desired.
    """

    cached_inventory_results: dict[str, Any] | None = None
    cached_risk_results: dict[str, Any] | None = None

    active_horizon_days: int | None = None
    active_sku_filter: list[str] | None = None

    conversation_history: list[dict[str, str]] = field(default_factory=list)


# ── Bonus: LangGraph state ────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    State TypedDict for the LangGraph bonus task.

    This dict is passed between all nodes in the graph. Every piece of
    information that needs to persist across turns (conversation history,
    cached tool results, active filters, current horizon) must live here.

    YOUR TASK:
      Complete this TypedDict. The fields marked # PROVIDED are required and
      must not be removed. Add any additional fields your implementation needs.

      Think carefully about:
        - What needs to survive across turns (cached results, horizon, filters)?
        - What changes turn by turn (messages, last_tool_called)?
        - How will the synthesise node know whether it is serving a cached
          result or a fresh one?
    """

    # PROVIDED — do not remove these fields

    messages: list[dict]
    """Full conversation history. Each entry: {"role": "user"|"assistant", "content": str}"""

    last_user_message: str
    """The most recent user message, extracted for convenience."""

    # ── TODO: add fields below ────────────────────────────────────────────────
    #
    # Suggestions (not exhaustive — add what your implementation needs):
    #
    #   resolved_sku_ids: list[str] | None
    #       The SKU IDs resolved from the latest user intent. None until
    #       parse_intent runs.
    #
    #   horizon_days: int
    #       The current planning horizon. Defaults to 30 on first turn.
    #
    #   active_filters: dict[str, Any]
    #       Any filters the user has applied (e.g. {"is_core": True}).
    #
    #   cached_inventory: dict | None
    #       The last inventory result. Reuse across turns if SKUs and horizon
    #       haven't changed.
    #
    #   cached_stockout_risk: dict | None
    #       The last stockout risk result. Re-run only if horizon or SKUs
    #       changed.
    #
    #   error_message: str | None
    #       Set by handle_error; cleared at the start of each new turn.
    #
    #   final_response: str
    #       The synthesised response to return to the user.
