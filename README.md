# SC Decision Engine — AI Engineer Intern Project

## Setup

```bash
pip install -r requirements.txt
```

## Run all tests

```bash
pytest tests/ -v
```

## Run Task A tests only

```bash
pytest tests/test_stockout_risk.py -v
```

## Run Task B tests only

```bash
pytest tests/test_orchestrator.py -v
```

## Project structure

```
sc-intern-project/
├── fixtures/               # JSON fixture data (inventory, forecast, POs, lead times)
├── tools/
│   ├── calculate_stockout_risk.py   # Task A: Monte Carlo simulation
│   └── stubs.py                     # Deterministic stubs for orchestration tests
├── agent/
│   ├── orchestrator.py              # Task B: PlanningAssistant
│   └── state.py                     # ConversationState, Intent, QueryPlan
├── utils/
│   └── intent_parser.py             # parse_intent → QueryPlan
├── tests/
│   ├── test_stockout_risk.py        # Task A tests (8 tests, no assert True)
│   └── test_orchestrator.py         # Task B tests (13 tests, no assert True)
├── models.py                        # Pydantic models (StockoutRiskInput/Output)
├── DECISIONS.md
├── requirements.txt
└── README.md
```
