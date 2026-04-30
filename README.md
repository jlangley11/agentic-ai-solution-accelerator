# Agentic AI Solution Accelerator

> **A GitHub template Microsoft partners clone to deliver a customer-specific agentic AI deployment in days.** Best read as a rendered site at <https://azure-samples.github.io/agentic-ai-solution-accelerator/>; this README is what you see inside a clone. Same markdown either way.

> Full engagement motion (discovery → UAT → handover → measure) is weeks, and documented below.

**Flagship scenario:** Sales Research & Personalized Outreach — a supervisor agent routes a research request across specialist workers (Account Researcher, ICP/Fit Analyst, Competitive Context, Outreach Personalizer) and returns a grounded, citeable sales brief with a CRM-ready outreach draft. Human-in-the-loop gates every CRM write and every email send.

**Stack:** Microsoft Agent Framework · Microsoft Foundry · Azure AI Search · Managed Identity · Key Vault · Container Apps · Application Insights · `azd` for infra.

**Adoption model:** `gh repo create --template` → Copilot-guided discovery → `azd up` → iterate in VS Code → merge through CI gates.

---

## Start here

**👉 Scan the full workflow first:** [`docs/partner-workflow.md`](docs/partner-workflow.md) — one-page visual of all 7 stages (discover → scaffold → provision → iterate → UAT → handover → measure) across the three responsibilities. Use it to orient yourself, then come back here and open your lane below.

> **Doc precedence:** when two sources conflict, the more specific one wins — custom agent > playbook / QUICKSTART > this README. Pages and this README render the same markdown, so "the doc you're reading" is never the conflict; it's always the linked custom agent or playbook that supersedes. Full chain: [Reference material](#reference-material).

### 🧭 Delivery Lead — scope, discovery, UAT, handover, value review
- **Start with:** [`docs/partner-playbook.md`](docs/partner-playbook.md) — end-to-end 7-stage motion, SOW guidance, "what good looks like" per stage
- **Then run:** `/delivery-guide` in Copilot Chat for a guided pass through the motion
- **Also use:** [`docs/discovery/how-to-use.md`](docs/discovery/how-to-use.md) (sequences the 5 discovery artifacts) · [`docs/handover/handover-packet-template.md`](docs/handover/handover-packet-template.md) (engagement-specific handover template)
- **Customer already gave you a PRD/BRD/spec?** Run `/ingest-prd` to pre-draft the brief, then `/discover-scenario` gap-fills the TBDs. Full flow inside `how-to-use.md`.
- **✅ Done when:** customer sponsor signs off at UAT (Stage 5), handover packet is delivered with a named owner and date (Stage 6), and the first monthly value review is on the calendar (Stage 7).

### 🛠️ Partner Engineer — scaffold, deploy, iterate, UAT support
- **Start with:** [`QUICKSTART.md`](QUICKSTART.md) — clone → discover → scaffold → **preflight (`/configure-landing-zone` + `/deploy-to-env`)** → `azd up` → iterate
- **Then run:** `/scaffold-from-brief` once a solution brief exists
- **Also use:** [`docs/getting-started/setup-and-prereqs.md`](docs/getting-started/setup-and-prereqs.md) (authoritative setup, prereqs, `azd up` troubleshooting) · [`docs/enablement/hands-on-lab.md`](docs/enablement/hands-on-lab.md) (7-lab sandbox rehearsal — **strongly recommended before your first customer-facing deployment**)
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

Custom agents in `.github/agents/` (they drive the executable surface) → `docs/partner-playbook.md` (delivery motion) and `docs/getting-started/setup-and-prereqs.md` (setup mechanics) → this README. The engagement-specific handover packet supersedes the generic `docs/customer-runbook.md` for the customer ops lane.

</details>

### 📐 Patterns & compliance
[Architecture](docs/patterns/architecture/README.md) · [WAF alignment](docs/patterns/waf-alignment/README.md) · [Responsible AI](docs/patterns/rai/README.md) · [Azure AI Landing Zone](docs/patterns/azure-ai-landing-zone/README.md)

### 🔀 Scenario variants (re-authoring walkthroughs)
[single-agent](patterns/single-agent/README.md) · [chat-with-actioning](patterns/chat-with-actioning/README.md) · [sales-research-frontend](patterns/sales-research-frontend/README.md) (reference UI)

### 📚 Reference scenarios (walkthroughs)
[customer-service-actioning](docs/references/customer-service-actioning/README.md) · [rfp-response](docs/references/rfp-response/README.md)

### 🔧 Engineer deep-dives
[Foundry tool catalog](docs/foundry-tool-catalog.md) · [Agent specs](docs/agent-specs/) · [SDK version matrix](docs/version-matrix.md)

### ⚙️ Under the hood

<details>
<summary>Full code + infra directory tree (click to expand)</summary>

