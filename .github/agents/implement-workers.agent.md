---
name: implement-workers
description: Walk the entire WORKERS DAG and implement every scaffolded-but-unfinished worker by invoking /implement-worker for each, in dependency order. Use this after /scaffold-from-brief when you want to fill in all stubs in one pass.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
---

# /implement-workers — finish every scaffolded worker in one pass

> Compatibility adapter: run `accel next` before implementation and
> `accel validate` after the worker set is complete. — finish every scaffolded worker in one pass

Use this when `/scaffold-from-brief` (or a sequence of `/add-worker-agent` calls) has stood up the structural shape of a multi-worker scenario but the three-layer files are still stubs. This custom agent delegates to `/implement-worker` for each worker, walking the supervisor DAG in dependency order so upstream context is always available before downstream workers are filled in.

## Preconditions
- `accelerator.yaml -> scenario.agents[]` lists every worker.
- `src/scenarios/<scenario>/workflow.py` declares the canonical `WORKERS: dict[str, WorkerSpec] = { ... }` registry.
- `docs/discovery/solution-brief.md` is filled.
- `/define-grounding` has run (every agent has a settled `retrieval.mode` and the index list is final).
- `evals/quality/golden_cases.jsonl` is auto-seeded by the scaffolders:
  `scaffold-scenario.py` creates `q-001` and `scaffold-agent.py` appends worker
  ids to `exercises`. Refine `query` and `expected` so the first
  `accel evaluate` run measures real customer criteria.

If any precondition fails, fix it first — implementing workers against a moving manifest produces drift.

## How it walks the DAG

1. Read `accelerator.yaml -> scenario.agents[]` and `WORKERS` in `workflow.py`. Build the agent set.
2. Topologically sort by `WorkerSpec.depends_on` (the supervisor is always first, transformational leaves are last).
3. For each worker, in order:
   - Skip if its three-layer files are no longer stubs (look for the scaffolder's TODO markers in `prompt.py`).
   - Otherwise invoke `/implement-worker <worker_id>`.
   - After each worker completes, run a quick subset validation:
     ```bash
     python -m ruff check src/scenarios/<scenario>/agents/<worker_id>/
     python -m pytest tests/ -k "<worker_id>" --no-header -q
     ```
   - If validation fails, **stop** and surface the error rather than continuing — a bad upstream worker contaminates every downstream `/implement-worker` invocation.

## Per-worker prompt to use

When invoking `/implement-worker` for each worker, pass it:
- The worker id and scenario id.
- The dependency outputs it will receive at runtime (read from each dependency's spec file).
- The relevant slice of the discovery brief (section 1 problem, section 5 worker-specific guidance).
- The `retrieval.mode` and `catalog_tools` from the manifest entry.

This avoids re-loading the brief on every per-worker call — context is threaded explicitly.

## After every worker is implemented

Run the full gate stack:

```bash
python -m ruff check src/ tests/
python scripts/accelerator-lint.py
python -m pytest tests/ --no-header -q
python -c "from src.main import app; print('OK')"
```

Then exercise quality + redteam against your dev environment:

```bash
accel evaluate --api-url <your-api-url> --execute
```

The unified evaluator reports every acceptance threshold and produces the
artifact used during UAT.

## Guardrails
- Never run multiple `/implement-worker` invocations in parallel — they need to read each other's specs to wire build_input correctly.
- Never skip the per-worker validation step. A regression caught after worker N+1 is implemented costs N+1 hours to bisect.
- Never re-run this custom agent after partial completion; re-invoke `/implement-worker` directly for the specific worker that failed. This custom agent is for the **clean-slate** fill-in.
