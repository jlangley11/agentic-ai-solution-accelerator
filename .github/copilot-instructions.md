# Copilot instructions for this accelerator-based repo

> This file is read by GitHub Copilot (VS Code, Chat, code review) on every interaction in this repo. It encodes the **non-negotiable rules** that make a solution built from this template production-grade and compliant. Keep it in sync with the top-level `AGENTS.md`.

## What this repo is
A partner cloned the **Azure Agentic AI Solution Accelerator** template to build an agentic solution for a specific customer. The flagship shape is a **supervisor + specialist workers** orchestration on Microsoft Agent Framework + Microsoft Foundry. The customer-specific scope lives in `docs/discovery/solution-brief.md`. The accelerator's consistency contract lives in `accelerator.yaml`.

Preserve every rule below. When a request conflicts with a rule, refuse or propose a compliant alternative — do not "make it work" by weakening a guardrail.

## Glossary — three things called "agent"

The word "agent" is overloaded. Disambiguate before you act:

1. **Foundry agent** — model + system-prompt + tools in Azure AI Foundry. Instructions live in `docs/agent-specs/<name>.md`, synced to portal by `src/bootstrap.py` at startup. Retrieved via `AzureAIClient(agent_name=..., use_latest_version=True)`.
2. **Microsoft Agent Framework worker** — Python module under `src/scenarios/<scenario>/agents/<agent_name>/` with the three-layer shape (`prompt.py` / `transform.py` / `validate.py`). Composed by the supervisor DAG. Scaffold via `scripts/scaffold-agent.py`.
3. **VS Code custom agent** — `.agent.md` file in `.github/agents/` that drives the partner delivery motion via Copilot Chat (`/discover-scenario`, `/scaffold-from-brief`, etc.). Historically called "chatmodes" before the Phase 2f-B migration.

When a doc/comment says "agent" without qualifier, infer from context: `.py` → #2, `docs/agent-specs/` → #1, `/slash-command` → #3.

---

## Hard rules — MUST / NEVER

### Identity & secrets
- MUST use `DefaultAzureCredential` or `ManagedIdentityCredential`. NEVER hardcode keys or connection strings.
- MUST resolve secrets from Azure Key Vault via references in Bicep or `DefaultAzureCredential` at runtime.
- NEVER commit `.env`, `*.pfx`, or any file with secrets. Don't weaken `.gitignore`.

### SDK & platform
- MUST use Microsoft Agent Framework (`agent_framework`) with Microsoft Foundry as the model backend.
- MUST author Foundry agent system instructions in `docs/agent-specs/<foundry_name>.md`. `src/bootstrap.py` syncs each spec to the matching Foundry agent on every `azd up` / `azd deploy`. MUST retrieve agents at runtime with `AzureAIClient(agent_name=..., use_latest_version=True)`. NEVER hardcode system instructions inside Python code (`prompt.py` is the user-message envelope builder, not the system instruction). NEVER author instructions in the Foundry portal — bootstrap overwrites portal drift on the next sync.
- MUST pin SDK versions per `pyproject.toml` / `docs/version-matrix.md`.
- NEVER introduce LangChain, LlamaIndex, Haystack, or any other orchestration SDK. Microsoft Agent Framework only.
- NEVER instantiate `openai.OpenAI(...)` or `AzureOpenAI(...)` directly. Use Agent Framework.

### Agent structure (3-layer pattern)
Every agent lives under `src/scenarios/<scenario>/agents/<agent_name>/` with exactly three files:
- `prompt.py` — `build_prompt(request_data: dict) -> str`
- `transform.py` — `transform_response(response: str) -> dict`
- `validate.py` — `validate_response(response: dict) -> tuple[bool, str]`

