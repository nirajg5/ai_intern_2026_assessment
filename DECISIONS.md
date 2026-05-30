# DECISIONS.md

## Monte Carlo design

I used 1,000 trials per SKU with a fixed seed (42) for reproducibility.
Daily demand is drawn from Normal(mean, std) clipped at zero — a reasonable
approximation when std << mean. The std is derived from the 80% CI in the
forecast fixture: `std = ci_width_80 / (2 × 1.28)`, since an 80% CI spans
approximately ±1.28σ. Real demand often has fat tails; a log-normal or Poisson
model would be more accurate but adds complexity without meaningfully changing
the directional risk rankings needed for planning decisions.

Lead-time variability is applied independently per open PO. I treat each PO's
effective arrival as `days_to_delivery + (Normal(lt_mean, lt_std) − lt_mean)`,
which adds jitter around the committed delivery date while preserving the
supplier's known bias (`lead_time_bias_days` is added to the mean). For SKU-007
(sample_count=2, below the threshold of 3), the supplier-level fallback row is
used rather than the unreliable SKU-level estimate.

Key simplification: `on_hand` and `in_transit` are combined into a single
starting stock figure (`net_available_to_sell + in_transit_qty`). In reality,
in-transit goods carry their own delivery uncertainty — not modelling this
separately understates risk slightly for SKUs with large in-transit quantities.
Documented rather than silently ignored.

## Schema design

I extended the brief's skeleton with `days_of_supply` and `risk_tier`.
`days_of_supply` gives planners a concrete number to act on: "you have ~4 days
before SKU-004 runs out" is more actionable than "84% probability." `risk_tier`
(HIGH/MEDIUM/LOW/SAFE) lets the orchestrator filter without arithmetic. Both
are derived from the simulation, so they add no computational cost. `high_risk_count`
on the output is pre-computed for the same reason — the orchestrator never needs
to scan results to know how many are high risk.

Pydantic validators on `StockoutRiskInput` enforce preconditions at the boundary:
horizon must be positive, confidence must be in (0,1), SKU IDs must not be empty
strings. The simulation can assume clean data.

## Orchestration design

Intent is parsed into an explicit `QueryPlan` struct before any tool is called.
This separation means the orchestrator acts on a plan rather than reacting to
raw strings, enabling dynamic tool selection, richer multi-step workflows, and
easier future integration of an LLM-based intent parser — keeping the core
design principle intact: the LLM plans, tools compute.

Cache key: `(tuple(sorted_sku_ids), horizon_days)`. Changing the horizon creates
a new entry rather than evicting the old one — switching back to 30 days reuses
the earlier result immediately. Cache is per-session (in-memory dict); a
production system would use Redis with TTLs.

Tool sequencing is enforced in `_execute_stockout_query`: inventory always runs
first. If either tool raises `RuntimeError`, the orchestrator surfaces a
plain-English message with no stack trace and no hallucinated data.

## Bonus: LangGraph implementation

Five nodes — `parse_intent → call_inventory → call_stockout_risk → synthesise` —
with conditional edges routing to `handle_error` if any tool sets `error_message`
in state. Each node is a pure function returning a dict of state updates, keeping
nodes independently testable. The `QueryPlan` struct from Task B carries over so
nodes act on a structured plan, not raw strings — preserving the LLM-plans /
tools-compute separation inside the graph.

## Tradeoffs

- No real LLM for intent parsing: keyword matching is brittle for ambiguous
  phrasing but adds zero latency and zero API dependency during evaluation.
  This is the first thing to replace in a production system.

- Fixed seed: makes tests deterministic at the cost of not capturing simulation
  variance across runs. A production system would run without a seed and use
  confidence intervals on the probability estimate itself.

- No async: the simulation is CPU-bound and single-threaded. For 8 SKUs this
  is fine; for 800, parallelising across SKUs with `concurrent.futures.ProcessPoolExecutor`
  would be the natural next step.

- Demand independence assumption: demand and lead time are modeled independently.
  In reality, supply disruptions can coincide with demand spikes (e.g. a port delay
  during a seasonal peak). Modeling this correlation would improve realism but was
  outside the scope of this assignment.

## What I would improve next

Introduce a planning layer that converts natural-language queries into a structured
`QueryPlan` before tool execution — this is already partially implemented here, but
a real version would use an LLM call to handle ambiguous phrasing, multi-intent
queries, and SKU resolution from partial names. This would enable dynamic tool
selection, richer multi-step workflows, and easier future extension — keeping the
core principle intact: the LLM plans, tools compute.