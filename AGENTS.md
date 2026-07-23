# Agent guidance — works across Copilot, Cursor, Claude Code, Codex CLI

> **This file documents the rules AI coding agents follow when working in this repo.** If you're a human partner, you don't need to read this — start at [README.md](README.md). If you're an AI agent (Copilot, Cursor, Cline, Claude Code, Codex CLI, etc.), the rules below are mandatory.

This file is the portable contract for Copilot CLI, Codex, Claude Code, and
other coding agents. `.github/copilot-instructions.md` carries equivalent
GitHub-specific guidance; keep the non-negotiable rules aligned.

## Template intent
This repo is an Azure Agentic AI Solution Accelerator. A partner clones it
as a template, runs `accel next`, approves discovery requirements, and
materializes a customer scenario. Specialist agents help with interviews and
authoring; the CLI owns lifecycle state and approval boundaries. Every change
MUST preserve the accelerator's guardrails.

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
  installing `.[mcp]`; MCP never creates a parallel lifecycle implementation.
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
# Optional consumption-based Foundry evaluators:
accel evaluate --api-url <api-url> --foundry --execute
```

Build the surfaces you changed:

```powershell
az bicep build --file infra/main.bicep
az bicep build --file deploy/hosted-preview/infra/main.bicep

python -m pip install -r requirements-docs.txt
python scripts/prepare-pages.py
python -m mkdocs build --strict

