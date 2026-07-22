---
name: scaffold-from-brief
description: Compatibility specialist for customer-specific authoring after the deterministic accel design/scaffold preview and apply flow.
tools: ['codebase', 'editFiles', 'search', 'terminal']
handoffs:
  - label: Define grounding per worker
    agent: define-grounding
    prompt: The scenario package is scaffolded. Run /define-grounding to wire FoundryIQ knowledge bases, Search indexes, and read-only catalog intent.
    send: false
---

# /scaffold-from-brief — generate a scenario from the discovery brief

> Compatibility adapter: use `accel design` and
> `accel scaffold --scenario-id <id> --dry-run` for authoritative readiness,
> preview, and apply behavior.

You are applying the customer's filled brief to this repo. `accel design` and
`accel scaffold` own readiness, transactional file creation, and the
`accelerator.yaml` scenario update. Your job is to guide customer-specific
authoring after the approved scaffold.

## Preflight
1. Open `docs/discovery/solution-brief.md`. If any section is missing or contains `TBD`, STOP and reply: "Run `/discover-scenario` first to fill the brief." Then stop.
2. Open `accelerator.yaml`. Check whether the existing `scenario:` block is the flagship (`id: sales-research`) or a prior partner-scaffolded scenario.
3. Confirm a scenario id (lowercase-with-hyphens, e.g. `order-triage`, `claims-intake`).

## Step 1 — Preview and apply the scaffold
```powershell
accel design
accel scaffold --scenario-id <scenario-id> --dry-run
```

Present the dry-run file/manifest actions and obtain explicit approval. Only
then run `accel scaffold --scenario-id <scenario-id> --apply`.
This materializes:
- `src/scenarios/<package>/{__init__,schema,workflow,retrieval}.py`
- `src/scenarios/<package>/agents/supervisor/{__init__,prompt,transform,validate}.py`
- `docs/agent-specs/accel-<scenario-id>-supervisor.md`
- `data/samples/<package>.json`

Package leaf is auto-derived (hyphens → underscores). The CLI fails fast if any target exists, and rolls back on partial failure.

## Step 2 — Re-sync engagement fields

`accel scaffold` updates the `scenario:` block automatically. Re-sync the
remaining engagement fields from the approved brief:
- `solution.name` → engagement slug (lowercase-with-hyphens)
- `solution.pattern` / `hitl` / `data_residency` / `identity`
- `solution.side_effect_tools` → tools your scenario will call (each must exist under `src/tools/` and pass HITL)
- `solution.grounding_sources[]` → preserve each source's classification,
  PII flag, and identity-enforcement mode from brief Section 5e
- `acceptance.*` → thresholds drawn from the brief's success criteria
- `kpis[]` → instrumentation events the scenario will emit

## Step 3 — Customize per the brief

| Brief section | Apply to |
|---|---|
| 1. Problem + persona | `docs/agent-specs/<foundry_name>.md` — Foundry system instructions |
| 5b–5d. UX | `scenario.response_schema` + `scenario.experience`; generic workbench metadata |
| 5. Solution shape (not supervisor-routing) | Drop the supervisor stub and re-shape `workflow.py` for `single-agent` or `chat-with-actioning` |
| 5. Grounding sources | Edit `src/scenarios/<package>/retrieval.py` — add fields/connectors; declare additional indexes under `scenario.retrieval.indexes` and re-run scaffolder for new agents if needed |
| 5. Side-effect tools | Create `src/tools/<tool_name>.py`, each wrapped with `hitl.checkpoint(...)`; reference the tool name from the supervisor's `requires_approval` output |
| 5. HITL gates | `src/accelerator_baseline/hitl.py` — rules per tool + confidence threshold |
| 6. Constraints | `infra/main.parameters.json` + `accelerator.yaml.controls.*` |
| 3+7. Success criteria → acceptance | `evals/quality/golden_cases.jsonl` — the scaffolder seeded a stub case `q-001` exercising every scaffolded worker; refine the `query` and `expected` fields to encode real success criteria, then add 4+ more cases |
| 6. RAI risks | `evals/redteam/cases.jsonl` — one case per risk |
| 4. KPIs | `src/accelerator_baseline/telemetry.py` — register each named KPI event; `infra/dashboards/roi-kpis.json` — append a `KqlItem/1.0` entry under `items[]` per KPI |

