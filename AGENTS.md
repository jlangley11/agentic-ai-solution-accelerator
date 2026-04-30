# Agent guidance — works across Copilot, Cursor, Claude Code, Codex CLI

> **This file documents the rules AI coding agents follow when working in this repo.** If you're a human partner, you don't need to read this — start at [README.md](README.md). If you're an AI agent (Copilot, Cursor, Cline, Claude Code, Codex CLI, etc.), the rules below are mandatory.

The authoritative copy of these rules is `.github/copilot-instructions.md`; this file is the IDE-agnostic mirror. Keep them in sync.

## Template intent
This repo is an Azure Agentic AI Solution Accelerator. A partner clones it
as a template, fills `docs/discovery/solution-brief.md` with a customer,
runs `/scaffold-from-brief`, then customizes with your help. Every change
you help with MUST preserve the accelerator's guardrails.

## Glossary — three things called "agent"

The word "agent" is overloaded in this repo. Disambiguate before you act:

1. **Foundry agent** — a model + system-prompt + tools deployment in
   Azure AI Foundry. System instructions live in
   `docs/agent-specs/<name>.md` and are synced to the portal at FastAPI
   startup by `src/bootstrap.py`. Code retrieves them via
   `AzureAIClient(agent_name=..., use_latest_version=True)`.
2. **Microsoft Agent Framework worker** — a Python module under
   `src/scenarios/<scenario>/agents/<agent_name>/` with the three-layer
   shape (`prompt.py` / `transform.py` / `validate.py`). The supervisor
   DAG composes these. Created via `python scripts/scaffold-agent.py …`.
3. **VS Code custom agent** — a `.agent.md` file in `.github/agents/`
   that shows up in the GitHub Copilot Chat agents dropdown (and as a
   `/<slug>` slash command). These drive the partner delivery motion
   (`/discover-scenario`, `/scaffold-from-brief`, `/define-grounding`,
   etc.). Historically called "chatmodes" — the migration to `.agent.md`
   was completed in Phase 2f-B.

When a doc or code comment says "agent" without qualifier, infer from
context: a `.py` file is meaning #2, a `docs/agent-specs/` reference is
#1, a `/slash-command` is #3.

## Non-negotiable rules (MUST / NEVER)

### Identity & secrets
- **MUST** use `DefaultAzureCredential` or `ManagedIdentityCredential`. Never embed keys or connection strings in code.
- **MUST** resolve secrets via Azure Key Vault references (Bicep) or `DefaultAzureCredential` (runtime). Never hardcode.
- **NEVER** commit `.env` files or secrets. `.gitignore` covers the common ones; don't weaken it.

### SDK & platform
- **MUST** use Microsoft Agent Framework (`agent_framework`) with Microsoft Foundry as the model backend. Do not introduce other orchestration frameworks.
- **MUST** author Foundry agent system instructions in `docs/agent-specs/<foundry_name>.md`. `src/bootstrap.py` syncs each spec to the matching Foundry agent on every `azd up` / `azd deploy`. **MUST** retrieve agents at runtime via `AzureAIClient(agent_name=..., use_latest_version=True)`. **NEVER** hardcode system instructions inside Python code (`prompt.py` is the user-message envelope builder, not the system instruction). **NEVER** author instructions in the Foundry portal — bootstrap overwrites portal drift on the next sync.
- **MUST** pin SDK versions per `pyproject.toml`. See `docs/version-matrix.md`; a weekly CI job validates against latest.

### Agent architecture (3-layer pattern per agent)
Every agent lives under `src/scenarios/<scenario>/agents/<agent_name>/` with three files:
- `prompt.py`   — `build_prompt(request_data) -> str`
- `transform.py` — `transform_response(response) -> dict`
- `validate.py`  — `validate_response(response) -> (bool, str)`
Add a new agent by running `python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id> --capability "<one-sentence capability>" [--depends-on a,b] [--optional]`; do not scaffold by hand. The scaffolder edits the declarative `WORKERS: dict[str, WorkerSpec]` registry in `src/scenarios/<scenario>/workflow.py` — that single dict is the supervisor DAG's only attachment point — and patches `agents/__init__.py`, creates the three-layer files, and writes a Foundry agent spec stub. It is transactional (rolls back on any failure) and re-run safe. You must still paste the printed YAML snippet into `accelerator.yaml -> scenario.agents[]` and add the new agent id to at least one golden case's `exercises` array (the `agent_has_golden_case` lint blocks otherwise). See the `/add-worker-agent` custom agent for the full flow. Scaffold a new *scenario* (sibling to `sales_research/`) with `python scripts/scaffold-scenario.py <id>`.

### HITL (Human-in-the-Loop)
- **MUST** gate every side-effect tool (writes, sends, destructive actions) through `src/accelerator_baseline/hitl.py`.
- **MUST** declare HITL policy in `accelerator.yaml -> solution.hitl` and per-tool in the tool module.
- **NEVER** let an agent execute a side-effect without an approved HITL checkpoint unless `accelerator.yaml -> solution.hitl = none` AND the action is reversible.

### Telemetry
- **MUST** emit typed events via `src/accelerator_baseline/telemetry.py`. Custom KPI events declared in `accelerator.yaml -> kpis` must appear in code.
- **MUST** wire Application Insights via `azure-monitor-opentelemetry` in `src/main.py` startup. Never disable.

