# 10. Operate (Day 2)

*Step 10 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Monthly KPI review, alert tuning, drift checks, regression evals against `main`. The accelerator runs in production; this step is what keeps it healthy.

    **📋 Prerequisite** — [9. UAT & handover](06-uat-and-handover.md) complete — customer ops has the packet; production is live.

    **💻 Where you'll work** — App Insights + GitHub Actions (scheduled evals) + the customer's PR review surface.

    **✅ Done when** — First monthly KPI review held; first alert tuned; first regression-eval run green on `main`. After that, this is a recurring loop, not a one-shot step.

---

This page is the **generic** Day-2 reference. The engagement-specific handover packet supersedes it for any customer that has one (see [9. UAT & handover](06-uat-and-handover.md)).

Start every operations session with:

```powershell
accel operate status
```

## What runs on its own

After deployment the accelerator emits and gates without partner intervention:

- **Telemetry** — every typed event declared in `src/accelerator_baseline/telemetry.py` flows into App Insights via OpenTelemetry. KPI events are dashboard-wired.
- **Content filters** — Bicep-attached `accelerator-default-policy` blocks
  Medium+ on Hate / Sexual / Violence / Self-harm. Portal drift is overwritten
  on the next infrastructure deployment.
- **Post-deploy regression evals** — the self-host path in
  `.github/workflows/deploy.yml` runs quality + red-team acceptance after
  deployment; `.github/workflows/evals.yml` provides PR-time evaluation when
  `EVALS_API_URL` is configured.
- **HITL gates** — every side-effect tool routes through `checkpoint(...)`. Failure to reach `HITL_APPROVER_ENDPOINT` is fail-closed.

## What customer ops owns

| Loop | Cadence | What |
|---|---|---|
| **KPI review** | Monthly | Pull dashboard panels declared in `accelerator.yaml -> kpis`. Compare against the brief's hypothesis numbers and the prior month. Flag drift to the partner team. |
| **Alert tuning** | As needed | Latency, error rate, eval-suite drift. Adjust thresholds based on observed baselines after the first 30 days. |
| **Regression evals** | Per release + scheduled policy | Run `accel evaluate --api-url <url> --execute`; use GitHub workflows for automated cadence. |
| **Secret rotation** | Per partner-practice schedule | `AZURE_CLIENT_ID` federated cred (Entra), `HITL_APPROVER_ENDPOINT` if the approver moves. |
| **Model swap** | When a new model is qualified | Edit `accelerator.yaml.models[]`, apply `accel deploy`, then run acceptance. |
| **Killswitch drills** | Quarterly | Practice setting `KILLSWITCH_TOOLS=on` in non-prod; confirm side-effect tools halt and the alert fires. |

## When something breaks

1. **Open App Insights.** Filter on `severityLevel >= 3` for the failing time window. The auto-deployed **ROI KPIs workbook** ([Section 2 — Dashboard](../../customer-runbook.md#dashboard)) is the fastest entry point — the "Latest failures and rejected actions" panel sorts the latest failures with a one-click `operation_Id` jump to Transaction Search.
2. **Find the trace.** Each end-to-end request emits a trace with the supervisor decision record + every worker invocation + every tool call (with HITL outcome). The from-KPI-to-trace recipe lives in [Section 2 — From KPI to trace](../../customer-runbook.md#from-kpi-to-trace).
3. **Check the lint + eval status on `main`.** If the post-deploy regression suite is red, that's where the regression entered.
4. **Roll back if needed.** Check out a tagged commit and use the declared
   target's `accel deploy` flow; document it in the packet.
5. **File a PR with the fix.** PR-gated CI (lint + quality evals + redteam) blocks merge until green.

## Looping back

When the customer asks for a new capability:

- Small additions (a new tool, a new worker, a model swap) — back to [8. Iterate & evaluate](05-iterate-and-evaluate.md).
- A new business scenario — back to [5. Discover with the customer](02-discover-with-the-customer.md) for that scenario, then through scaffold → provision → iterate → UAT → handover. Multiple scenarios coexist under `src/scenarios/<id>/`.

The detailed procedures live in the [customer runbook](../../customer-runbook.md),
the deep operations reference under Delivery context.

---

**End of walkthrough.** For the next engagement, Track 1 (*Get ready*) stays done — return directly to [4. Clone for the customer](01-clone-for-the-customer.md) and run Track 2 with the new customer's short-name.
