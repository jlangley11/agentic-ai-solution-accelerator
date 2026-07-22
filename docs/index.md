---
hide:
  - navigation
---

# Agentic AI Solution Accelerator

> **A GitHub template that Microsoft partners clone to deliver a customer-specific agentic AI solution — live in days, not months.** The full engagement motion (discovery → UAT → handover → measure) is weeks, and walked step-by-step below.

**Flagship scenario:** Sales Research & Personalised Outreach — a supervisor
routes a request across Account Planner, ICP/Fit Analyst, Competitive Context,
and Outreach Personaliser workers, returning a grounded, citable brief plus a
CRM-ready outreach draft. **HITL gates every CRM write and email send.**

**Stack:** Microsoft Agent Framework · Microsoft Foundry · Azure AI Search · Managed Identity · Key Vault · Container Apps · Application Insights · `azd` for infra.

---

## How this site is organised

The executable front door is `accel next`. This site explains the decisions,
roles, and artifacts behind the command it returns. First-time partners can
still read the linear walkthrough in two tracks:

- **[Get ready](start/ready/01-get-oriented.md)** *(3 steps, do once)* — orient yourself, install your tools, rehearse in your own sandbox.
- **[Deliver to a customer](start/deliver/01-clone-for-the-customer.md)** *(7 steps, repeat per engagement)* — clone, discover, scaffold, provision, iterate, hand over, operate.

Roles are skim guidance, not separate paths:

| Role | Read deeply | Skim |
|---|---|---|
| **Delivery lead** | *Get oriented*, *Discover with the customer*, *UAT & handover*, *Operate (Day 2)* | The engineering steps |
| **Partner engineer** | *Set up your machine*, *Rehearse in a sandbox*, *Clone* through *Iterate & evaluate* | *Get oriented* |
| **Solo partner** | All 10 steps | — |

[:material-console: Start or continue with **`accel next`** →](lifecycle.md){ .md-button .md-button--primary }
[:material-rocket-launch: First time? **Get oriented** →](start/ready/01-get-oriented.md){ .md-button }
[:material-robot-outline: Browse custom agents →](agents-index.md){ .md-button }

```mermaid
flowchart LR
    classDef ready fill:#a5d8ff,stroke:#1864ab,stroke-width:2px,color:#000
    classDef deliver fill:#99e9f2,stroke:#0c8599,stroke-width:2px,color:#000
    subgraph READY["<b>Get ready</b> · do once"]
      direction LR
      R1["1. Get oriented"]:::ready --> R2["2. Set up your machine"]:::ready --> R3["3. Rehearse in a sandbox"]:::ready
    end
    subgraph DELIVER["<b>Deliver</b> · per customer"]
      direction LR
      D1["4. Clone"]:::deliver --> D2["5. Discover"]:::deliver --> D3["6. Scaffold"]:::deliver --> D4["7. Provision"]:::deliver --> D5["8. Iterate & evaluate"]:::deliver --> D6["9. UAT & handover"]:::deliver --> D7["10. Operate"]:::deliver
    end
    R3 --> D1
    D7 -. "next engagement" .-> D2
```

---

## Joining mid-engagement?

Jump in at the step that matches your current state.

