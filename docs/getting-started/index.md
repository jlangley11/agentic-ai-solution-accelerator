# Getting started — orientation

> **Looking for the recommended path?** Start at the partner walkthrough — [*Get ready → 1. Get oriented*](../start/ready/01-get-oriented.md). It's the linear flow most partners follow. This page is kept as a reference index for the older role-based layout.

> **Before you start.** A 2-minute frame for what this accelerator is, what you'll ship, and which of the three Getting started docs to open next.

## What this accelerator is

A Microsoft-published **template repo** for partners delivering agentic AI
solutions to customers on **Microsoft Foundry + Microsoft Agent Framework**.
Partners fork it once per customer, approve the discovery intent, and use
target-aware `accel deploy` to land the solution in the customer's Azure
subscription.

The flagship scenario (Sales Research & Personalised Outreach) runs out of the box; you customise it from the `docs/discovery/solution-brief.md` the partner produces during discovery.

## Choose your path

Pick the row that matches what you're doing today. The Getting started nav lists every doc below; this section just tells you the **order** to read them in.

| You are… | Read in this order |
|---|---|
| **First-time partner engineer** (first customer engagement on this accelerator) | [Setup & prereqs](setup-and-prereqs.md) (one-time) → [Hands-on lab](../enablement/hands-on-lab.md) (sandbox rehearsal) → [Quickstart](../../QUICKSTART.md) (per-customer deployment) |
| **Returning engineer / customer N+1** (Setup is done, lab is done) | [Quickstart](../../QUICKSTART.md) — go straight to it |
| **Delivery lead** (you scope, run discovery, sign off UAT, run handover) | [Partner playbook](../partner-playbook.md) — full 7-stage motion |
| **Customer ops** (day-2 after handover) | The engagement-specific handover packet first; [Day-2 runbook](../customer-runbook.md) as fallback |

## How the docs fit together

```text
orientation (you are here)
    │
    ├─→ Setup & prereqs (one-time)  ──  authoritative for prereqs / secrets / troubleshooting
    │       │
    ├─→ Hands-on lab (sandbox rehearsal, before first customer)
    │       │
    ├─→ Quickstart (per-customer deployment)  ──  printable engineer reference
    │
    └─→ Partner playbook  ───────────────────  delivery lead motion (discovery → handover → measure)
```

### Precedence when docs conflict

This is the precedence rule for the whole site:

1. **`AGENTS.md`** defines non-negotiable repository engineering rules.
2. **`accel` + `accelerator.yaml`** define executable lifecycle and deployment
   state; specialist agents do not maintain parallel state.
3. **[Setup & prereqs](setup-and-prereqs.md)** wins on local setup,
   authentication, and troubleshooting.
4. **[Partner playbook](../partner-playbook.md)** wins on delivery rationale and
   role ownership; **[Quickstart](../../QUICKSTART.md)** is its concise action
   reference.
5. The engagement-specific handover packet supersedes the generic
   [customer runbook](../customer-runbook.md) for customer operations.

## What you'll have shipped at the end

- A customer-specific clone of this template, deployed to the customer's Azure subscription
- A filled `docs/discovery/solution-brief.md` recording approved intent and an
  aligned executable `accelerator.yaml`
- CI gates (lint + quality evals + redteam) running on every PR; target-aware
  deployment shipping merged changes
- An Application Insights dashboard wired to the brief's KPI events

---

**Ready?** First-time? → [**Setup & prereqs**](setup-and-prereqs.md). Returning? → [**Quickstart**](../../QUICKSTART.md).

**Need the full engagement motion first?** → [Partner playbook](../partner-playbook.md)
