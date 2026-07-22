---
name: switch-to-variant
description: Switch the repo from the flagship supervisor-routing pattern to a simpler variant (single-agent or chat-with-actioning), or vice versa.
tools: ['codebase', 'editFiles', 'search', 'terminal']
---

# /switch-to-variant — change the solution shape

> Compatibility adapter: run `accel design` before selecting a variant and
> `accel validate` after re-authoring the scenario.

Use this only after `accel design` indicates that the current orchestration or
application shell is over- or under-powered. Agent type and deployment target
are approved in `accelerator.yaml.architecture`, not selected independently here.

## Choices
- **single-agent** — one agent + retrieval + 1–2 tools. Best for narrow Q&A-with-actioning.
- **chat-with-actioning** — conversational front-end with tools + HITL. Best when UX is a chat thread.
- **supervisor-routing** — flagship default; 2+ specialists + aggregation.

## Actions by target

### → single-agent
The `single-agent` variant is documented in `patterns/single-agent/README.md`. It is a manual re-authoring walkthrough, not a drop-in package. To switch:
1. Approve `single-agent` orchestration through `accel design`, then run
   `accel scaffold`; prompt-agent decisions generate a `primary` package.
2. Consolidate system instructions in `docs/agent-specs/<foundry_name>.md`;
   `prompt.py` remains the per-request envelope.
3. Keep one or two most-used tools; drop the rest.
4. Point `accelerator.yaml.scenario.id` at the new scenario; archive the flagship scenario under `src/scenarios/sales_research/` (git history preserves).
5. Keep `solution.pattern`, `scenario.implementation`, and
   `architecture.decision` aligned.
6. Update the flagship diagram in `docs/patterns/architecture/README.md` to match the new shape (or replace it with a single-agent diagram).

### → chat-with-actioning
The `chat-with-actioning` variant is documented in `patterns/chat-with-actioning/README.md`. It is a manual re-authoring walkthrough, not a drop-in package. To switch:
1. Author a new scenario package with a conversation loop and tool-backed workers.
2. Wire session/thread state (`agent_framework` thread management).
3. Set `accelerator.yaml.solution.pattern: chat-with-actioning`.
4. Confirm HITL still gates every side-effect in the chat loop.

### → supervisor-routing
1. If coming from a single-agent scenario, split the prompt into worker-aligned capabilities; each becomes a worker.
2. Re-author `src/scenarios/<scenario>/agents/supervisor/` and `src/scenarios/<scenario>/workflow.py` using flagship `src/scenarios/sales_research/` as a reference.
3. Identify ≥2 workers; update supervisor prompt with routing cues.
4. Set `accelerator.yaml.solution.pattern: supervisor-routing`.

## Post-switch
- Run `scripts/accelerator-lint.py`.
- Re-run `evals/quality/` locally; thresholds may need revisiting.
- Commit: `chore: switch pattern to <variant>`.

## Guardrails
- Do NOT silently delete customer-specific logic; move it into the new shape.
- HITL, telemetry, retrieval, content filters stay regardless of variant.
- "Turn off HITL to simplify chat" → refuse; HITL is pattern-agnostic.