| If this is true… | Start at |
|---|---|
| You haven't cloned the customer repo yet | [4. Clone for the customer](start/deliver/01-clone-for-the-customer.md) |
| Repo is cloned, no brief yet | [5. Discover with the customer](start/deliver/02-discover-with-the-customer.md) |
| Brief is filled in the repo, no scaffold yet | [6. Scaffold from the brief](start/deliver/03-scaffold-from-the-brief.md) |
| Code scaffolded, not provisioned in customer Azure | [7. Provision the customer's Azure](start/deliver/04-provision-the-customers-azure.md) |
| Provisioned, you're customising and running evals | [8. Iterate & evaluate](start/deliver/05-iterate-and-evaluate.md) |
| Evals green, heading into UAT | [9. UAT & handover](start/deliver/06-uat-and-handover.md) |
| Already in production | [10. Operate (Day 2)](start/deliver/07-operate-day-2.md) |

---

## Reference material

Deep dives that sit **outside** the walkthrough — open them when a step sends you there.

### Common tasks

| If you want to… | Go to |
|---|---|
| Determine the current stage and next safe action | [`accel next`](lifecycle.md) |
| Inspect blockers and all lifecycle stages | `accel status --verbose` |
| Register PRDs, PDFs, spreadsheets, or workshop files | `accel intake add …` · [Discovery flow](discovery/how-to-use.md) |
| Preview scenario creation | `accel design` → `accel scaffold --scenario-id <id> --dry-run` |
| Preview or execute a deployment | `accel deploy --dry-run` · [Provisioning](start/deliver/04-provision-the-customers-azure.md) |
| Run acceptance and produce UAT artifacts | `accel evaluate` → `accel uat report` |
| See which custom agent runs at which step | [Custom agents overview](agents-index.md) |
| Add a side-effect tool with HITL baked in | [`/add-tool`](../.github/agents/add-tool.agent.md) (used in step 8) |
| Add a specialist worker agent | [`/add-worker-agent`](../.github/agents/add-worker-agent.agent.md) (used in step 8) |
| Scaffold from approved intent | `accel design` → `accel scaffold`; then use grounding/worker specialists |
| Onboard a new Azure environment (dev/UAT/prod) | [`/deploy-to-env`](../.github/agents/deploy-to-env.agent.md) (used in step 7) |
| Pick a landing-zone tier (standalone / AVM / ALZ-integrated) | [`/configure-landing-zone`](../.github/agents/configure-landing-zone.agent.md) (used in step 7) |
| Preflight a change against lint / eval / deploy gates | [`/explain-change`](../.github/agents/explain-change.agent.md) (used in step 8) |
| Re-author the scenario as single-agent or chat-with-actioning | [`/switch-to-variant`](../.github/agents/switch-to-variant.agent.md) (used in step 8) |

### Deep dives

- **Architecture & governance** — [Reference architecture](patterns/architecture/README.md) · [Azure AI landing zone](patterns/azure-ai-landing-zone/README.md) · [WAF alignment](patterns/waf-alignment/README.md) · [Responsible AI](patterns/rai/README.md)
- **Engineering reference** — [Agent specs](agent-specs/README.md) · [Tool catalog](foundry-tool-catalog.md) · [Version matrix](version-matrix.md)
- **Frontend starter** — [`patterns/sales-research-frontend/`](patterns/sales-research-frontend/README.md)
- **Reference scenarios** — [Customer service actioning](references/customer-service-actioning/README.md) · [RFP response](references/rfp-response/README.md)
- **Delivery context** — [Partner playbook](partner-playbook.md) (narrative companion to the walkthrough) · [Solution brief guide](discovery/SOLUTION-BRIEF-GUIDE.md) · [Handover template](handover/handover-packet-template.md) · [Workflow map](partner-workflow.md)

[:material-github: GitHub repo](https://github.com/Azure-Samples/agentic-ai-solution-accelerator) · [Contributing](about/CONTRIBUTING.md) · [Support](about/SUPPORT.md)

---

## Returning for the next customer?

Track 1 (*Get ready*) stays done. Clone the next customer repository, install
the editable package, and run `accel next`; it starts from that repository's
persistent artifacts rather than your previous agent session.

Quick preflight before the next engagement:

- [ ] `gh auth status` succeeds and you can see the customer's GitHub org.
- [ ] `az account list` includes the customer's tenant; partner has rights in their target subscription.
- [ ] `accelerator-lint.py` is green on the latest commit of the template (`main`).
- [ ] You've reviewed any version-matrix updates from the weekly CI run.

---

## Glossary

Acronyms used across these docs, in one place.

| Term | Meaning |
|---|---|
| **ALZ** | Azure Landing Zone — Microsoft's reference architecture for an enterprise Azure tenancy (hub vNet, private DNS, MG hierarchy, policy). |
| **AVM** | Azure Verified Modules — Microsoft-maintained Bicep/Terraform modules following Azure best practices. |
| **BYO** | Bring Your Own — partner supplies the Azure subscription / tenant / identity, accelerator deploys into it. |
| **CCoE** | Cloud Center of Excellence — the customer team that owns Azure platform standards, ALZ, policy. |
| **HITL** | Human-in-the-Loop — required human approval gate before any side-effect tool call (CRM write, email send, etc.). |
| **MG** | Management Group — Azure's tenancy-scoped policy + RBAC container above subscriptions. |
| **OIDC** | OpenID Connect — token-based federated auth; used here so GitHub Actions can deploy to Azure without a service-principal secret. |
| **RAG** | Retrieval-Augmented Generation — pattern of grounding LLM responses in indexed sources (here, Azure AI Search). |
| **RAI** | Responsible AI — Microsoft's safety practice (content filters, redteam evals, PII handling, transparency). |
| **RBAC** | Role-Based Access Control — Azure's identity-based permission model. |
| **SSE** | Server-Sent Events — one-way streaming HTTP protocol the scenario endpoint uses to push agent progress to clients. |
| **WAF** | Well-Architected Framework — Microsoft's five-pillar architecture review (reliability, security, cost, op-ex, performance). |
