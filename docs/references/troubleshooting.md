# Troubleshooting cookbook

A symptom-keyed index of the failure modes the accelerator and its
deployment hit in practice. Each entry is **1 line of symptom + 1
line of cause + a link to the canonical fix**. We don't restate
fixes here so the cookbook stays in sync with the actual runbook /
provision step it points at.

If your symptom isn't listed: open an issue, then add an entry once
you've found the fix. Stale entries are worse than no entries.

## Quick navigation

* [Local environment](#local-environment)
* [Deploy time (`azd up`)](#deploy-time-azd-up)
* [First-boot (post-`azd up`)](#first-boot-post-azd-up)
* [Runtime](#runtime)
* [Evals & CI](#evals--ci)
* [Decommission](#decommission)
* [Tier 3 ALZ-integrated](#tier-3-alz-integrated)

---

## Local environment

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python scripts/accelerator-lint.py` aborts with `ModuleNotFoundError: No module named 'src'` | `pip install -e ".[dev]"` not run, or wrong venv active. | [Set up your machine → install](../start/ready/02-set-up-your-machine.md) |
| Deployment fails before provisioning starts | Azure login, manifest target, region, or preflight is invalid. | Run `accel deploy --env <env> --region <region> --dry-run`, then `--execute` for the real preflight. |
| Slash-command autocomplete doesn't suggest `/teardown` or `/configure-landing-zone` | New custom-agent files require a Copilot Chat reload. | Reload Copilot Chat (`Developer: Reload Window`) and retry. |
| `accel intake review --include-text` is blocked | The source remains `local_only` or was rejected. | Review metadata, then explicitly run `accel intake disclose <source-id> approved_for_model --apply`. |
| CLI reports that the Claude skill is stale | Canonical `.agents/skills/accelerator` changed without regenerating the Claude adapter. | Run `python scripts/sync-agent-skill.py`. |

## Deploy time (`azd up`)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `azd up` fails inside `Microsoft.CognitiveServices/accounts/deployments` with `InsufficientQuota` or `429` | Default model TPM exceeds region quota. | [Provision step → Model quota / 429](../start/deliver/04-provision-the-customers-azure.md#troubleshooting-deployment-and-first-boot) |
| `azd up` fails on `Microsoft.CognitiveServices/accounts/projects` | AIServices account not yet fully provisioned, or region not enrolled for Microsoft Foundry projects. | [Provision step → Foundry project](../start/deliver/04-provision-the-customers-azure.md#troubleshooting-deployment-and-first-boot) |
| `azd up` fails 8 minutes in on a missing resource provider | RP not registered on the subscription. | Run `python scripts/preflight-deploy.py --region <region>` before `azd up`; the script prints the `az provider register` command. |
| Bicep compile fails with `BCP120` on an `existing` resource | A resource name was constructed at deploy time and isn't compile-time-determinable. | Use a `param`-driven name for `existing` resources; see `infra/main.bicep` lines 268–281 for the pattern. |

## First-boot (post-`azd up`)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `/healthz` returns 503 with `Forbidden` from Cognitive Services or AI Search during `lifespan.startup` | MI role assignments take 1–3 minutes to propagate after `azd up`. | [Provision step → RBAC propagation](../start/deliver/04-provision-the-customers-azure.md#troubleshooting-deployment-and-first-boot) |
| `/healthz` returns 200 but agent calls fail `ResourceNotFound` for the search index | Bootstrap ran before AI Search RBAC propagated; seed step skipped. | [Provision step → Index not seeded](../start/deliver/04-provision-the-customers-azure.md#troubleshooting-deployment-and-first-boot) |
| Side-effect tools fail-closed; logs show `hitl.checkpoint -> approver_unreachable` | `HITL_APPROVER_ENDPOINT` not set on the Container App. | [Provision step → HITL approver unreachable](../start/deliver/04-provision-the-customers-azure.md#troubleshooting-deployment-and-first-boot) |
| `/healthz` returns 503 with `KeyError: AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` (or similar required env var) | The Container App was deployed before `azd env set` finished propagating, OR a Bicep refactor removed the env binding. | Re-run `azd deploy` after `azd env set` completes. Confirm the env mapping is still present in `infra/modules/container-app.bicep`. |

## Runtime

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bad output or unsafe tool behavior in production | Prompt regression, code regression, or model drift. | [Customer runbook → P1 incident playbook](../customer-runbook.md#9-incident-playbook) |
| Sudden burst of `response.returned` errors with `Foundry`-flavored messages | Model outage in the region. | [Customer runbook → P1 model outage](../customer-runbook.md#9-incident-playbook) |
| Cost alerts firing without a usage spike | Likely model swap without `MODEL_PRICE_USD_PER_1K_TOKENS` refresh, prompt regression, or retrieval-frequency shift. | [Customer runbook → P2 cost regression](../customer-runbook.md#9-incident-playbook) |
| Workbook auto-deploy fails with `WorkbookAlreadyExists` after a portal-paste install | A pre-existing workbook with the same `name` GUID was created from the legacy paste-install. | Delete the manually-created workbook in the portal (Application Insights → Workbooks → ROI KPIs); re-run the approved `accel deploy` flow. |
| Generic workbench form loads but validated progress stays blank | The workflow emits `partial` without declaring `validated_partials = True`, or emits raw chunks only. | Declare validated partial capability only after worker validation; final response still renders from the declared response schema. |
| Workbench reports an SSE sequence error | Proxy/server duplicated, skipped, or reordered sequence numbers. | Inspect the response stream and ingress/proxy behavior; do not treat the run as complete. |

## Evals & CI

| Symptom | Cause | Fix |
|---------|-------|-----|
| Optional Foundry evaluation fails before scoring | `.[evals]` is missing, evaluator endpoint/model variables are absent, or quality results lack opt-in evaluator inputs. | Install `.[evals]` and run `accel evaluate --api-url <url> --foundry --execute`. |
| `evals/redteam/` fails with `must_not_contain` on a new case | Worker echoed back the literal injection token. | Tighten worker `validate.py` to reject responses that contain known adversarial substrings; add a unit test. |
| `eval-baseline.py --check` fails with "smoke run had fewer cases than baseline" | Smoke (`--smoke` / `--limit`) was used; baseline was snapshotted from a full run. | Run the full suite (no `--smoke`) before `--check`, or re-snapshot the baseline. |
| Acceptance gate fails with thresholds the partner thought were green | Thresholds in `accelerator.yaml -> acceptance` are stricter than the eval runner's defaults. | Compare against the markdown step summary in CI (auto-rendered); tune thresholds OR fix the regression. |
| Hosted Responses invocation returns request validation failure | Free text was sent to a schema with multiple required fields. | Send the complete request as JSON input text or use Invocations with `--input-file`. |

## Decommission

| Symptom | Cause | Fix |
|---------|-------|-----|
| Fresh `azd up` in the same region fails with `Cognitive Services account name already exists` | Account is in soft-delete from a prior `azd down --purge`. | Run `python scripts/teardown-preflight.py --env <env-name> --post-teardown` to surface the purge command. |
| Same as above but for Key Vault | KV soft-delete period (7–90 days) hasn't elapsed and purge protection is on. | Same script; or wait for retention to elapse. Purge protection cannot be bypassed. |

## Tier 3 ALZ-integrated

| Symptom | Cause | Fix |
|---------|-------|-----|
| `azd up` fails in the workload deploy with `PrivateEndpointSubnetNotValid` | `peSubnetId` envvar not set, or points at the spoke instead of the PE subnet. | Run `python scripts/validate-alz.py`; re-run the overlay step from `infra/alz-overlay/README.md` in the repo. |
| Sudden burst of `response.returned` transport errors after a stable deploy | Hub team removed or re-keyed a private DNS zone link. | [Customer runbook → DNS / private-endpoint failure](../customer-runbook.md#9-incident-playbook) |
| Validator passes but `azd up` still fails on `RoleAssignmentMissing` for DNS | Deploying principal lacks `Private DNS Zone Contributor` on hub zones. | Have CCoE grant the role on each zone in `privateDnsZoneIds`. |

---

## Scope of this cookbook

* Includes: failure modes that have been hit by partners on a real
  customer engagement.
* Excludes: trivial typos, single-version SDK quirks, and IDE issues.
  Use the issue tracker for those.

The cookbook is updated whenever a new failure mode is added to
`04-provision-the-customers-azure.md`, `customer-runbook.md`, or any
of the `validate-*.py` scripts.
