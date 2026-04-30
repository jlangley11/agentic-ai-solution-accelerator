# ADR-0007 · Three-layer agent module (prompt / transform / validate)

**Status:** Accepted

## Context

A worker agent's per-call logic consists of three concerns:

1. **Prompt construction** — turn the request into the user message.
2. **Response transformation** — turn the model's reply into a typed
   dict the supervisor can consume.
3. **Response validation** — assert the reply satisfies the
   scenario's groundedness, schema, and guardrail rules.

These can collapse into one function, but doing so makes each concern
hard to test independently and harder to evolve. A partner who wants
to tighten validation shouldn't have to touch prompt construction.

## Decision

Every worker agent under
`src/scenarios/<scenario>/agents/<agent_name>/` ships **exactly three
files**, each with a single named function:

| File | Function | Purpose |
|------|----------|---------|
| `prompt.py`    | `build_prompt(request_data: dict) -> str`              | Compose the user message from typed inputs |
| `transform.py` | `transform_response(response: str) -> dict`            | Parse model reply into a typed dict |
| `validate.py`  | `validate_response(response: dict) -> tuple[bool, str]` | Return `(ok, reason)` on guardrail/schema/groundedness checks |

`scripts/scaffold-agent.py` is the only supported way to add a
worker — it scaffolds the three files transactionally, registers the
agent in the scenario's `WORKERS` registry, and writes a Foundry
agent spec stub. Hand-scaffolding is rejected by lint
(`agent_module_shape`).

## Consequences

**Positive**

* Each concern is unit-testable in isolation. `tests/` follows the
  same shape: `test_<agent>_prompt.py`, `test_<agent>_transform.py`,
  `test_<agent>_validate.py`.
* `validate.py` is the one place groundedness/schema rules live, so
  `evals/quality/` can target it directly.
* `/add-worker-agent` and the manifest-update flow have a fixed
  surface to template against.

**Negative**

* For a trivial agent the three-file split feels heavy. The win
  shows up the first time a partner needs to harden validation
  during pilot — they edit one small file.
* Partners coming from "single function per agent" frameworks must
  unlearn that habit.

**How to deviate**

Not supported in the flagship. Partners can delete `validate.py`
(it'll trip lint) but that defeats the eval gate; partners can fold
`transform` into `prompt` (it'll trip lint) but that defeats the
test surface.

## References

* `src/scenarios/sales_research/agents/<agent>/` — exemplars
* `scripts/scaffold-agent.py` — the only supported scaffolder
* `scripts/accelerator-lint.py` — `agent_module_shape` rule
* `.github/agents/add-worker-agent.agent.md`
* `.github/copilot-instructions.md` — "Agent structure (3-layer pattern)" rules
