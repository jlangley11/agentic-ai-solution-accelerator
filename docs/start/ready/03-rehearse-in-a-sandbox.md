# 3. Rehearse in a sandbox

*Step 3 of 10 · Get ready*

!!! info "Step at a glance"
    **🎯 Goal** — Clone the template into your own dev subscription, run the full deploy + eval loop end-to-end, feel one HITL approval — before you face a customer.

    **📋 Prerequisite** — [2. Set up your machine](02-set-up-your-machine.md) complete.

    **💻 Where you'll work** — VS Code + Azure portal (your sandbox subscription) + Foundry portal (`ai.azure.com`).

    **✅ Done when** — You ran the reference frontend at `http://localhost:5173`, clicked **Run research**, and saw a streamed briefing render with citations from the deployed `/research/stream` API; you read the matching App Insights trace; quality + redteam evals pass; you approved one HITL prompt.

??? success "What success looks like"
    Three signals, in the order you'll hit them:

    **1. Backend smoke test (Lab 1).** Proves the Container App booted and bootstrap completed. Not a workflow validation.

    ```bash
    curl <api-url>/healthz
    # {"status": "ok", "bootstrap": "complete"}
    ```

    **2. Primary success signal — the browser path (Lab 2).** A partner engineer's first proof the accelerator works:

    1. Reference frontend running at `http://localhost:5173` (from `patterns/sales-research-frontend/`).
    2. Click **Run research** with the pre-filled form.
    3. Streamed `status` → `partial` → `final` events render in the viewer; the result panel shows a usable briefing with citations.

    **3. Eval gate (Lab 4).** `python evals/quality/run.py --api-url <api-url>` ends with something like:

    ```
    quality: 18/20 passed (0.90) ≥ threshold 0.85  ✅
    groundedness: 19/20 passed (0.95) ≥ threshold 0.90  ✅
    ```

    `python scripts/enforce-acceptance.py` finishes with:

    ```
    ✅ All acceptance thresholds met for env=sandbox
    ```

---

This step is the **sandbox rehearsal** — done once per partner engineer, before your first customer-facing engagement. Returning engineers skip straight to *4. Clone for the customer* on subsequent engagements.

It is **not** customer training. It is partner-engineer training, with check-your-work gates so you catch misunderstandings in your own sub instead of in front of a customer.

## Lab objectives

After finishing the sandbox rehearsal you can:

1. Deploy the flagship scenario to your own sandbox subscription with `azd up` and confirm it works end-to-end.
2. Open the reference front-end locally and drive the workflow from a browser.
3. Read App Insights telemetry emitted by real browser traffic, and know which dashboard panels require partner-wired emitters to light up.
4. Run the quality and redteam evals against your deployment and read `scripts/enforce-acceptance.py` output.
5. Edit an agent's instructions the supported way (spec file + `azd provision`), not by portal drift.
6. Swap the model via `accelerator.yaml → models[]`.
7. Scaffold a new side-effect tool via `/add-tool` with HITL baked in, and know why the redteam case is not optional.
8. Scaffold a new scenario with `/scaffold-from-brief` and know what it actually does vs what you still author by hand.

## Where you'll work in the sandbox

