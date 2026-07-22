# 9. UAT & handover

*Step 9 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Run customer UAT to acceptance, deliver the handover packet to customer ops.

    **📋 Prerequisite** — [8. Iterate & evaluate](05-iterate-and-evaluate.md) complete — quality + redteam evals green; KPI events emitting; dashboards populated.

    **💻 Where you'll work** — Customer environment (UAT pass) + handover meeting (live or recorded) + your delivery workspace (where the filled handover packet lands).

    **✅ Done when** — Acceptance criteria signed by customer sponsor; handover packet (alerts, dashboards, runbook, eval gates, rollback plan) delivered; customer ops named.

---

## UAT — what "acceptance" means here

Acceptance is **objective + signed**, not "the demo went well."

- **Objective:** every threshold in `accelerator.yaml -> acceptance` is green on the customer environment, against the customer's golden cases (`evals/quality/golden_cases.jsonl`) and the customer-specific redteam cases (`evals/redteam/`).
- **Signed:** `accel uat report` renders the accepted result and
  `accel uat signoff --sponsor <name> --approver <name> --apply` records the
  reviewed decision locally.

If a threshold misses, **don't ship**.

!!! danger "Acceptance is a gate, not a target"
    Loop back to [8. Iterate & evaluate](05-iterate-and-evaluate.md) and fix in PRs against the customer environment, with the regression suite guarding the merge. Shipping below the agreed threshold compromises the engagement's measurable ROI claim.

## Handover packet

Generate the environment-aware draft, then use the template prompts to fill
customer-owned values:

```powershell
accel handover generate --env <environment-name> --dry-run
accel handover generate --env <environment-name> --apply
```

Minimum contents:

- **Endpoint inventory** — API URL, frontend URL (if any), Foundry project name, resource group name.
- **Architecture decision** — prompt/Hosted type, orchestration, application
  shell, target, rationale, approver, override, and requirements fingerprint.
- **Approvers** — who is on-call for HITL approvals; backup; escalation.
- **Dashboards** — App Insights workbook URL, KPI panels, latency panels, error panels.
- **Alerts** — what fires, to whom, on what threshold; how to acknowledge.
- **SLAs** — uptime, response time, eval thresholds; what "broken" means and who decides.
- **Eval gates** — `accelerator.yaml -> acceptance` thresholds; how to re-run; how to interpret.
- **Rollback** — how to redeploy a tagged commit through the declared target;
  how to flip the tool killswitch (`KILLSWITCH_TOOLS=on`).
- **Secret rotation** — schedule and procedure for `AZURE_CLIENT_ID` federated cred rotation, `HITL_APPROVER_ENDPOINT` rotation if the approver moves.
- **Model swap** — how to update `accelerator.yaml.models[]`, apply
  `accel deploy`, and re-run acceptance.

After the live review, record customer-ops acceptance:

```powershell
accel handover approve --approver <customer-ops-owner> --apply
```

Until approval, Day 2 remains blocked. The approved engagement packet
supersedes the generic operate page.

## Handover meeting

Walk the customer ops team through the packet **live**:

- Open the App Insights dashboard. Drive a single end-to-end request. Show the trace.
- Approve a HITL prompt together — show what the approver sees and what gets logged.
- Run `accel evaluate --api-url <customer-api-url> --execute` and walk the
  acceptance/UAT artifact.
- Hand them the killswitch demonstration (do not actually flip it in prod — show it in a non-prod env).
- Confirm they have access to: the customer GitHub repo (read at minimum), the App Insights workspace, the resource group, the Foundry project.

Record the meeting; archive with the packet in your delivery workspace.

## Archive

In your delivery workspace (not this template repo):

- The filled `solution-brief.md` and `roi-calculator.xlsx`.
- The signed acceptance report.
- The filled handover packet.
- The handover meeting recording.
- A pointer to the customer GitHub repo + customer Azure environments.

---

**Continue →** [10. Operate (Day 2)](07-operate-day-2.md)
