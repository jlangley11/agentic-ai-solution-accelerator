# Support

> **TL;DR:** the Azure Agentic AI Solution Accelerator is **community-supported, best-effort**. Partners own the customer deployment end-to-end. Microsoft does not operate the pager for customer solutions built on this accelerator.

---

## What support looks like

### 1. Repo-level (what Microsoft provides)

- **GitHub issues** on this repo — bug reports, pattern questions, content gaps, scenario requests.
- **Releases + release notes** for the accelerator template (flagship code, scenario framework, Bicep modules, accelerator-lint, custom agents).
- **Security vulnerabilities** — report privately per [SECURITY.md](SECURITY.md).
- **Office hours** (if your partner org is onboarded) — periodic sync with the accelerator engineering team.

**What Microsoft does NOT provide via this repo:**
- Production support for customer deployments.
- 24×7 incident response.
- Legal / contractual support commitments.
- Customer-specific architecture review.

### 2. Engagement-level (what the partner provides)

Partners own:
- Sev-1 response + customer comms.
- Runbook execution.
- Waiver tracking within the customer engagement.
- Baseline upgrades on customer schedules.
- Cost + RAI posture monitoring.

This accelerator gives partners the *tools + patterns* to do those jobs well. It does not replace them.

### 3. Microsoft field (when applicable)

Depending on your partner's commercial relationship with Microsoft, a field Solutions Architect may be engaged per-customer for co-delivery on lighthouse or strategic engagements. That is outside the scope of this repo; coordinate through your Microsoft partner manager.

---

## How to file a useful issue

Include:

1. **What layer is the issue on?**
   - Content (pattern doc / guidance)
   - Tooling (validator, `baseline` CLI, azd template)
   - Example (reference scenario, example Spec)
2. **What version?** — release tag, or commit SHA.
3. **Minimal repro** — Spec excerpt, CI log tail, validator output.
4. **What you expected vs. what happened.**
5. **Severity from your perspective** — blocking a production deploy / blocking dev / nice-to-have.

Good issues, with clear reproduction steps, get triaged faster. Vague or off-topic issues may be closed without action.

---

## What's actually shipped today

- Flagship scenario (Sales Research & Outreach) is fully runnable under `src/scenarios/sales_research/`; loaded dynamically from `accelerator.yaml -> scenario:` at startup.
- Scenario framework: `src/workflow/registry.py` + `src/workflow/base.py`. `scripts/scaffold-scenario.py` materializes new scenarios.
- Infra: `infra/` deploys Foundry (GA API) + default content filter + model deployment + Search + KV + ACA + App Insights via `azd up`.
- Evals: `evals/quality/` + `evals/redteam/` run against the deployed endpoint; thresholds in `accelerator.yaml -> acceptance`.
- Lint: `scripts/accelerator-lint.py` — ~30 deterministic AST-only checks; CI-gated.
- Reference scenarios: Customer Service Actioning and RFP Response ship as walkthrough READMEs under `docs/references/` (runnable code lands when a customer engagement motivates it).

See [docs/getting-started/setup-and-prereqs.md](docs/getting-started/setup-and-prereqs.md) for the exact onboarding path.

---

## Security

Security vulnerabilities go to MSRC via [SECURITY.md](SECURITY.md), not GitHub issues.

---

## Escalation paths

| Situation | Where to go |
|---|---|
| Pattern bug or content error | GitHub issue on this repo |
| Accelerator lint false positive / false negative | GitHub issue with repro |
| Customer production incident | Partner's own on-call; accelerator engineering is not on the pager |
| Security vulnerability in the accelerator | MSRC per SECURITY.md |
| Need a new reference scenario or pattern variant | GitHub issue + discussion |
| Disagree with a pattern recommendation | PR with rationale; accelerator engineering reviews |