## Step 4 — Add additional worker agents (optional)
If the brief implies more than a supervisor, run `/add-worker-agent` (or
`scripts/scaffold-agent.py`) for each worker. Do not hand-scaffold packages.
Then use `/implement-workers` to fill the three-layer modules and Foundry specs.

## Step 5 — Validate
```powershell
accel review
accel validate --full --execute
```
The lint's `scenario-manifest` check validates every import ref in the new `scenario:` block; `agents-three-layer` verifies the package's `agents/` directory contains complete three-layer agents.

## Step 6 — Surface the UX-shape next step

Read the `## UX shape` / `ux_shape` field from `docs/discovery/solution-brief.md` and print the matching next-step block. Do **not** scaffold any frontend code — frontend forking is a manual decision. Just signpost:

| `ux_shape` value | Print to chat |
|---|---|
| **Structured form + report** | "The Accelerator Workbench reads request/response schemas and `experience.output_sections` from `/scenario/metadata`. Confirm those contracts first; add tailored React layouts only where the generic renderers are insufficient." |
| **Chat** | "No chat UI pattern shipped yet. The `chat-with-actioning` backend pattern supports this shape — build the UI on top (or use any chat UI framework). Consume `/<scenario>/stream` from your client." |
| **Dashboard / viewer** | "Have the customer's app consume `/scenario/metadata` plus the declared SSE endpoint — see `scenarioClient.ts` and `types/scenario.ts`." |
| **API-only / embed** | "No UI. The hosted SSE endpoint at `/<scenario>/stream` IS the deliverable. Hand the URL + auth scheme to the integrating system (Power Automate, n8n, partner platform)." |
| TBD / missing | "The brief's `ux_shape` field is empty. Re-run `/discover-scenario` to fill it before deciding on a frontend." |

### Step 6a — Form + report deep-dive (only when `ux_shape` is `Structured form + report`)

Read the brief's `## UX inputs` and `## UX output sections` tables. If either is missing or still contains `TBD`, reply: "Re-run `/discover-scenario` to fill the UX inputs / UX output sections tables before continuing." Then stop.

1. **Print `## UX inputs` back verbatim**, then ensure the scenario request
   Pydantic model declares those fields. `DynamicSchemaForm.tsx` renders them.

2. **Print `## UX output sections` back verbatim**, then ensure
   `ScenarioResponse` and `scenario.experience.output_sections` use matching
   keys. `DynamicResultPanel.tsx` renders validated output automatically.

3. **Emit `docs/discovery/ux-blueprint.md`** — a generated reference doc that persists both tables for downstream work. Use this template, substituting the tables verbatim from the brief:

   ```markdown
   # UX blueprint — <scenario-id>

   > Generated by `/scaffold-from-brief` from `docs/discovery/solution-brief.md`.
   > This is a **reference snapshot** of the form+report contract — keep it
   > in sync with the brief if either changes. Wired to:
   > `patterns/sales-research-frontend/src/components/DynamicSchemaForm.tsx`,
   > `patterns/sales-research-frontend/src/components/DynamicResultPanel.tsx`,
   > `src/scenarios/<pkg>/schema.py`,
   > `src/scenarios/<pkg>/agents/supervisor/transform.py`.

   ## Inputs (form fields)

   <copy `## UX inputs` table from the brief>

   ## Output sections (result panels)

   <copy `## UX output sections` table from the brief>
   ```

   Overwrite if the file already exists; the approved brief is the intent
   contract and the scenario schemas are the executable UI contract.

## Guardrails
- NEVER hardcode Foundry agent system instructions inside Python. The durable
  authoring source is `docs/agent-specs/<foundry_name>.md`; `prompt.py` is the
  user-message envelope. Shared provisioning overwrites portal drift on the
  next deployment sync.
- NEVER weaken HITL, telemetry, evals, or content-filter controls to fit the brief. If the brief implies they should be weakened, flag the conflict — don't comply.
- Keep all edits consistent with `.github/copilot-instructions.md`.
- If the brief demands a stack other than Agent Framework + Foundry, STOP and escalate. This template doesn't support alternative stacks.

## Output
Summarize as a table: file changed, reason (which brief section drove it), whether it needs further human authoring (e.g., golden cases, retrieval connector credentials).
