# ADR-0003 · Supervisor + workers as the flagship shape

**Status:** Accepted

## Context

A scenario can be implemented in at least three orchestration shapes:

1. **Single agent** with all tools attached. Simplest; the model
   decides everything.
2. **Chat-with-actioning** — single agent for dialog, dispatches to
   tools that may call other agents. A middle ground.
3. **Supervisor + specialist workers** — a router agent classifies
   intent and dispatches to one or more stateless worker agents,
   then aggregates.

For a flagship reference that is meant to scale from "small enough to
read in an afternoon" to "regulated enterprise rollout", the shape
choice trades off cognitive load against extensibility, traceability,
and per-step content filtering.

## Decision

The flagship scenario (`src/scenarios/sales_research/`) implements
**supervisor + specialist workers** with stateless workers and an
explicit aggregation executor. Single-agent and chat-with-actioning
are documented as **walkthrough variants** in
`patterns/<variant>/README.md` — not drop-in packages — because
flipping shape is a re-authoring exercise, not a config switch.

The `/switch-to-variant` chat-mode walks a partner through that
re-authoring.

## Consequences

**Positive**

* New capabilities are added by scaffolding a worker, not by editing
  one growing prompt. The 3-layer agent shape (ADR-0007) makes that
  routine.
* Each worker is independently evaluable and rate-limit-able, so a
  noisy worker doesn't poison the rest of the flow.
* Supervisor's routing decision is itself a telemetry event — the
  trace shows *which* worker fired and *why*, not just "the agent
  did things".

**Negative**

* For a scenario with one capability and no extension plan, the
  supervisor is overhead. Partners targeting that shape should pick
  the `single-agent` variant via `/switch-to-variant`.
* Two LLM round-trips minimum (supervisor + worker) — slightly higher
  per-call cost than a one-shot agent.

**How to deviate**

`/switch-to-variant single-agent` or `/switch-to-variant chat-with-actioning`.
The HITL, telemetry, retrieval, and content-filter invariants stay
regardless of variant — only the orchestrator shape changes.

## References

* `src/scenarios/sales_research/workflow.py` — flagship `WORKERS` registry
* `docs/patterns/single-agent/README.md` and `chat-with-actioning/README.md`
* `.github/agents/switch-to-variant.agent.md`
* [ADR-0007 — Three-layer agent module](0007-three-layer-agent-module.md)
