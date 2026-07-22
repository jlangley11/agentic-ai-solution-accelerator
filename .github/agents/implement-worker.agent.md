---
name: implement-worker
description: Implement one scaffolded worker — fill prompt.py, transform.py, validate.py, and the Foundry agent spec from the discovery brief and scenario manifest. Run after the worker has been added via /add-worker-agent or /scaffold-from-brief.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
---

# /implement-worker — fill in a scaffolded worker

> Compatibility adapter: run `accel next` before implementation and
> `accel validate` after the worker is complete. — fill in a scaffolded worker

Use this after a worker has been **structurally** added (by `/add-worker-agent` or as part of `/scaffold-from-brief`) but the three layer files (`prompt.py`, `transform.py`, `validate.py`) and the Foundry agent spec are still stubs. This custom agent produces a working, validated worker — no manual code-writing required.

## Preconditions
- `accelerator.yaml -> scenario.agents[]` lists the worker.
- `src/scenarios/<scenario>/agents/<worker_id>/` exists with stub `prompt.py`, `transform.py`, `validate.py`, `__init__.py` (the scaffolder always emits these).
- `docs/agent-specs/<foundry_name>.md` exists as a stub (the scaffolder always emits this).
- `docs/discovery/solution-brief.md` is filled (section 1 problem framing, section 2 personas, section 5 solution shape).

If the worker isn't scaffolded yet, run `/add-worker-agent` first. **Do not hand-write the three-layer files** — the canonical shape is contract for every future tool.

## Inputs to gather
1. **Worker id** (e.g. `account_planner`) — the directory name under `src/scenarios/<scenario>/agents/`.
2. **Scenario id** (e.g. `sales-research`) — `accelerator.yaml -> scenario.id`.

Read the matching `scenario.agents[]` entry to learn:
- `foundry_name` — the Foundry agent identifier; controls which spec file to write.
- `retrieval.mode` — drives validator opt-ins (citations, hallucinated-URL check).
- `catalog_tools` (if any) — read-only environment attachments only; drives
  prompt guidance about when to invoke them.

Read `docs/discovery/solution-brief.md` for the worker's role; the supervisor's prompt usually carries a one-line capability sentence — that capability is the worker's contract.

## What you write

### A. `docs/agent-specs/<foundry_name>.md` — system instructions (source of truth)
This is the **only** place the system instructions live. Shared provisioning
syncs it at self-host startup (through `src/bootstrap.py`) or Hosted preview
postdeploy; portal edits are overwritten on the next sync.

Fill the spec with:
- A one-sentence role definition, mirroring the supervisor's capability cue.
- The output JSON schema (field-by-field) the worker must emit, reading from the discovery brief.
- Tool-use rules: when to call the FoundryIQ Knowledge Base, when (if ever) to call a catalog tool, when to refuse.
- Citation policy: every factual field must carry a citation entry under the response's `citations` field.
- Refusal policy: when the worker should emit `{}` or a stub rather than guessing.

### B. `prompt.py` — `build_prompt(request_data: dict) -> str`
Prompt = the **user message** envelope sent to the agent. System instructions live in the spec file (above), not here.

Pull from `request_data`:
- The raw user request (`request_data["request"]`).
- The output of every dependency the worker declares in `WorkerSpec.depends_on` (each dependency dropped a `dict` into the same `request_data`).

Format the prompt as a short, structured user message: a one-line restatement of the task, followed by the upstream context as labeled blocks. Keep it under ~2 KB — the agent's spec already carries the heavyweight instructions.

### C. `transform.py` — `transform_response(raw: str | dict) -> dict`
Parse the raw response into the dict shape the worker advertises in its agent spec. Be defensive:
- Accept both `str` (JSON-string) and `dict` (already-parsed) input — flagship workers do this.
- Tolerate missing fields by returning empty defaults that the validator will catch (don't raise here).
- Coerce types (str → list when the agent emits a comma-separated string) only if the brief calls for it.

### D. `validate.py` — `validate_response(response: dict) -> tuple[bool, str]`
Three layered checks, in order:

1. **Required fields** — declared at module top as `REQUIRED_FIELDS: tuple[str, ...]`. Loop and return on first miss.
2. **Cross-agent contamination** — declared as `FORBIDDEN_FIELDS: tuple[str, ...]` (fields owned by other workers in the DAG). Reject if present, naming the owner.
3. **Groundedness** — opt-in based on `retrieval.mode`:
   - **`foundry_tool` mode**: use both citation helpers from `src.accelerator_baseline.citations`.
     ```python
     from src.accelerator_baseline.citations import (
         assert_no_hallucinated_urls,
         require_citations,
     )

     ok, msg = require_citations(
         response, when_fields_present=("<factual_field_a>", "<factual_field_b>")
     )
     if not ok:
         return False, msg

     citations = response.get("citations") or []
     if isinstance(citations, list):
         retrieved = response.get("_retrieved_uris", []) or []
         ok, msg = assert_no_hallucinated_urls(citations, retrieved)
         if not ok:
             return False, msg
     ```
     `_retrieved_uris` is stamped onto the response by the supervisor (Phase 2c.2) — it carries the URI list the Foundry tool trace surfaced for this turn. The validator fails open when the trace was empty (unit tests, ungrounded fallback).
   - **`none` mode**: omit the citation checks entirely; the worker has no facts to ground.

The flagship `account_planner` validator is the canonical reference — read `src/scenarios/sales_research/agents/account_planner/validate.py`.

## Output contract

Every populated worker layer file must be **deterministic** for a given input — `build_prompt`, `transform_response`, `validate_response` are pure functions (no I/O, no globals, no time-of-day). Tests must run them with handcrafted inputs without spinning up Foundry.

## Validate

```bash
python -m ruff check src/ tests/
python -m pytest tests/ -k "<worker_id>" --no-header -q
python scripts/accelerator-lint.py
```

Add a unit test under `tests/test_<worker_id>.py` that exercises:
- Happy path through all three layers.
- Each `REQUIRED_FIELDS` miss (one test per field).
- Hallucinated URL rejection when in `foundry_tool` mode.

## Verify against acceptance

```bash
accel evaluate --api-url <your-api-url> --execute
```

If the worker drifts another worker's quality numbers, the supervisor is mis-routing — refine the worker's capability sentence in the supervisor's prompt and re-deploy.

## Guardrails
- **Never** put system instructions in `prompt.py` — they belong in the spec file.
- **Never** mutate `request_data` inside `build_prompt`; treat it as read-only.
- **Never** raise from `transform_response`; let the validator surface the failure.
- **Never** call out to Foundry, AI Search, or any external system from these three files. The supervisor + `_invoke_agent` are the only orchestration points.
- **Never** edit `accelerator.yaml -> scenario.agents[]` from this custom agent — that's `/define-grounding`.
