# Copilot instructions for this accelerator-based repo

> This file is read by GitHub Copilot (VS Code, Chat, code review) on every interaction in this repo. It encodes the **non-negotiable rules** that make a solution built from this template production-grade and compliant. Keep it in sync with the top-level `AGENTS.md`.

## What this repo is
A partner cloned the **Azure Agentic AI Solution Accelerator** template to build an agentic solution for a specific customer. The flagship shape is a **supervisor + specialist workers** orchestration on Microsoft Agent Framework + Microsoft Foundry. The customer-specific scope lives in `docs/discovery/solution-brief.md`. The accelerator's consistency contract lives in `accelerator.yaml`.

Preserve every rule below. When a request conflicts with a rule, refuse or propose a compliant alternative — do not "make it work" by weakening a guardrail.

## Unified local delivery interface

- Install the editable package before lifecycle work, then first run
  `accel --json --pretty next` (`python -m accelerator_cli --json --pretty
  next` is equivalent after installation).
- The CLI derives state from persistent repository and Azure artifacts. Never
  infer the engagement stage from chat history.
- `.agents/skills/accelerator/SKILL.md` is the portable workflow used by
  Copilot CLI and Codex. Claude Code uses the synchronized adapter under
  `.claude/skills/accelerator/`.
- Optional MCP clients use the same operations through `accel-mcp` after
  installing `.[mcp]`; do not implement lifecycle behavior in MCP prompts.
- Preview repository changes before `--apply`; request separate approval before
  `--execute`; surface destructive commands for the human operator.
- Customer documents enter `.accelerator/private/evidence.db` as local-only.
  Do not expose source text to a model until the user records an explicit
  disclosure decision.

## Build, test, and lint commands

Run commands from the repository root unless noted.

```powershell
# Install the runtime plus CI/dev tooling.
python -m pip install -e ".[dev]"

# Core CI-equivalent checks.
ruff check src patterns scripts
pyright src patterns
python scripts/accelerator-lint.py
python -m pytest -q

# One test file or one test.
python -m pytest tests/test_citations.py -q
python -m pytest tests/test_citations.py::test_assert_no_hallucinated_urls_fails_on_unknown_host -q

# SDK drift and change-impact preflight.
python scripts/ga-sdk-freshness.py
python scripts/explain-change.py
python -m pip_audit --local
```

Acceptance tests require a deployed endpoint:

```powershell
accel evaluate --api-url <api-url> --execute
accel evaluate --api-url <api-url> --foundry --execute  # optional native evaluators
```

Build the surfaces you changed:

```powershell
# Root self-host infrastructure.
az bicep build --file infra/main.bicep

# Explicit Hosted Agents preview infrastructure.
az bicep build --file deploy/hosted-preview/infra/main.bicep

# Documentation site.
python -m pip install -r requirements-docs.txt
python scripts/prepare-pages.py
python -m mkdocs build --strict

# Reference React UI (not part of the root CI build).
Set-Location patterns\sales-research-frontend
npm install
npm test
npm run typecheck
npm run build
npm audit
```

## High-level architecture

- **Authority is split deliberately.** The solution brief is the approved
  customer intent; `accelerator.yaml` is the executable contract; the
  gitignored evidence ledger stores local provenance.
- **Architecture is an approval gate.** `accel design` records agent type,
  orchestration, application shell, target, rationale, alternatives, approver,
  and requirements fingerprint. Never scaffold/deploy a stale decision.
  Foundry agent types are prompt and Hosted; workflow is orchestration.
- **Scenario loading is manifest-driven.** The registry resolves request and
  response schemas, experience metadata, workflow, endpoint, agents, retrieval,
  and eval paths into a `ScenarioBundle`.
- **The reference workbench is schema-driven.** `/scenario/metadata` drives
  generic inputs/results. Never render or retain raw `chunk` content; render
  only final output and explicitly validated partials.
- **There are three serving targets.**
  - Root `azure.yaml` + `src/main.py` is the default self-hosted FastAPI/Container Apps path. It exposes the scenario SSE endpoint and runs `src.bootstrap.bootstrap()` in the lifespan.
  - `deploy/foundry-prompt/` provisions prompt agents without application runtime code.
  - `deploy/hosted-preview/` + `src/agent_host.py` is the opt-in hosted-code
    path. The policy label remains because pinned hosting packages/extensions
    are prerelease. It exposes Responses and Invocations; `dev` remains
    self-hosted.
- **Infrastructure follows the serving target.** Root provisions the full app
  stack. Prompt-agent and Hosted targets share slim Foundry/Search/monitoring
  infrastructure; only Hosted stages runtime code.
