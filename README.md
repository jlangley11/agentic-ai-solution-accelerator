# Agentic AI Solution Accelerator

> **A GitHub template Microsoft partners clone to deliver a customer-specific agentic AI deployment in days.** Best read as a rendered site at <https://azure-samples.github.io/agentic-ai-solution-accelerator/>; this README is what you see inside a clone. Same markdown either way.

> Full engagement motion (discovery → UAT → handover → measure) is weeks, and documented below.

**Flagship scenario:** Sales Research & Personalized Outreach — a supervisor
routes a request across Account Planner, ICP/Fit Analyst, Competitive Context,
and Outreach Personalizer workers, returning a grounded, citable brief plus a
CRM-ready outreach draft. HITL gates every CRM write and email send.

**Stack:** Microsoft Agent Framework + Harness · Microsoft Foundry · Azure AI Search · Managed Identity · Key Vault · Container Apps · Application Insights · `azd` for infra.

### Flagship reference architecture

![Sales Research and Personalized Outreach reference architecture](docs/assets/diagrams/sales-research-reference.svg)

This sample was generated—not hand-drawn—with the
[Azure Architecture Diagram Builder MCP](https://techcommunity.microsoft.com/blog/azurearchitectureblog/beyond-the-canvas-the-azure-architecture-diagram-builder-becomes-agent-ready/4534590)
v1.0.0. The companion
[MCP provenance record](docs/assets/diagrams/sales-research-reference.mcp.json)
captures the exact service graph, tool sequence, SVG checksum, and deterministic
WAF validation. It intentionally reflects the default single-region
`standalone` example; the recorded findings call out the Front Door/WAF and
multi-region upgrades expected for stricter production landing zones.

**Adoption model:** `gh repo create --template` → `accel next` → governed
discovery → Architecture Advisor decision → architecture-aware scaffold and
deployment → CI-gated iteration.

---

## Start here

**Unified path:** after cloning, install the local package once and run:

```powershell
python -m pip install -e ".[dev]"
accel next
```

After installation, `python -m accelerator_cli next` is equivalent.

This detects the engagement stage and returns the next valid action. It works
from GitHub Copilot CLI, Codex, Claude Code, or a normal terminal. See the
[unified lifecycle](docs/lifecycle.md).

**👉 Scan the full workflow first:** [`docs/partner-workflow.md`](docs/partner-workflow.md) — one-page visual of all 7 stages (discover → design + scaffold → provision → iterate → UAT → handover → measure) across the three responsibilities.

> **Authority:** executable schemas and `accel` determine lifecycle state and
> permitted actions. `AGENTS.md` defines non-negotiable engineering rules; the
> shared Agent Skill and specialist agents provide conversational guidance;
> the playbook and walkthrough explain why. See [Artifact authority](docs/reference/artifact-model.md).

### 🧭 Delivery Lead — scope, discovery, UAT, handover, value review
- **Start with:** `accel next` — it reports the current stage, missing decisions, approval boundary, and next command
- **Use for context:** [`docs/partner-playbook.md`](docs/partner-playbook.md) — end-to-end motion, SOW guidance, and "what good looks like"
- **Conversational option:** `/accelerator` or `/delivery-guide`
- **Also use:** [`docs/discovery/how-to-use.md`](docs/discovery/how-to-use.md) (sequences the 5 discovery artifacts) · [`docs/handover/handover-packet-template.md`](docs/handover/handover-packet-template.md) (engagement-specific handover template)
- **Customer already gave you source documents?** Register them together with
  `accel intake add`, review disclosure, then use `/ingest-prd` and
  `/discover-scenario` for evidence-backed drafting and gap-fill.
- **✅ Done when:** customer sponsor signs off at UAT (Stage 5), handover packet is delivered with a named owner and date (Stage 6), and the first monthly value review is on the calendar (Stage 7).

### 🛠️ Partner Engineer — scaffold, deploy, iterate, UAT support
- **Start with:** `accel next`; use [`QUICKSTART.md`](QUICKSTART.md) as the printable command reference
- **Decide:** `accel design` compares prompt versus Hosted agents,
  `managed-prompt` versus `harness` versus `custom-workflow`, orchestration
  patterns, application shells, and deployment targets; review/approve its
  evidence before scaffolding
- **Build:** approved design → `accel scaffold --scenario-id <id> --dry-run` →
  approved apply; specialists fill prompts, grounding, tools, and workers
- **Also use:** [`docs/getting-started/setup-and-prereqs.md`](docs/getting-started/setup-and-prereqs.md) (authoritative setup, prerequisites, deployment troubleshooting) · [`docs/enablement/hands-on-lab.md`](docs/enablement/hands-on-lab.md) (8-lab sandbox rehearsal — **strongly recommended before your first customer-facing deployment**)
- **✅ Done when:** acceptance evals (quality + redteam) pass in the customer's environment and the handover artifacts — repo access, runbook, approver rota, killswitch drill notes — are delivered to customer ops.

### 🏛️ Customer Ops — day-2 operations after handover
- **Primary:** Your engagement-specific handover packet (partner delivers at handover — Stage 6)
- **Fallback:** [`docs/customer-runbook.md`](docs/customer-runbook.md) — generic day-2 ops (monitoring, killswitch, evals, model swap, secret rotation, incidents). Partner packet wins on conflict.
- **✅ Done when (handover accepted):** alerts route to your on-call, HITL approver rota is current, killswitch + secret-rotation drills have been run once, and you know which partner contact handles expansion requests. *Day-2 ops is steady-state, not a finish line.*

> **Wearing multiple hats at a small partner?** The lanes above are responsibilities, not required job titles. **Solo partner:** run the Lead lane top-to-bottom through Stage 1; drop into the Engineer lane at Stage 2 (scaffold → provision → iterate); return to the Lead lane at Stage 5 (UAT) through Stage 7. Customer ops is always the customer's lane.

---

## Reference material

<details>
<summary><b>Full doc precedence when guidance disagrees</b> (click to expand)</summary>

`accel` and executable schemas → `AGENTS.md` guardrails → shared Agent Skill →
specialist custom agents → playbook/walkthrough/reference docs. The approved
engagement brief governs customer intent; `accelerator.yaml` governs executable
deployment. The engagement-specific handover packet supersedes the generic
customer runbook.

</details>

### 📐 Patterns & compliance
[Architecture](docs/patterns/architecture/README.md) · [WAF alignment](docs/patterns/waf-alignment/README.md) · [Responsible AI](docs/patterns/rai/README.md) · [Azure AI Landing Zone](docs/patterns/azure-ai-landing-zone/README.md)

### 🔀 Scenario variants (re-authoring walkthroughs)
[single-agent](patterns/single-agent/README.md) · [chat-with-actioning](patterns/chat-with-actioning/README.md) · [sales-research-frontend](patterns/sales-research-frontend/README.md) (reference UI)

### 📚 Reference scenarios (walkthroughs)
[customer-service-actioning](docs/references/customer-service-actioning/README.md) · [rfp-response](docs/references/rfp-response/README.md)

### 🔧 Engineer deep-dives
[Architecture Advisor](docs/reference/architecture-advisor.md) · [Foundry tool catalog](docs/foundry-tool-catalog.md) · [Agent specs](docs/agent-specs/) · [SDK version matrix](docs/version-matrix.md)

### ⚙️ Under the hood

<details>
<summary>Full code + infra directory tree (click to expand)</summary>

```
agentic-ai-solution-accelerator/
├── accelerator.yaml              approved architecture + scenario/deploy/eval contract
├── src/
│   ├── main.py                   scenario-agnostic FastAPI; mounts the scenario endpoint from manifest
│   ├── accelerator_cli/          lifecycle + Architecture Advisor + intake/deploy/UAT
│   ├── accelerator_mcp/          optional MCP adapter over the same command contract
│   ├── workflow/                 framework: BaseWorkflow Protocol + scenario registry (load_scenario)
│   ├── retrieval/                generic SearchRetriever(index_name) against Azure AI Search
│   ├── tools/                    HITL-gated side-effect tools (CRM write, email send)
│   ├── accelerator_baseline/     partner-owned primitives: telemetry, HITL, killswitch, evals, cost
│   └── scenarios/                scenario instances loaded via manifest
│       └── sales_research/       flagship: schema, workflow factory, retrieval schema
│           └── agents/           supervisor + 4 workers (three-layer: prompt, transform, validate)
├── infra/                        Bicep + azd (Foundry GA + content filter, Search, KV, ACA, App Insights)
├── deploy/
│   ├── foundry-prompt/           prompt-agent-only Foundry target
│   └── hosted-preview/           custom-code Hosted agent target
├── evals/
│   ├── quality/                  golden cases + CI gates from accelerator.yaml.acceptance
│   ├── redteam/                  XPIA + jailbreak + brief-specific RAI cases
│   └── foundry/                  optional native relevance + groundedness evaluators
├── patterns/
│   ├── single-agent/             variant: when orchestration isn't needed
│   ├── chat-with-actioning/      variant: conversational front-end with tools
│   └── sales-research-frontend/  tailored sales UI + schema-driven generic workbench
├── docs/
│   ├── getting-started/         orientation + setup-and-prereqs (authoritative)
│   ├── partner-playbook.md       end-to-end partner motion (7 stages)
│   ├── discovery/                discovery kit (5 artifacts + how-to-use sequencing guide)
│   ├── references/               reference scenarios (customer service, RFP response)
│   ├── agent-specs/              per-agent Foundry bootstrap specs (flagship + candidates)
│   ├── foundry-tool-catalog.md   when-to-use matrix for Foundry Agent Service tools
│   ├── customer-runbook.md       day-2 ops for the customer team
│   ├── enablement/
│   │   └── hands-on-lab.md       partner-team self-paced first-deployment walkthrough (8 labs)
│   ├── patterns/                 architecture · WAF · RAI · Azure AI Landing Zone
│   └── version-matrix.md         known-good SDK pins (weekly CI validates against latest)
├── .github/
│   ├── copilot-instructions.md   hard rules: Agent Framework, MI, HITL, evals, RAI
│   ├── agents/                   unified accelerator + specialist compatibility agents
│   └── workflows/                lint, evals, deploy, version-matrix (weekly pinned-latest)
├── .agents/skills/accelerator/   portable workflow for Copilot CLI and Codex
├── .claude/skills/accelerator/   generated Claude Code skill adapter
├── AGENTS.md                     portable engineering contract
├── CLAUDE.md                     Claude-specific import and adapter guidance
└── scripts/
    ├── accelerator-lint.py       deterministic policy checks (local + CI)
    ├── scaffold-scenario.py      scenario materializer used by `accel scaffold`
    ├── sync-agent-skill.py       keeps the Claude skill mirror exact
    └── generate-cli-docs.py      generates the CLI command reference
```

</details>

---

## Why this instead of starting from scratch

| Without the accelerator | With the accelerator |
|---|---|
| Partner re-invents auth, telemetry, HITL, evals, RAI posture every engagement | Ships as partner-owned source in `src/accelerator_baseline/`; used from day one |
| Discovery notes disconnected from code | Private evidence ledger → approved brief → executable manifest → traceable evals |
| "Should we use single-agent or supervisor?" → guesswork | Flagship + two variants + two reference scenarios; pick-and-scaffold |
| Every hosted agent rebuilds planning, history, approvals, and telemetry | Advisor selects the stable Agent Framework Harness for adaptive hosted single-agent work |
| Compliance & WAF done at the end (if at all) | Enforced from commit 1 via `copilot-instructions.md` + CI lint + IaC content filters |
| ROI promises are slides | KPIs declared in `accelerator.yaml.kpis[]`; partners wire a telemetry event per KPI in the scenario code, then monitor in App Insights + the shipped workbook template (`infra/dashboards/roi-kpis.json`) |

---

## Reference scenarios (in `docs/references/`)

- **customer-service-actioning/** — multi-agent service assistant that looks up orders, issues refunds/credits via HITL, updates CRM. Deflection + AHT ROI.
- **rfp-response/** — multi-specialist (pricing · legal · tech · security) aggregator that drafts proposal responses. Response time days → hours; win rate lift.

Flagship itself (sales research & outreach) is fully runnable under `src/scenarios/sales_research/` — loaded at startup via the top-level `scenario:` block in `accelerator.yaml`. Preview and add a sibling scenario with `accel scaffold --scenario-id <id> --dry-run`, then repeat with `--apply`.

### Documented scenario ideas (no runnable starter yet)

- **Zero Trust posture analysis** — chat-based, file-upload (CSV/Excel) assessment with multi-turn iteration. Fits a different solution shape than the flagship (conversational + artifact ingest). Tracked in `docs/agent-specs/README.md`; promote to `docs/references/zero-trust/` when a customer engagement motivates it.

---

## What this accelerator does NOT try to be

- Not a runtime platform. No services Microsoft operates for partners.
- Not a cryptographic attestation or governance gate. Consistency is enforced by CI lint + pinned SDK + starter defaults + Copilot shaping — not by Microsoft blocking partners at deploy time.
- Not a DSL. `accelerator.yaml` is ~12 fields of plain YAML. No `spec.agent.yaml`.
- Not IDE-locked. The same `accel` commands, JSON contract, and Agent Skill work
  through Copilot CLI, Codex, Claude Code, MCP, or a normal terminal.

---

## Contributing / feedback

- GitHub Issues are the intake for scenario requests, bug reports, pattern suggestions.
- Monthly triage; quarterly blessed-pattern promotions (criteria in `CONTRIBUTING.md`).
- Version matrix is maintained weekly; deprecation policy is N-1 minor.

See `SECURITY.md` for vulnerability reporting and `SUPPORT.md` for channels.