Do not hand-scaffold. Run `python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id> --capability "<one-sentence capability>" [--depends-on a,b]` to create a new worker. The scaffolder appends to the declarative `WORKERS: dict[str, WorkerSpec]` registry in the scenario's `workflow.py` (the single attachment point for the supervisor DAG), patches `agents/__init__.py`, writes the three-layer files, and emits a Foundry agent spec stub. It is transactional and re-run safe. Afterwards you must paste the printed YAML snippet into `accelerator.yaml -> scenario.agents[]` and add the agent id to at least one golden case's `exercises` array (lint enforces). See the `/add-worker-agent` custom agent for the full flow including the manifest + golden-case steps.

### Supervisor + workers wiring
- Workers are stateless. Supervisor routes based on intent classification in its prompt.
- Supervisor MUST emit a structured decision record (`src/accelerator_baseline/telemetry.py` event) naming which worker(s) it invoked and why.
- Aggregation (combining worker outputs) happens in an explicit executor, not inside a worker's transform.

### HITL (Human-in-the-Loop)
- MUST gate every side-effect tool through `src/accelerator_baseline/hitl.py.checkpoint(...)`.
- Side-effect = writes to external systems (CRM, ticketing, DB), sends (email, chat, webhook), destructive calls (restart, delete).
- HITL policy declared in `accelerator.yaml -> solution.hitl` AND per-tool in the tool module.
- NEVER bypass HITL "just for a demo." If `hitl = none`, the action MUST be reversible and MUST be logged.

### Grounding / RAG
- MUST use `src/retrieval/ai_search.py` (Azure AI Search) for retrieval. No direct HTTP to content sources.
- MUST return citations. `validate_response` rejects ungrounded factual claims.
- NEVER inject retrieved content into the system prompt without a size cap; chunk and select.

### Telemetry
- MUST emit typed events via `src/accelerator_baseline/telemetry.py`. Custom KPI events declared in `accelerator.yaml -> kpis` MUST appear in code.
- MUST wire Application Insights via `azure-monitor-opentelemetry` in `src/main.py` startup. NEVER disable.
- NEVER use `print()` or ad-hoc logging for observability.

### Responsible AI
- MUST apply Azure AI content filters via IaC (`infra/modules/foundry.bicep`). `controls.content_filters = iac` in `accelerator.yaml`.
- MUST keep `evals/redteam/` XPIA + jailbreak suites passing. New tools trigger new redteam cases.
- MUST flag PII handling in the solution brief; map RAI risks to eval cases.
- See `docs/patterns/rai/README.md` for the full RAI checklist.

### Well-Architected Framework + Azure AI Landing Zone
- Follow `docs/patterns/waf-alignment/README.md` (reliability · security · cost · op-ex · performance).
- Follow `docs/patterns/architecture/README.md` for topology.
- Pick a landing-zone tier in `accelerator.yaml` `landing_zone.mode`: `standalone` (pilot/SMB), `avm` (mid-market with AVM + PE), or `alz-integrated` (enterprise with existing AI ALZ hub). See `docs/patterns/azure-ai-landing-zone/README.md`; use `/configure-landing-zone` to switch. Lint rule `landing_zone_mode_consistent` enforces the infra/ shape matches.
- Regulated workloads: `controls.private_endpoints = required` AND `controls.key_vault = true` (implies Tier 2 or Tier 3).

### CI gates
- MUST keep `scripts/accelerator-lint.py` green. It reads `accelerator.yaml` + repo state.
- MUST keep `evals/quality/` acceptance thresholds from `accelerator.yaml -> acceptance` green before merge.
- MUST NOT disable the `version-matrix.yml` weekly job.

---

## How to respond to common requests

### Adding a side-effect tool (e.g., "create a ServiceNow ticket")
1. Recommend `/add-tool` for a guided scaffold.
2. If coding directly: create `src/tools/<tool_name>.py`, wrap the side effect with `hitl.checkpoint(...)`, emit telemetry, add a unit test, add a redteam case.
3. Register it on the worker agent that should use it.
4. Never skip HITL.