- **Serving shares one SSE contract.** `src/serving/sse.py` validates before streaming, adds monotonic `seq`, converts heartbeats to `: ka`, emits in-band `error`, and always terminates with `done`. Keep the reference frontend types aligned with this event vocabulary.
- **Provisioning is shared and ordered.** `src/provisioning.py::provision()` creates Search schemas/seeds, then FoundryIQ knowledge sources/KB, then prompt-agent versions and Search RBAC, then the optional canary. `src/bootstrap.py` is only the self-host compatibility shim and no-ops in hosted mode.
- **The hosted workspace stages source; it is not a second codebase.** Edit root `src/`, `accelerator.yaml`, and `pyproject.toml`, then let `deploy/hosted-preview/hooks/prepare.py` regenerate ignored `app/src` and metadata. Do not edit generated files under `deploy/hosted-preview/app/`.
- **The worker graph is declarative.** `src/scenarios/<scenario>/workflow.py::WORKERS` is the only attachment point. `SupervisorDAG` schedules workers when dependencies are ready, creates fresh `WorkerState` per request, retries validation, propagates optional-worker skips, and fails fast for required workers. Aggregation and HITL execution remain outside workers.
- **New manifests use `foundry_tool` or `none`.** `python_injected` is a legacy
  runtime compatibility path. URL provenance propagates to dependent factual
  workers and is validated against live tool annotations.
- **CI is target-gated.** `deploy/environments.yaml` selects `selfhost`,
  `foundry-prompt`, or `hosted-preview`. Self-host runs full acceptance,
  prompt-agent runs provisioning/readback checks, and Hosted runs a protocol smoke.

## Glossary — three things called "agent"

The word "agent" is overloaded. Disambiguate before you act:

1. **Foundry agent** — model + system-prompt + tools in Microsoft Foundry. Instructions live in `docs/agent-specs/<name>.md` and are synced by `src/provisioning.py` (self-host startup through `src/bootstrap.py`; hosted preview through the postdeploy hook). Runtime invocation is centralized in the scenario workflow through Agent Framework's `FoundryAgent` with explicit version resolution.
2. **Microsoft Agent Framework worker** — Python module under `src/scenarios/<scenario>/agents/<agent_name>/` with the three-layer shape (`prompt.py` / `transform.py` / `validate.py`). Composed by the supervisor DAG. Scaffold via `scripts/scaffold-agent.py`.
3. **VS Code custom agent** — `.agent.md` specialist/compatibility prompt in
   `.github/agents/` (`/discover-scenario`, `/add-tool`, etc.). It assists with
   interviews or authoring but does not own lifecycle state.

When a doc/comment says "agent" without qualifier, infer from context: `.py` → #2, `docs/agent-specs/` → #1, `/slash-command` → #3.

---

## Hard rules — MUST / NEVER

### Identity & secrets
- MUST use `DefaultAzureCredential` or `ManagedIdentityCredential`. NEVER hardcode keys or connection strings.
- MUST resolve secrets from Azure Key Vault via references in Bicep or `DefaultAzureCredential` at runtime.
- NEVER commit `.env`, `*.pfx`, or any file with secrets. Don't weaken `.gitignore`.

### SDK & platform
- MUST use Microsoft Agent Framework (`agent_framework`) with Microsoft Foundry as the model backend.
- MUST author Foundry agent system instructions in `docs/agent-specs/<foundry_name>.md`. `src/provisioning.py` syncs each spec to the matching Foundry agent. Reuse the scenario workflow's Agent Framework invocation/version-resolution path; do not construct a parallel client path. NEVER hardcode system instructions inside Python code (`prompt.py` is the user-message envelope builder, not the system instruction). NEVER author instructions in the Foundry portal — provisioning overwrites portal drift.
- MUST pin SDK versions per `pyproject.toml` / `docs/version-matrix.md`.
- NEVER introduce LangChain, LlamaIndex, Haystack, or any other orchestration SDK. Microsoft Agent Framework only.
- NEVER instantiate OpenAI clients for agent inference. The provisioning-time
  seed-embedding path in `src/provisioning.py` is the only exception and must
  remain Entra-authenticated and isolated from agent reasoning.

### Agent structure (3-layer pattern)
Every agent lives under `src/scenarios/<scenario>/agents/<agent_name>/` with exactly three files:
- `prompt.py` — `build_prompt(request_data: dict) -> str`
- `transform.py` — `transform_response(response: str) -> dict`
- `validate.py` — `validate_response(response: dict) -> tuple[bool, str]`

Use `/add-worker-agent` (or the low-level `scripts/scaffold-agent.py`) rather
than hand-scaffolding. The transactional script updates the `WORKERS` registry,
`agents/__init__.py`, the three-layer files, the Foundry spec stub, and existing
golden-case `exercises` arrays. Paste its printed agent snippet into
`accelerator.yaml -> scenario.agents[]`.

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
- New manifests use `foundry_tool` (FoundryIQ KB over governed AI Search
  indexes) or `none`; `python_injected` via `src/retrieval/ai_search.py` is
  legacy runtime compatibility only.
- MUST return citations. `validate_response` rejects ungrounded factual claims.
- NEVER bypass governed retrieval with direct HTTP to content sources.
- NEVER inject retrieved content into the system prompt without a size cap; chunk and select.

### Telemetry
- MUST emit typed events via `src/accelerator_baseline/telemetry.py`. Custom KPI events declared in `accelerator.yaml -> kpis` MUST appear in code.
- MUST wire Application Insights via `azure-monitor-opentelemetry` in both `src/main.py` and `src/agent_host.py`. NEVER disable.
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
- When changing docs, run `scripts/prepare-pages.py` before strict MkDocs build. When changing Bicep, build the specific root or hosted-preview entrypoint.