```
agentic-ai-solution-accelerator/
├── accelerator.yaml              engagement manifest — scenario contract + acceptance + controls + KPIs
├── src/
│   ├── main.py                   scenario-agnostic FastAPI; mounts the scenario endpoint from manifest
│   ├── workflow/                 framework: BaseWorkflow Protocol + scenario registry (load_scenario)
│   ├── retrieval/                generic SearchRetriever(index_name) against Azure AI Search
│   ├── tools/                    HITL-gated side-effect tools (CRM write, email send)
│   ├── accelerator_baseline/     partner-owned primitives: telemetry, HITL, killswitch, evals, cost
│   └── scenarios/                scenario instances loaded via manifest
│       └── sales_research/       flagship: schema, workflow factory, retrieval schema
│           └── agents/           supervisor + 4 workers (three-layer: prompt, transform, validate)
├── infra/                        Bicep + azd (Foundry GA + content filter, Search, KV, ACA, App Insights)
├── evals/
│   ├── quality/                  golden cases + CI gates from accelerator.yaml.acceptance
│   └── redteam/                  XPIA + jailbreak + brief-specific RAI cases
├── patterns/
│   ├── single-agent/             variant: when orchestration isn't needed
│   ├── chat-with-actioning/      variant: conversational front-end with tools
│   └── sales-research-frontend/  reference UI starter (React + Vite + TS) for /research/stream
├── docs/
│   ├── getting-started/         orientation + setup-and-prereqs (authoritative)
│   ├── partner-playbook.md       end-to-end partner motion (7 stages)
│   ├── discovery/                discovery kit (5 artifacts + how-to-use sequencing guide)
│   ├── references/               reference scenarios (customer service, RFP response)
│   ├── agent-specs/              per-agent Foundry bootstrap specs (flagship + candidates)
│   ├── foundry-tool-catalog.md   when-to-use matrix for Foundry Agent Service tools
│   ├── customer-runbook.md       day-2 ops for the customer team
│   ├── enablement/
│   │   └── hands-on-lab.md       partner-team self-paced first-deployment walkthrough (7 labs)
│   ├── patterns/                 architecture · WAF · RAI · Azure AI Landing Zone
│   └── version-matrix.md         known-good SDK pins (weekly CI validates against latest)
├── .github/
│   ├── copilot-instructions.md   hard rules: Agent Framework, MI, HITL, evals, RAI
│   ├── agents/                   discover-scenario, scaffold-from-brief, delivery-guide, add-*, switch-to-variant (.agent.md)
│   └── workflows/                lint, evals, deploy, version-matrix (weekly pinned-latest)
├── AGENTS.md                     IDE-agnostic mirror of copilot-instructions (Cursor/Claude/Codex)
└── scripts/
    ├── accelerator-lint.py       ~30 deterministic policy checks (local + CI), AST-only
    └── scaffold-scenario.py      materialize a new scenario skeleton (CLI behind /scaffold-from-brief)
```

</details>

---

## Why this instead of starting from scratch

| Without the accelerator | With the accelerator |
|---|---|
| Partner re-invents auth, telemetry, HITL, evals, RAI posture every engagement | Ships as partner-owned source in `src/accelerator_baseline/`; used from day one |
| Discovery notes disconnected from code | Solution Brief drives scaffolding, evals, manifest, dashboards |
| "Should we use single-agent or supervisor?" → guesswork | Flagship + two variants + four reference scenarios; pick-and-scaffold |
| Compliance & WAF done at the end (if at all) | Enforced from commit 1 via `copilot-instructions.md` + CI lint + IaC content filters |
| ROI promises are slides | KPIs declared in `accelerator.yaml.kpis[]`; partners wire a telemetry event per KPI in the scenario code, then monitor in App Insights + the shipped workbook template (`infra/dashboards/roi-kpis.json`) |

---

## Reference scenarios (in `docs/references/`)

- **customer-service-actioning/** — multi-agent service assistant that looks up orders, issues refunds/credits via HITL, updates CRM. Deflection + AHT ROI.
- **rfp-response/** — multi-specialist (pricing · legal · tech · security) aggregator that drafts proposal responses. Response time days → hours; win rate lift.

Flagship itself (sales research & outreach) is fully runnable under `src/scenarios/sales_research/` — loaded at startup via the top-level `scenario:` block in `accelerator.yaml`. Add a sibling scenario with `python scripts/scaffold-scenario.py <id>`; the framework mounts it the same way the flagship is mounted.

### Documented scenario ideas (no runnable starter yet)

- **Zero Trust posture analysis** — chat-based, file-upload (CSV/Excel) assessment with multi-turn iteration. Fits a different solution shape than the flagship (conversational + artifact ingest). Tracked in `docs/agent-specs/README.md`; promote to `docs/references/zero-trust/` when a customer engagement motivates it.

---

## What this accelerator does NOT try to be

- Not a runtime platform. No services Microsoft operates for partners.
- Not a cryptographic attestation or governance gate. Consistency is enforced by CI lint + pinned SDK + starter defaults + Copilot shaping — not by Microsoft blocking partners at deploy time.
- Not a DSL. `accelerator.yaml` is ~12 fields of plain YAML. No `spec.agent.yaml`.
- Not IDE-locked. Copilot-first; AGENTS.md mirrors the rules for Cursor, Claude Code, Codex CLI.

---

## Contributing / feedback

- GitHub Issues are the intake for scenario requests, bug reports, pattern suggestions.
- Monthly triage; quarterly blessed-pattern promotions (criteria in `CONTRIBUTING.md`).
- Version matrix is maintained weekly; deprecation policy is N-1 minor.

See `SECURITY.md` for vulnerability reporting and `SUPPORT.md` for channels.