Set-Location patterns\sales-research-frontend
npm install
npm test
npm run typecheck
npm run build
npm audit
```

## High-level architecture

- **Authority is split deliberately.** `docs/discovery/solution-brief.md` is the
  customer-approved intent contract. `accelerator.yaml` is the executable
  deployment/scenario contract. `.accelerator/private/evidence.db` stores
  local provenance and is never committed. Do not create a parallel config.
- **Architecture is an approval gate.** `accel design` records agent type,
  implementation pattern, orchestration, application shell, deployment target,
  rationale, alternatives, approver, and requirements fingerprint under
  `accelerator.yaml.architecture`.
  Never scaffold or deploy a stale decision. Foundry agent types are prompt and
  Hosted; implementation patterns are `managed-prompt`, `harness`, and
  `custom-workflow`; workflow is an orchestration pattern.
- **Architecture diagrams are governed scaffold artifacts.** Generate Azure
  resource diagrams with Azure Architecture Diagram Builder MCP v1.0.0 using
  `list_services`, `validate_architecture`, then `render_diagram`. Commit the SVG
  and checksum-bound `.mcp.json` provenance; never hand-edit generated SVGs.
  Diagram findings do not override the approved architecture decision.
- **Scenario loading is manifest-driven.** `load_scenario()` resolves request
  and response schemas, experience metadata, workflow, endpoint, agents,
  retrieval, and eval paths into a `ScenarioBundle`.
- **The reference UI is schema-driven.** `/scenario/metadata` feeds
  `DynamicSchemaForm` and `DynamicResultPanel`. Generic UIs render only
  workflows that explicitly advertise validated partials; raw `chunk` content
  is never rendered or retained.
- **Metadata and browser state are disclosure-safe.** Scenario metadata may
  expose the approved implementation shape, never secret/approver
  configuration. Browser history is opt-in local storage with visible privacy
  and deletion controls; do not render saved request values in navigation.
- **There are three serving targets.**
  - Root `azure.yaml` + `src/main.py` is the default self-hosted FastAPI/Container Apps path.
  - `deploy/foundry-prompt/` provisions prompt agents without application
    runtime compute.
  - `deploy/hosted-preview/` + `src/agent_host.py` is the opt-in hosted-code
    target. The repo retains the `hosted-preview` policy label because its
    pinned serving packages/extensions remain prerelease. `dev` stays
    self-hosted.
- **Infrastructure follows the serving target.** Root provisions the full
  application stack. `foundry-prompt` and `hosted-preview` share slim
  Foundry/Search/monitoring infrastructure; only Hosted preview stages runtime
  code.
- **Serving shares one SSE contract.** `src/serving/sse.py` validates before streaming, adds monotonic `seq`, converts heartbeats to `: ka`, emits in-band `error`, and always terminates with `done`.
- **Serving errors fail safely.** Log exceptions server-side, emit exception
  type only to telemetry, and return generic client messages. Never stream raw
  exception text.
- **Provisioning is shared and ordered.** `src/provisioning.py::provision()` creates Search schemas/seeds, then FoundryIQ knowledge sources/KB, then prompt-agent versions and Search RBAC, then the optional canary. Harness scenarios invoke the model directly and deliberately skip unused prompt-agent versions. `src/bootstrap.py` is only the self-host compatibility shim and no-ops in hosted mode.
- **The hosted workspace stages source; it is not a second codebase.** Edit root sources, then let `deploy/hosted-preview/hooks/prepare.py` regenerate ignored files under `app/`.
- **The worker graph is declarative.** `src/scenarios/<scenario>/workflow.py::WORKERS` is the only attachment point. `SupervisorDAG` schedules by dependency, creates fresh `WorkerState` per invocation, retries validation, propagates optional-worker skips, and fails fast for required workers.
- **Supported manifest grounding modes are `foundry_tool` and `none`.**
  `foundry_tool` uses a FoundryIQ KB through MCP; `python_injected` remains a
  legacy runtime compatibility path and is not accepted for new manifests.
  Citation validation compares normalized full source URLs and propagates
  retrieved provenance to dependent factual workers.
- **CI is target-gated.** Self-host runs full post-deploy acceptance,
  foundry-prompt runs shared provisioning/readback checks, and hosted-preview runs a
  fresh-session protocol smoke.

## Glossary — three things called "agent"

The word "agent" is overloaded in this repo. Disambiguate before you act:

1. **Foundry agent** — a model + system-prompt + tools deployment in
   Microsoft Foundry. System instructions live in
   `docs/agent-specs/<name>.md` and are synced by `src/provisioning.py`
   (self-host startup through `src/bootstrap.py`; hosted preview through
   the postdeploy hook). Runtime invocation is centralized in the scenario
   workflow through Agent Framework's `FoundryAgent` with explicit version
   resolution.
2. **Microsoft Agent Framework worker** — a Python module under
   `src/scenarios/<scenario>/agents/<agent_name>/` with the three-layer
   shape (`prompt.py` / `transform.py` / `validate.py`). The supervisor
   DAG composes these. Created via `python scripts/scaffold-agent.py …`.
3. **Custom coding agent** — a `.agent.md` compatibility/specialist prompt in
   `.github/agents/`. These provide focused conversations
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
- **MUST** author agent system instructions in `docs/agent-specs/<foundry_name>.md`. `src/provisioning.py` syncs managed-prompt/custom-workflow specs to Foundry; `src/workflow/harness.py` loads the same spec for Harness. Reuse the approved `FoundryAgent` or Harness path; do not construct another inference client. **NEVER** hardcode system instructions inside Python code (`prompt.py` is the user-message envelope builder, not the system instruction). **NEVER** author instructions in the Foundry portal — provisioning overwrites portal drift.
- **NEVER** instantiate OpenAI clients for agent inference. The only exception is
  provisioning-time seed embedding in `src/provisioning.py`, which uses
  `AsyncAzureOpenAI` with Entra authentication and performs no agent reasoning.
- **MUST** pin SDK versions per `pyproject.toml`. See `docs/version-matrix.md`; a weekly CI job validates against latest.

### Agent architecture (3-layer pattern per agent)
Every agent lives under `src/scenarios/<scenario>/agents/<agent_name>/` with three files:
- `prompt.py`   — `build_prompt(request_data) -> str`
- `transform.py` — `transform_response(response) -> dict`
- `validate.py`  — `validate_response(response) -> (bool, str)`
Add a new agent with `/add-worker-agent` (or the low-level
`python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id>
--capability "<one-sentence capability>" [--depends-on a,b] [--optional]`).
The transactional scaffolder updates `WORKERS`, `agents/__init__.py`, the
three-layer files, the Foundry spec stub, and existing golden-case `exercises`
arrays. Paste its printed agent snippet into `accelerator.yaml ->
scenario.agents[]`. Preview/apply a new scenario with `accel scaffold`.

### Agent Framework Harness
- `harness` is an implementation pattern, not a Foundry agent type or
  orchestration pattern. It requires `hosted-agent` + `single-agent`.
- Use `src/workflow/harness.py`; domain instructions still live in
  `docs/agent-specs/<name>.md` and are loaded verbatim at runtime.
- Safe defaults disable file memory/access, background agents, looping, shell,
  built-in web search, and framework auto-approval. These capabilities require a
  separate governed design before enablement.
- Harness scaffolds currently require retrieval mode `none`. Do not bypass this
  with direct Search/HTTP calls.
- Harness tools are added deliberately. Every side effect still calls
  `hitl.checkpoint(...)`; Harness approval is not a substitute.

### HITL (Human-in-the-Loop)
- **MUST** gate every side-effect tool (writes, sends, destructive actions) through `src/accelerator_baseline/hitl.py`.
- **MUST** declare HITL policy in `accelerator.yaml -> solution.hitl` and per-tool in the tool module.
- **NEVER** let an agent execute a side-effect without an approved HITL checkpoint unless `accelerator.yaml -> solution.hitl = none` AND the action is reversible.

### Telemetry
- **MUST** emit typed events via `src/accelerator_baseline/telemetry.py`. Custom KPI events declared in `accelerator.yaml -> kpis` must appear in code.
- **MUST** wire Application Insights via `azure-monitor-opentelemetry` in both `src/main.py` and `src/agent_host.py`. Never disable.

### Grounding / RAG
- **MUST** cite retrieved sources in responses. `validate.py` must reject
  ungrounded factual claims.
- New manifests use `foundry_tool` (FoundryIQ KB over governed AI Search
  indexes) or `none`. `python_injected` through `src/retrieval/ai_search.py`
  remains legacy compatibility only.
- **NEVER** bypass governed retrieval with direct HTTP to content sources.

### Responsible AI
- **MUST** have content filters applied via IaC (`infra/`), not portal. `controls.content_filters = iac` in `accelerator.yaml`.
- **MUST** keep `evals/redteam/` XPIA + jailbreak cases green in CI before deploy.
- **MUST** flag PII handling in the solution brief; RAI risks mapped to eval cases.
- See `docs/patterns/rai/README.md` for full RAI checklist.

### UX and accessibility
- Dynamic schema forms MUST preserve JSON types, omit empty optional
  non-nullable fields, validate numeric arrays/integers, and connect help/error
  text with `aria-describedby`.
- Interactive controls need visible `:focus-visible` states and motion must
  respect `prefers-reduced-motion`.

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
- When changing docs, run `scripts/prepare-pages.py` before strict MkDocs build. When changing Bicep, build the specific root or hosted-preview entrypoint.

## Forbidden patterns (will fail lint / review)
- Constructing OpenAI clients for agent inference. The only narrow exception is
  provisioning-time seed embedding in `src/provisioning.py`, which uses
  `AsyncAzureOpenAI` with an Entra token and never performs agent reasoning.
- `requests.post(...)` to an LLM endpoint. Use the SDK.
- Hardcoded resource names/IDs. Use env + Bicep params.
- `print()` for observability. Use structured telemetry.
- Editing `src/accelerator_baseline/` to wrap Azure SDKs (it is for primitives only).
- Moving agent instructions into code. They live in `docs/agent-specs/<foundry_name>.md` (`src/provisioning.py` syncs managed agents; Harness loads the same source at runtime; portal edits are overwritten).

## When adding things
- **Continue an engagement or determine what comes next** → run `accel next`.
- **Review the current lifecycle and blockers** → run `accel status --verbose`.
- **Choose or revisit the solution architecture** → run `accel design`; require
  explicit approval or an override reason before scaffold/deploy.
- **Use the legacy custom agents** only as compatibility workflows; their
  deterministic operations should converge on the matching `accel` command.
- **New tool** → `/add-tool` custom agent → creates `src/tools/<tool>.py` with HITL scaffolding + unit test.
- **New worker agent** → only for an approved `custom-workflow`
  deterministic/supervisor
  decision; `/add-worker-agent` creates the 3-layer module and wiring.
- **Per-agent model override** → edit `accelerator.yaml` `models:` block (add a slug entry), then set `scenario.agents[].model: <slug>`. Bicep `loadYamlContent` parses the block at compile time; `infra/modules/foundry.bicep` provisions each extra deployment with the shared RAI policy (`@batchSize(1)` serialises the loop); `src/provisioning.py` resolves agent slugs to deployment names. Lint rules `models_block_shape` + `agent_model_refs_exist` enforce shape. Removing the block resets state to template defaults; raw env-var overrides are NOT supported.
- **New Azure environment** (partner dev/staging/customer sub) → `/deploy-to-env` custom agent → adds entry to `deploy/environments.yaml`, creates the GitHub Environment, wires OIDC, dispatches a deploy. Never hand-edit `deploy.yml` to add envs; the manifest + `resolve-env` job is the contract. The azd env name is **always** derived from `deploy/environments.yaml` — never set `vars.AZURE_ENV_NAME`.
- `deployment_target` is `selfhost`, `foundry-prompt`, or `hosted-preview`;
  omitted legacy values mean `selfhost`. `default_env` MUST remain selfhost.
- The `hosted-preview` target requires explicit acknowledgement, Python 3.14
  in the deployed runtime (Python 3.13+ is sufficient locally), exact pinned
  extensions, and operator RBAC values. `accel deploy` selects the nested
  workspace; direct recovery commands must change directory rather than relying
  on `azd -C`.
- **Preflight a change before commit / PR** → `/explain-change` custom agent → runs `python scripts/explain-change.py` to map the current diff to the specific lint rules, evals, and deploy-pipeline steps it will trigger. Read-only; does not replace CI gates.
- **Pick or switch landing-zone tier** → `/configure-landing-zone` custom agent → walks the partner through choosing `standalone` / `avm` / `alz-integrated` based on the customer environment and updates `accelerator.yaml` + `infra/` accordingly. Uses exemplars in `infra/avm-reference/` (Tier 2) or the overlay skeleton in `infra/alz-overlay/` (Tier 3). Lint rule `landing_zone_mode_consistent` enforces the match.
- **Switching pattern** → `/switch-to-variant` custom agent → walks through re-authoring the scenario under `src/scenarios/<new-id>/` toward a `single-agent` or `chat-with-actioning` shape (documented walkthroughs in `patterns/<variant>/README.md`; not drop-in packages).
- **Starting a new customer engagement** → `accel next`; register evidence with
  `accel intake`; use `/discover-scenario` for the interview; preview/apply the
  initial structure with `accel scaffold`.

## References
- Onboarding: `docs/start/index.md` (partner walkthrough) and `docs/getting-started/setup-and-prereqs.md` (deep reference)
- Discovery guide: `docs/discovery/SOLUTION-BRIEF-GUIDE.md`
- `docs/agent-specs/README.md` — per-agent system instructions and provisioning mechanics
- Patterns: `docs/patterns/{architecture,rai,waf-alignment}/README.md`
- Version matrix: `docs/version-matrix.md`
- Scenario catalog: `docs/references/`
