
# SC Decision Engine — AI Engineer Intern Project

## Setup

```bash
pip install -r requirements.txt
```

Optional bonus dependencies (LangGraph task only):

```bash
pip install -r requirements_bonus.txt
```

## Run Tests

**Required tasks (Tasks A & B):**
```bash
pytest tests/test_stockout_risk.py tests/test_orchestrator.py -v
```

**Bonus task** (requires `requirements_bonus.txt` installed first):
```bash
pytest tests/test_agent.py -v
```

**Run everything at once:**
```bash
pytest -v
```

> Note: `tests/test_agent.py` is automatically skipped if LangGraph is not installed.

## Recommended Approach

### Task A
Implement a deterministic stockout risk simulation tool.

Focus on:
- directional correctness,
- testing,
- structured outputs,
- and clear assumptions.

### Task B
Build a lightweight orchestration layer.

Focus on:
- tool sequencing,
- state management,
- cache reuse,
- cache invalidation,
- and graceful error handling.

## Example Interaction

```python
assistant.handle_query(
    "Which SKUs are at highest risk in the next 30 days?"
)

assistant.handle_query(
    "Now show me only the core SKUs."
)

assistant.handle_query(
    "What would happen if the horizon was 60 days instead?"
)
```

## Notes

- Simpler approximations are acceptable.
- We care more about systems thinking than framework usage.
- AI assistants are explicitly allowed.
