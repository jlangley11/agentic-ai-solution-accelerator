# Responsible AI — content filter, groundedness, HITL, red-team

What ships in v1 and where it lives. Customisation within these rails is fine; divergence needs a documented rationale in the partner's engagement repo.

---

## Principle 1 — Safety at the model boundary

- **Content filter locked at strict default on every deployment.** `infra/modules/foundry.bicep` sets the `accelerator-default-policy` RAI policy (Hate / Sexual / Violence / Self-harm at Medium). `scripts/accelerator-lint.py::content_filter_iac_only` blocks any portal-only relaxation.
- **Jailbreak-resistant system instructions authored in `docs/agent-specs/<foundry_name>.md`.** `src/bootstrap.py` syncs each spec verbatim to the Foundry portal at FastAPI startup on every deploy. Source code references agents by Foundry agent name (e.g. `accel-sales-research-supervisor`); instructions never appear inline in Python.
- **Prompt-injection surface scoped at retrieval.** `src/retrieval/ai_search.py` only returns fields declared in the scenario retrieval schema; the red-team suite probes data exfiltration via response shaping and tool abuse.

## Principle 2 — Grounded responses with attribution

- **Every retrieval source declared in `accelerator.yaml`** under `solution.grounding_sources` and in the scenario retrieval module (`src/scenarios/<scenario>/retrieval.py`).
- **Grounding metadata surfaced to the user** — workers emit `citations` arrays in their structured output; the quality eval runner enforces `must_cite` on cases that declare it.
- **Groundedness threshold is a CI gate.** `accelerator.yaml.acceptance.groundedness_threshold` (default 0.85) feeds `.github/workflows/evals.yml`; regressions below threshold block merge.
- **Retrieval runs under the app's managed identity.** `src/retrieval/ai_search.py` uses `DefaultAzureCredential()`, not caller identity. Partners requiring caller-identity retrieval (customer-Entra ACL pass-through) must extend the retrieval glue in their engagement repo and document the change — the accelerator does not ship this pattern in v1.

## Principle 3 — Human in the loop for side-effects

- **Every side-effect tool declares a HITL checkpoint.** Each tool module in `src/tools/` declares an `HITL_POLICY` constant at module scope and calls `hitl.checkpoint(...)` before executing the side effect. The lint rule `scripts/accelerator-lint.py::side_effect_tools_call_hitl` walks `src/tools/*.py` and blocks any module that has the side-effect shape but is missing either piece. The `accelerator.yaml.solution.hitl` value is engagement-level documentation (e.g. `none`, `pre-exec`, `post-exec`) — the lint reads it but the runtime gate is per-tool.
- **HITL pattern is partner-scope.** The flagship scenario does not ship a HITL queue UI — partners wire approval flow into their engagement app (Logic Apps, Teams card, ticketing system) and the tool blocks until approval returns.
- **Default checkpoint is pre-execution.** Reversible / telemetry-first variants require explicit partner + customer sign-off and heightened telemetry.
- **Harness does not replace HITL.** The accelerator disables Harness framework
  auto-approval by default. Any custom Harness tool that writes, sends, or
  destroys still calls `hitl.checkpoint(...)` inside the tool implementation.

## Principle 4 — Red-team evals in CI

- **Default red-team suite:** `evals/redteam/cases.jsonl` covers direct + indirect prompt injection, jailbreak attempts, tool abuse, data exfiltration via response shaping.
- **`redteam_must_pass: true`** in `accelerator.yaml.acceptance` is zero-tolerance — any failure blocks CI.
- **Runner is scenario-agnostic.** `evals/redteam/run.py` reads `accelerator.yaml`, forwards the partner-defined payload, and injects into fields declared in each case's `inject_into` list.
- **Partners extend** with domain-specific probes in `evals/redteam/cases.jsonl`.
- **Re-run triggers:** scenario change, model change, tool-catalog change, Foundry instruction change.

## Principle 5 — Data classification discipline

- **Partner declares** data classification per grounding source in `accelerator.yaml.solution.grounding_sources`.
- **Tool catalog** (`src/tools/`) should restrict destinations by classification — partners enforce this in the tool body; the accelerator ships example tools (`crm_write_contact`, `send_email`, `web_search`) as scaffolding.
- **Customer signs off on classification.** Partners must not decide unilaterally.

## Principle 6 — RAI Impact Assessment

- **Partner-scope.** Start from
  [`docs/governance/rai-impact-assessment-template.md`](../../governance/rai-impact-assessment-template.md)
  and export the reviewed engagement copy to the customer's approved governance
  location. It covers use case, stakeholders, harms, mitigations, data flows,
  classification, and residual-risk acknowledgement.
- **Expires in 180 days.** Material changes (model swap, tool add, grounding-source add) expire it sooner.
- **Accelerator surfaces the hook** via `accelerator.yaml.acceptance` — partners layer the IA check into their PR gates.

## Principle 7 — Transparency

- **Users know they're interacting with AI.** The reference workbench is a
  starter; the production customer surface must retain explicit AI disclosure.
- **Uncertainty is communicated.** Worker outputs express confidence where applicable; eval suites probe for confident-wrong.
- **Source attribution visible** on grounded responses (see Principle 2).
- **Only validated output is rendered.** Raw token `chunk` events are never
  shown or retained by the reference workbench. Final and `briefing_ready`
  payloads must pass the declared response schema; partials render only when
  the workflow explicitly advertises validated partial output.
- **Operational configuration is not advertised.** Client metadata describes
  the approved implementation shape but does not reveal whether secret-backed
  approver endpoints are configured.
- **Failures do not disclose internals.** Full exceptions stay in server logs;
  telemetry records exception type and clients receive generic error text.
- **Demo history is explicit and erasable.** Browser-local saves carry privacy
  messaging, do not display request values in navigation, and provide clear-all.

---

## Anti-patterns

| Anti-pattern | Why it's bad |
|---|---|
| "We disabled the content filter to reduce false positives" | Exits support scope and makes the system unsafe. Use allow-lists at the app layer instead. |
| "We skipped HITL for a low-risk side-effect" | "Low-risk" is a design claim until evals + production data prove it. HITL stays. |
| "Groundedness threshold = 0.5 because eval is too strict" | Lower threshold ships more hallucination. Fix the eval; do not mask the risk. |
| "Red-team evals are too flaky; we skip them in CI" | Flakiness signals real vulnerabilities. Fix the flake. |
| Agent instructions containing customer PII or secrets | Foundry portal snapshot + log trail exposes them. Instructions reference, do not embed. |

---

## Where this lives in the repo

- Content filter + model deployment: `infra/modules/foundry.bicep`
- Retrieval: `src/retrieval/ai_search.py`
- HITL lint contract: `scripts/accelerator-lint.py::side_effect_tools_call_hitl`
- Red-team suite + runner: `evals/redteam/`
- Acceptance gates: `accelerator.yaml.acceptance` + `src/accelerator_baseline/evals.py`