| Where | What you do there |
|---|---|
| **VS Code** | Run repo-local commands in the integrated terminal (`` Ctrl+` ``); edit files; talk to GitHub Copilot Chat in the right sidebar (custom agents via the agents dropdown or `/` slash equivalents) |
| **GitHub web** | Watch Actions runs (optional in the lab; required in real engagements) |
| **Azure portal** | Resource group, App Insights logs and dashboards, Foundry quota |
| **Foundry portal** (ai.azure.com) | Visually confirm agents (Lab 5 demonstrates that portal edits get overwritten by spec files on next `azd provision`) |

## Sandbox smoke-test (start here)

```bash
# 1. Clone the template into a sandbox repo (NOT a customer repo — that's step 4)
gh repo create <your-handle>-accel-sandbox --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <your-handle>-accel-sandbox
code .

# 2. Authenticate to your SANDBOX subscription
az login --tenant <your-sandbox-tenant-id>
azd auth login

# 3. Provision + deploy
azd env new sandbox-dev
azd up
```

`azd up` returns the API URL. Hit `/healthz` to confirm the Container App booted and bootstrap completed — that's the backend smoke test, not a workflow validation. **Lab 2 is where you exercise `/research/stream` end-to-end through the reference frontend** and see the accelerator actually work.

Cleanup when done: `azd down --purge`.

## The labs (sequential)

The 8 labs walk the same surface with check-yourself prompts so you can self-check each result before moving on. Each one-line goal below is enough for the most common path; click **Full lab** if you want the verbose walkthrough.

| # | One-line goal | Check yourself | Full lab |
|---|---|---|---|
| 1 | Deploy the flagship backend to your sandbox with `azd up`. | **Backend smoke test only:** `curl <api>/healthz` returns `{"status":"ok"}` and the resource group has AIServices + Container App + AI Search + App Insights. This proves the container booted; Lab 2 is the first user-facing validation. | [Lab 1](../../enablement/hands-on-lab.md#lab-1--first-deploy) |
| 2 | Run the reference frontend locally and stream a research request from the browser. | **Primary success signal:** `http://localhost:5173` renders a streamed briefing with citations after you click **Run research**. This is the traffic Lab 3 inspects in App Insights. | [Lab 2](../../enablement/hands-on-lab.md#lab-2--see-it-work-in-a-browser) |
| 3 | Read the App Insights trace for the Lab 2 call — find the supervisor decision and worker spans. | App Insights shows a single end-to-end trace; you can name (a) which workers ran, (b) which tools fired, (c) where HITL would have been called if it were a write. | [Lab 3](../../enablement/hands-on-lab.md#lab-3--read-the-telemetry) |
| 4 | Run quality + redteam evals against your sandbox; capture the baseline. | `python scripts/enforce-acceptance.py` reports green; you saved the output as your sandbox baseline. | [Lab 4](../../enablement/hands-on-lab.md#lab-4--run-evals--acceptance-baseline) |
| 5 | Edit an agent spec in `docs/agent-specs/`, run `azd provision`, watch the change land in Foundry. | Foundry portal shows the new instructions; portal-only edits get reverted on next provision. | [Lab 5](../../enablement/hands-on-lab.md#lab-5--edit-an-agents-instructions-the-supported-way) |
| 6 | Swap the model via `accelerator.yaml -> models[]` and re-deploy. | The chosen agent now runs on the new model; lint passes; eval scores haven't regressed. | [Lab 6](../../enablement/hands-on-lab.md#lab-6--swap-the-model) |
| 7 | Use `/add-tool` to scaffold a side-effect tool — then read the auto-generated HITL + redteam case. | Tool calls fail-closed without HITL approval; redteam case fails the suite if you remove the HITL guard. | [Lab 7](../../enablement/hands-on-lab.md#lab-7--add-a-side-effect-tool-with-add-tool) |
| 8 | Use `/scaffold-from-brief` to scaffold a *new* scenario sibling to `sales_research`. | New `src/scenarios/<id>/` exists, lint passes, supervisor + workers wired in `WORKERS`. | [Lab 8](../../enablement/hands-on-lab.md#lab-8--scaffold-a-new-scenario) |

→ Or open the [full lab guide](../../enablement/hands-on-lab.md) for all 8 labs in one page.

## What's intentionally **out of scope** in the sandbox

These all become real in step 7 once you have a customer:

- GitHub Environment-scoped OIDC secrets — sandbox `azd up` runs locally with `azd auth login` only.
- Multi-environment `deploy/environments.yaml` — single `sandbox-dev` env is fine here.
- Private endpoints, AVM, or ALZ overlay — Tier 1 standalone for the sandbox.
- Production HITL approver webhook — `HITL_DEV_MODE=1` auto-approves in the sandbox.

---

**Continue →** when you have a real engagement, go to [4. Clone for the customer](../deliver/01-clone-for-the-customer.md). Otherwise stop here — Track 1 (*Get ready*) is complete.
