# SC Decision Engine — AI Engineer Intern Project

## Setup

```bash
pip install -r requirements.txt
```

For the bonus LangGraph task:

```bash
pip install -r requirements_bonus.txt
```

---

## Run all tests

```bash
pytest tests/ -v
```

Expected: **33 passed**

## Run each task separately

```bash
# Task A — Monte Carlo simulation
pytest tests/test_stockout_risk.py -v

# Task B — Orchestration layer
pytest tests/test_orchestrator.py -v

# Bonus — LangGraph agent
pytest tests/test_agent.py -v
```

---

## Project structure

```
sc-intern-project/
├── fixtures/                        # JSON fixture data
│   ├── inventory_position.json      #   on-hand stock, is_core flags
│   ├── open_pos.json                #   open purchase orders
│   ├── forecast_with_ci.json        #   30-day demand forecast with CI
│   └── lead_times.json              #   supplier lead-time distributions
├── tools/
│   ├── calculate_stockout_risk.py   # Task A: Monte Carlo simulation
│   └── stubs.py                     # Deterministic stubs for Task B tests
├── agent/
│   ├── orchestrator.py              # Task B: PlanningAssistant (stateful class)
│   ├── state.py                     # ConversationState, Intent, QueryPlan, AgentState
│   ├── nodes.py                     # Bonus: LangGraph node functions
│   └── graph.py                     # Bonus: compiled LangGraph app
├── utils/
│   └── intent_parser.py             # parse_intent → QueryPlan
├── tests/
│   ├── test_stockout_risk.py        # Task A — 8 tests, no assert True
│   ├── test_orchestrator.py         # Task B — 13 tests, no assert True
│   └── test_agent.py                # Bonus — 7 tests, no assert True
├── models.py                        # Pydantic models (StockoutRiskInput/Output)
├── DECISIONS.md
├── requirements.txt                 # pydantic, numpy, pytest
└── requirements_bonus.txt           # + langgraph
```

---

## Architecture overview

```
User query (natural language)
        │
        ▼
  Intent parser → QueryPlan
  (keyword matching; LLM drop-in ready)
        │
        ▼
  Orchestrator / LangGraph graph
  ├── query_inventory_state()   ← always first (sequencing invariant)
  └── calculate_stockout_risk() ← real Monte Carlo simulation (Task A)
        │
        ▼
  Structured response
  (ranked table + plain-English summary)
```

**Design principle:** the orchestrator plans and routes — it never computes.
All numbers come from deterministic tools.
