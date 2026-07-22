# Handover packet template — `<customer>` engagement

> **Template-fill marker:** Replace every occurrence of `<customer>` (and `<YYYY-MM-DD>` in the filename) throughout this packet with the customer short-name (e.g., `contoso`) and the export date.

> **DO NOT HAND OVER** this packet to the customer while any
> `[PARTNER-FILL REQUIRED: ...]` markers remain. Search the file for
> the literal string `PARTNER-FILL REQUIRED` before exporting — every
> hit is a bug.

This packet is the engagement-specific counterpart to
[`docs/customer-runbook.md`](../customer-runbook.md). The runbook
describes what a generic deployment of this accelerator can do; this
packet describes what **this specific customer's** deployment is, how
it is wired, and who owns each piece. **When the two disagree, this
packet wins** — it is closer to the customer's reality than the
generic runbook.

Pair this packet with the archived discovery artifacts (filled
`solution-brief.md`, completed `roi-calculator.xlsx`, signed SOW) in
your delivery workspace. Do not archive them here.

---

## 1. Deployment environments

One row per environment the partner provisioned. Dev/test environments
are listed so the customer's ops team can reproduce incidents.

| Env | Target | Subscription ID | Resource group | Region | `azd` env name | Endpoint URL | Foundry project | Search service | Key Vault |
|---|---|---|---|---|---|---|---|---|---|
| prod | selfhost / foundry-prompt / hosted-preview | `[PARTNER-FILL REQUIRED: sub id]` | `[PARTNER-FILL REQUIRED: rg]` | `[PARTNER-FILL REQUIRED: region]` | `[PARTNER-FILL REQUIRED: azd env]` | `[PARTNER-FILL REQUIRED: URL or agent endpoint]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED or N/A]` |
| staging | | | | | | | | | |
| dev | | | | | | | | | |

Notes: `[PARTNER-FILL REQUIRED: any env-specific gotchas — paired
tenants, VNet peering, private endpoints, data residency]`

### Approved architecture decision

- Agent type:
- Orchestration pattern:
- Application shell:
- Deployment target:
- Advisor recommendation/confidence:
- Override reason (if any):
- Approved by/date:
- Requirements fingerprint:

Source: `accelerator.yaml -> architecture`.

---

## 2. HITL approval wiring

Describes which tool calls require human approval, who the approver
is, and how they receive / action the request.

| Tool | HITL gate trigger | Approver (role + on-call) | Channel (Teams / email / webhook) | SLA to act | Fallback if approver unavailable |
|---|---|---|---|---|---|
| `[PARTNER-FILL REQUIRED: tool name]` | `[PARTNER-FILL REQUIRED: threshold or condition]` | `[PARTNER-FILL REQUIRED: role + rota link]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED: policy — deny / queue / escalate]` |

Approver endpoint (if using a partner-hosted approval UI):
- URL: `[PARTNER-FILL REQUIRED]`
- Auth: `[PARTNER-FILL REQUIRED: Entra group / role]`
- Runbook for approvers: `[PARTNER-FILL REQUIRED: link]`

---

## 3. Alert rules & thresholds

Enumerate every App Insights alert configured for this deployment.
Anything not listed here is **not** monitored.

| Alert name | Signal (metric / KQL) | Threshold | Window | Severity | Action group | Runbook step |
|---|---|---|---|---|---|---|
| `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | Sev1 / 2 / 3 | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED: customer-runbook.md#... or this packet's Section 4 / Section 5]` |

---

## 4. Killswitch procedure

`[PARTNER-FILL REQUIRED: exact steps + who is authorised to pull it]`

Minimum contents:
- Where the killswitch toggle lives (App Config / Key Vault secret / env var / feature flag).
- Who is authorised to flip it (role + rota).
- Expected time to effect (immediate vs propagation-delayed).
- Rollback-of-rollback — how to re-enable after the incident clears.

---

## 5. Rollback path

How to restore this deployment to a known-good state if a release
breaks production.

- **Last-known-good commit:** `[PARTNER-FILL REQUIRED: git SHA + tag]`
- **Last-known-good container image digest:** `[PARTNER-FILL REQUIRED: sha256:...]`
- **Rollback-to-N retention policy:** `[PARTNER-FILL REQUIRED: how
  many prior versions are kept, where, and for how long]`
- **Rollback procedure** (step-by-step — assume the person executing
  has never seen this deployment before):
  1. `[PARTNER-FILL REQUIRED]`
  2. `[PARTNER-FILL REQUIRED]`
  3. Verify with `[PARTNER-FILL REQUIRED: smoke test command / URL]`
- **`azd env refresh` recipe** (if applicable):
  ```bash
  [PARTNER-FILL REQUIRED: exact commands]
  ```
- **Environments with rollback retention:** `[PARTNER-FILL REQUIRED:
  which envs keep N prior versions]`

---

## 6. Customer-specific deviations from shipped defaults

The accelerator ships with defaults; this engagement almost certainly
diverged. List every divergence here so the customer's ops team isn't
surprised when they `diff` against the upstream template.

