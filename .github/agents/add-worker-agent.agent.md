---
name: add-worker-agent
description: Add a new specialist worker agent to an existing scenario by invoking scripts/scaffold-agent.py, then finishing the three manual follow-ups the scaffolder cannot do.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
handoffs:
  - label: Implement this worker
    agent: implement-worker
    prompt: A new worker has been scaffolded. Run /implement-worker on it to fill in prompt.py, transform.py, validate.py, and the Foundry agent spec.
    send: false
---

# /add-worker-agent — scaffold a new worker via scripts/scaffold-agent.py

> Compatibility adapter: use `accel next` before changing the worker graph and
> `accel validate` after the scaffolder and manual follow-ups complete.

Use this when the brief or a follow-on requirement introduces a capability no current worker covers (e.g., "pricing calc", "risk scoring", "invoice classification").

**Do not hand-scaffold.** `scripts/scaffold-agent.py` is the single supported entry point. It edits the declarative `WORKERS: dict[str, WorkerSpec]` registry in `src/scenarios/<scenario>/workflow.py` — that dict is the only attachment point the supervisor DAG reads. Hand edits whose shape doesn't match what the scaffolder expects flip the file to "no longer scaffold-managed" and break future automation.

## Preconditions
- `accelerator.yaml.architecture.status` is `approved`.
- The decision uses `hosted-agent` with `supervisor-routing` or
  `deterministic-workflow`. Do not add workers to a prompt-agent decision.
- The target scenario exists under `src/scenarios/<scenario>/` and its `workflow.py` declares `WORKERS: dict[str, WorkerSpec] = { ... }` in the canonical single-form shape. (The flagship `sales-research` scenario is the reference.)
- The new worker has a clear, one-sentence capability. If you can't write that sentence, push back to clarify — don't scaffold fuzziness.

## Inputs to gather
1. **Agent id** (lowercase_with_underscores, e.g. `pricing_calculator`, `risk_scoring`)
2. **Scenario id** (lowercase-with-hyphens — matches `accelerator.yaml.scenario.id`, e.g. `sales-research`)
3. **One-sentence capability** (used by the supervisor router; quoted verbatim into the YAML snippet)
4. **Upstream workers it depends on** (comma-separated list of existing worker ids the DAG must schedule first)
5. **Whether it's optional** (the DAG can skip it and still produce a valid answer)
6. **Foundry agent name** — defaults to `accel-<scenario-id>-<agent-id-with-underscores-to-hyphens>` (e.g. `risk_scoring` → `accel-sales-research-risk-scoring`). The scaffolder writes a `docs/agent-specs/<foundry_name>.md` stub; shared provisioning syncs it on the next target-aware deployment. Author system instructions in the spec file — never in the portal or Python.

## Invoke the scaffolder
```bash
# <agent_id> e.g., risk_scoring; <scenario-id> e.g., sales-research
python scripts/scaffold-agent.py <agent_id> \
  --scenario <scenario-id> \
  --capability "<one-sentence capability>" \
  --depends-on <upstream_a>,<upstream_b> \
  [--optional]
```

The scaffolder will:
- Create `src/scenarios/<scenario>/agents/<agent_id>/{__init__,prompt,transform,validate}.py` with working three-layer stubs.
- Patch `src/scenarios/<scenario>/agents/__init__.py` — add the import and extend `__all__`.
- Patch `src/scenarios/<scenario>/workflow.py` — add the import, insert a `_build_input_<agent_id>` helper immediately above `WORKERS`, and insert a new `"<agent_id>": WorkerSpec(...)` entry immediately before the dict's closing `}`.
- Write a Foundry agent spec stub at `docs/agent-specs/<foundry-agent-name>.md`.
- Print the YAML snippet you must paste into `accelerator.yaml -> scenario.agents[]`.

The scaffolder is **transactional**: it snapshots `workflow.py` and `agents/__init__.py` before any write and rolls everything back (including deleting newly created files) on any failure, including a post-write `ast.parse` syntax check. It is also **re-run safe**: a second run with the same `<agent_id>` exits non-zero without changing anything.

## Two manual follow-ups
The scaffolder cannot do these; you must.

1. **Paste the printed YAML snippet** into `accelerator.yaml -> scenario.agents[]`. The lint rule `agents_registered_in_manifest_match_code` enforces parity between the manifest and the `WORKERS` dict.
2. **Tune the `_build_input_<agent_id>` stub** in `workflow.py` if the default (pass each declared dependency's output plus `request`) isn't the right payload. The TODO comment marks the spot.

The scaffolder also extends `evals/quality/golden_cases.jsonl` for you: every existing case's `exercises` array gets the new agent id appended so the `agent_has_golden_case` lint rule passes immediately. Refine each case's `query` and `expected` fields when you wire the real evaluator — the stub only guarantees lint coverage, not eval quality.

## Tools
If the agent needs a side-effect tool (writes to a system, sends email/webhook, destructive action), run `/add-tool` for each separately — never mix tool creation with worker scaffolding, and ensure the tool flows through `src/accelerator_baseline/hitl.py`.

## Validate
```bash
python scripts/accelerator-lint.py   # must be 0 blocking / 0 warning
python -c "from src.main import app; print('OK')"
```

If lint reports `agent_has_golden_case` or `agents_registered_in_manifest_match_code`, revisit the two manual follow-ups above. If the scaffolder reports `workflow.py is no longer scaffold-managed`, someone has hand-edited the `from .agents import (...)` tuple, the `WORKERS` dict shape, or the close-brace line; restore the canonical shape (see the flagship `sales_research/workflow.py`) before retrying.

## Verify against acceptance
A new worker changes the supervisor's routing surface. Re-run the full acceptance chain against your deployed dev environment to confirm quality and safety still hold:

```bash
accel evaluate --api-url <your-api-url> --execute
```

If quality regresses on a worker the new agent should not have touched, the
supervisor is mis-routing — tighten the capability or
`_build_input_<agent_id>` payload.

## Guardrails
- Never hardcode Foundry system instructions in Python. The durable authoring
  source is `docs/agent-specs/<foundry-agent-name>.md`; shared provisioning
  overwrites portal drift on the next deployment sync.
- Never bypass the scaffolder to "just quickly add" a worker. The declarative `WORKERS` registry is the contract every future tool (scheduler, telemetry, lints, docs) reads.
- The supervisor is always-invoked; do not list it in `depends_on` or golden-case `exercises`.