### Grounding / RAG
- **MUST** cite retrieved sources in responses. `validate.py` must reject ungrounded responses when the agent claims facts.
- **MUST** use `src/retrieval/ai_search.py` (Azure AI Search) rather than direct HTTP to content sources.

### Responsible AI
- **MUST** have content filters applied via IaC (`infra/`), not portal. `controls.content_filters = iac` in `accelerator.yaml`.
- **MUST** keep `evals/redteam/` XPIA + jailbreak cases green in CI before deploy.
- **MUST** flag PII handling in the solution brief; RAI risks mapped to eval cases.
- See `docs/patterns/rai/README.md` for full RAI checklist.

### Well-Architected Framework (WAF) + Azure AI Landing Zone alignment
- **MUST** follow `docs/patterns/waf-alignment/README.md` for reliability, security, cost, op-ex, performance.
- **MUST** follow `docs/patterns/architecture/README.md` for topology.
- **MUST** pick a landing-zone tier in `accelerator.yaml` `landing_zone.mode` and keep `infra/` consistent with it. Tiers:
  - `standalone` — single-RG, public endpoints + Entra; for pilots / SMB / self-host.
  - `avm` — Azure Verified Modules + private endpoints + private DNS; for mid-market.
  - `alz-integrated` — customer's existing AI ALZ hub via `infra/alz-overlay/`; for enterprise/regulated.
  - See `docs/patterns/azure-ai-landing-zone/README.md` for the decision tree; use `/configure-landing-zone` to switch tiers. Lint rule `landing_zone_mode_consistent` enforces it.
- Private endpoints: `controls.private_endpoints = required` for any regulated workload (implies Tier 2 or Tier 3).

### CI & lint
- **MUST** keep `scripts/accelerator-lint.py` passing. Reads `accelerator.yaml` + repo state; enforces the rules above.
- **MUST** keep `evals/quality/` acceptance gates green before merge. Thresholds live in `accelerator.yaml -> acceptance`.

## Forbidden patterns (will fail lint / review)
- Constructing `openai.OpenAI()` or `AzureOpenAI()` directly. Use Agent Framework.
- `requests.post(...)` to an LLM endpoint. Use the SDK.
- Hardcoded resource names/IDs. Use env + Bicep params.
- `print()` for observability. Use structured telemetry.
- Editing `src/accelerator_baseline/` to wrap Azure SDKs (it is for primitives only).
- Moving agent instructions into code. They live in `docs/agent-specs/<foundry_name>.md` (`src/bootstrap.py` syncs them to the Foundry portal at FastAPI startup; never author instructions directly in the portal — they get overwritten on next deploy).

## When adding things
- **New tool** → `/add-tool` custom agent → creates `src/tools/<tool>.py` with HITL scaffolding + unit test.
- **New worker agent** → `/add-worker-agent` custom agent → creates the 3-layer module + wires into supervisor.
- **Per-agent model override** → edit `accelerator.yaml` `models:` block (add a slug entry), then set `scenario.agents[].model: <slug>`. Bicep `loadYamlContent` in `infra/main.bicep` parses the block at compile time on the next `azd up`; `infra/modules/foundry.bicep` provisions each extra deployment with the shared RAI policy (`@batchSize(1)` serialises the loop); `src/bootstrap.py` re-points the Foundry agent at FastAPI startup. Lint rules `models_block_shape` + `agent_model_refs_exist` enforce shape. Removing the block resets state to template defaults; raw env-var overrides are NOT supported.
- **New Azure environment** (partner dev/staging/customer sub) → `/deploy-to-env` custom agent → adds entry to `deploy/environments.yaml`, creates the GitHub Environment, wires OIDC, dispatches a deploy. Never hand-edit `deploy.yml` to add envs; the manifest + `resolve-env` job is the contract. The azd env name is **always** derived from `deploy/environments.yaml` — never set `vars.AZURE_ENV_NAME`.
- **Preflight a change before commit / PR** → `/explain-change` custom agent → runs `python scripts/explain-change.py` to map the current diff to the specific lint rules, evals, and deploy-pipeline steps it will trigger. Read-only; does not replace CI gates.
- **Pick or switch landing-zone tier** → `/configure-landing-zone` custom agent → walks the partner through choosing `standalone` / `avm` / `alz-integrated` based on the customer environment and updates `accelerator.yaml` + `infra/` accordingly. Uses exemplars in `infra/avm-reference/` (Tier 2) or the overlay skeleton in `infra/alz-overlay/` (Tier 3). Lint rule `landing_zone_mode_consistent` enforces the match.
- **Switching pattern** → `/switch-to-variant` custom agent → walks through re-authoring the scenario under `src/scenarios/<new-id>/` toward a `single-agent` or `chat-with-actioning` shape (documented walkthroughs in `patterns/<variant>/README.md`; not drop-in packages).
- **Starting a new customer engagement** → `/discover-scenario` then `/scaffold-from-brief`.

## References
- Onboarding: `docs/start/index.md` (partner walkthrough) and `docs/getting-started/setup-and-prereqs.md` (deep reference)
- Discovery guide: `docs/discovery/SOLUTION-BRIEF-GUIDE.md`
- `docs/agent-specs/README.md` — per-agent system instructions and bootstrap mechanics
- Patterns: `docs/patterns/{architecture,rai,waf-alignment}/README.md`
- Version matrix: `docs/version-matrix.md`
- Scenario catalog: `docs/references/`