- **Provisioning or tool-attachment deviations:**
  `[PARTNER-FILL: document any approved deviation from the standard deployment
  or governed catalog-tool declaration. Agent instructions must remain in
  docs/agent-specs/*.md and must not be portal-managed.]`
- **Key Vault secret references added beyond the accelerator defaults:**
  `[PARTNER-FILL REQUIRED: secret name → what it's for → who owns
  rotation]`
- **Extra telemetry events** (beyond the KPI events in
  `accelerator.yaml:kpis[]`):
  `[PARTNER-FILL REQUIRED: e.g. cost.call, eval.result, custom
  business events]`
- **Scaffolded agents or tools beyond the flagship scenario:**
  `[PARTNER-FILL REQUIRED]`
- **Infra deviations** (extra networking, private endpoints, custom
  Bicep modules, non-default SKUs):
  `[PARTNER-FILL REQUIRED]`
- **Eval deviations** (custom golden cases, lowered thresholds,
  skipped redteam categories):
  `[PARTNER-FILL REQUIRED — and why they were lowered; if thresholds
  were relaxed, include the exit plan to get back to defaults]`

---

## 7. SLA specifics

| Surface | Target | Measurement source | Credit / remedy if missed |
|---|---|---|---|
| Availability | `[PARTNER-FILL REQUIRED: e.g. 99.5%]` | `[PARTNER-FILL REQUIRED: App Insights availability test]` | `[PARTNER-FILL REQUIRED]` |
| P95 latency | `[PARTNER-FILL REQUIRED: ms]` | `[PARTNER-FILL REQUIRED: KQL on requestDuration]` | `[PARTNER-FILL REQUIRED]` |
| Groundedness | `[PARTNER-FILL REQUIRED: score]` | `[PARTNER-FILL REQUIRED: eval CI + sample-in-prod if used]` | `[PARTNER-FILL REQUIRED]` |
| HITL response time | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` |

Excluded from SLA: `[PARTNER-FILL REQUIRED: planned maintenance,
upstream provider outages, customer-caused incidents, etc.]`

---

## 8. Customer-specific contacts

| Role | Name | Contact | Escalation after |
|---|---|---|---|
| Partner delivery lead | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | — |
| Partner on-call (incident) | `[PARTNER-FILL REQUIRED: rota link]` | `[PARTNER-FILL REQUIRED]` | — |
| Customer exec sponsor | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | — |
| Customer ops owner (day-2) | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | — |
| HITL approver primary | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` |
| HITL approver backup | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | — |
| Security / compliance reviewer | `[PARTNER-FILL REQUIRED]` | `[PARTNER-FILL REQUIRED]` | — |

---

## 9. Engagement artifacts (archived references)

Not embedded here — links to the copies archived in the **delivery
workspace** (partner-internal), not the customer's repo.

- Filled `docs/discovery/solution-brief.md` at kickoff:
  `[PARTNER-FILL REQUIRED: link]`
- Completed `roi-calculator.xlsx`: `[PARTNER-FILL REQUIRED: link]`
- Signed SOW: `[PARTNER-FILL REQUIRED: link]`
- Change-control log (post-handover changes to scope / thresholds /
  agents): `[PARTNER-FILL REQUIRED: link]`
- UAT sign-off record: `[PARTNER-FILL REQUIRED: link]`

---

## How this packet is produced

1. Copy this file to the partner's delivery workspace (do **not**
   commit the filled packet to the customer's repo — it contains
   contact PII).
2. Rename to `handover-packet-<customer>-<YYYY-MM-DD>.md`.
3. Fill every `[PARTNER-FILL REQUIRED: ...]` marker. Each marker's
   hint text says what goes there.
4. Before hand-off, search for the literal string
   `PARTNER-FILL REQUIRED`. Zero hits = ready.
5. Review with the customer's incoming ops owner in a handover
   session; walk them through sections 2, 4, 5, and 6 line by line.
6. Store the final packet alongside `docs/customer-runbook.md` in the
   customer's ops location (Teams / SharePoint / their GitHub fork's
   `ops/` folder — wherever day-2 runbooks live for them).

Related:
- [`docs/customer-runbook.md`](../customer-runbook.md) — generic day-2
  operations; this packet wins on conflict.
- [`docs/partner-playbook.md`](../partner-playbook.md) Stage 6 — the
  handover motion this packet supports.


---

## Wrap-up — you've delivered

If you reached this section with every [PARTNER-FILL REQUIRED] resolved, the engagement is delivered. Recommended next steps:

- **File feedback as an issue** on the template repo — gaps you hit, lint rules that misfired, prereqs that were missing, anything that would have saved you time on day 1.
- **Share engagement learnings** with your delivery team — what scenario shape worked, where HITL gates saved the customer, what evals you added.
- **Hand the customer over to day-2 ops** using [docs/customer-runbook.md](../customer-runbook.md) as the generic baseline; this packet supersedes it for customer-specifics.
- **Start your next engagement** from [docs/partner-playbook.md](../partner-playbook.md) — Stage 1 (discovery) is the front door for the next customer.