### Adding a specialist worker agent
1. Run `/add-worker-agent`.
2. Create `src/scenarios/<scenario>/agents/<agent_name>/{prompt.py, transform.py, validate.py}`.
3. Register the agent in `accelerator.yaml` under `scenario.agents[]` and wire it into `src/scenarios/<scenario>/workflow.py`.
4. Update `src/scenarios/<scenario>/agents/supervisor/prompt.py` with the new worker's capability and routing cue.

### Switching solution shape
- The `single-agent` and `chat-with-actioning` variants are **documented walkthroughs** in `patterns/<variant>/README.md` — not drop-in packages. Run `/switch-to-variant single-agent` (or `chat-with-actioning`) to get a step-by-step walkthrough of re-authoring the scenario under `src/scenarios/<new-id>/` for the target shape; flagship HITL / telemetry / retrieval / content-filter invariants stay regardless of variant.

### Starting a new customer
- Run `/discover-scenario` to fill `docs/discovery/solution-brief.md`.
- Then `/scaffold-from-brief` to customize prompts, tools, retrieval, HITL, evals, manifest.

### Deploying to a new Azure environment (partner dev / staging / customer subscription)
- Run `/deploy-to-env`. It adds an entry to `deploy/environments.yaml` (the source of truth for BYO-Azure deploy targets), creates the matching GitHub Environment, wires the OIDC federated credential, and dispatches a first deploy.
- Never hand-edit `deploy.yml` to add envs. The `resolve-env` job + the manifest are the contract; the `deploy_matrix_matches_azure_envs` lint rule enforces it.
- The azd environment name is **always** derived from `deploy/environments.yaml`. Never set `vars.AZURE_ENV_NAME` — that's drift.

### Preflighting a change before commit / PR
- Run `/explain-change` (or `python scripts/explain-change.py`). It maps the current diff to the specific `accelerator-lint.py` rules, eval runners, and deploy-pipeline steps the change will trigger, plus a tailored recommended pre-commit command list.
- The preflight is read-only; CI gates (`accelerator-lint`, `evals`) remain authoritative. Run them locally before pushing.

### Assigning a different model to an agent
- Edit `accelerator.yaml`. Add a `models:` entry with a unique `slug` + `deployment_name` + `model`/`version`/`capacity` (Bicep provisions it on the next `azd up`), then set `scenario.agents[].model: <slug>` on the agent you want re-pointed.
- The reserved slug `default` is always the default deployment; omitting `model:` on an agent falls through to it.
- Pre-provision YAML parsing (Bicep `loadYamlContent` in `infra/main.bicep`) compiles the block into the ARM template; FastAPI startup bootstrap (`src/bootstrap.py`) resolves each agent's slug → deployment name. Lint rules `models_block_shape` + `agent_model_refs_exist` block malformed manifests at PR time.

---

## Things that will fail code review / lint (don't do these)
- `openai.OpenAI()` / `AzureOpenAI()` direct instantiation
- `requests.post` to any LLM endpoint
- Hardcoded resource names, subscription IDs, tenant IDs
- Adding a side-effect tool without `hitl.checkpoint`
- Editing `src/accelerator_baseline/` to wrap Azure SDKs (it is for primitives only)
- Authoring agent system instructions in the Foundry portal (bootstrap overwrites portal drift on the next sync) or hardcoding them inside Python code — use `docs/agent-specs/<foundry_name>.md`
- Disabling content filters, evals, or telemetry
- `time.sleep` in async code, bare `except:`, swallowing errors silently

---

## Reference
- Top-level: `README.md`, `QUICKSTART.md`, `AGENTS.md`
- Engagement: `accelerator.yaml`, `docs/discovery/solution-brief.md`
- Patterns: `docs/patterns/{architecture,waf-alignment,rai}/README.md`
- Scenarios: `docs/references/`
- Version matrix: `docs/version-matrix.md`