---

## How to respond to common requests

### Adding a side-effect tool (e.g., "create a ServiceNow ticket")
1. Recommend `/add-tool` for a guided scaffold.
2. If coding directly: create `src/tools/<tool_name>.py`, wrap the side effect with `hitl.checkpoint(...)`, emit telemetry, add a unit test, add a redteam case.
3. Register it on the worker agent that should use it.
4. Never skip HITL.

### Continuing or resuming an engagement
1. Run `accel next` (or `python -m accelerator_cli next`).
2. Follow the returned `next_command`; do not infer stage from conversation.
3. Treat existing task-specific custom agents as compatibility adapters around
   the unified CLI.

### Adding a specialist worker agent
1. Confirm the approved architecture uses a Hosted workflow/supervisor, then
   run `/add-worker-agent`.
2. Create `src/scenarios/<scenario>/agents/<agent_name>/{prompt.py, transform.py, validate.py}`.
3. Register the agent in `accelerator.yaml` under `scenario.agents[]` and wire it into `src/scenarios/<scenario>/workflow.py`.
4. Update `src/scenarios/<scenario>/agents/supervisor/prompt.py` with the new worker's capability and routing cue.

### Switching solution shape
- The `single-agent` and `chat-with-actioning` variants are **documented walkthroughs** in `patterns/<variant>/README.md` — not drop-in packages. Run `/switch-to-variant single-agent` (or `chat-with-actioning`) to get a step-by-step walkthrough of re-authoring the scenario under `src/scenarios/<new-id>/` for the target shape; flagship HITL / telemetry / retrieval / content-filter invariants stay regardless of variant.

### Starting a new customer
- Run `accel next`, register source evidence, and use `/discover-scenario` for
  the interview.
- Run `accel design`, approve its recommendation (or record an override
  reason), then preview/apply `accel scaffold`.

### Deploying to a new Azure environment (partner dev / staging / customer subscription)
- Run `/deploy-to-env`. It adds an entry to `deploy/environments.yaml` (the source of truth for BYO-Azure deploy targets), creates the matching GitHub Environment, wires the OIDC federated credential, and dispatches a first deploy.
- Never hand-edit `deploy.yml` to add envs. The `resolve-env` job + the manifest are the contract; the `deploy_matrix_matches_azure_envs` lint rule enforces it.
- The azd environment name is **always** derived from `deploy/environments.yaml`. Never set `vars.AZURE_ENV_NAME` — that's drift.
- `deployment_target` is `selfhost`, `foundry-prompt`, or `hosted-preview`;
  omitted legacy values mean `selfhost`. `default_env` MUST remain selfhost.
- The `hosted-preview` target requires explicit acknowledgement, Python 3.14
  in the deployed runtime (Python 3.13+ is sufficient locally), pinned
  extensions, and operator RBAC values. `accel deploy` selects the nested
  workspace; direct recovery commands must change directory and must not rely
  on `azd -C`.

### Preflighting a change before commit / PR
- Run `/explain-change` (or `python scripts/explain-change.py`). It maps the current diff to the specific `accelerator-lint.py` rules, eval runners, and deploy-pipeline steps the change will trigger, plus a tailored recommended pre-commit command list.
- The preflight is read-only; CI gates (`accelerator-lint`, `evals`) remain authoritative. Run them locally before pushing.

### Assigning a different model to an agent
- Edit `accelerator.yaml`. Add a `models:` entry with a unique `slug` + `deployment_name` + `model`/`version`/`capacity` (Bicep provisions it on the next `azd up`), then set `scenario.agents[].model: <slug>` on the agent you want re-pointed.
- The reserved slug `default` is always the default deployment; omitting `model:` on an agent falls through to it.
- Bicep `loadYamlContent` compiles the block into the ARM template; `src/provisioning.py` resolves each agent's slug → deployment name. Lint rules `models_block_shape` + `agent_model_refs_exist` block malformed manifests at PR time.

---

## Things that will fail code review / lint (don't do these)
- OpenAI clients for agent inference. The only exception is the
  Entra-authenticated provisioning-time seed-embedding path in
  `src/provisioning.py`.
- `requests.post` to any LLM endpoint
- Hardcoded resource names, subscription IDs, tenant IDs
- Adding a side-effect tool without `hitl.checkpoint`
- Editing `src/accelerator_baseline/` to wrap Azure SDKs (it is for primitives only)
- Authoring agent system instructions in the Foundry portal (provisioning overwrites portal drift on the next sync) or hardcoding them inside Python code — use `docs/agent-specs/<foundry_name>.md`
- Disabling content filters, evals, or telemetry
- `time.sleep` in async code, bare `except:`, swallowing errors silently

---

## Reference
- Top-level: `README.md`, `QUICKSTART.md`, `AGENTS.md`
- Engagement: `accelerator.yaml`, `docs/discovery/solution-brief.md`
- Patterns: `docs/patterns/{architecture,waf-alignment,rai}/README.md`
- Scenarios: `docs/references/`
- Version matrix: `docs/version-matrix.md`
