# Security Policy

## Reporting

Report security issues to Microsoft Security Response Center (MSRC):
https://msrc.microsoft.com/create-report

Do **NOT** file public issues on this repo for security vulnerabilities.

## Scope of accepted reports

In-scope:
- Flagship scenario code (`src/scenarios/sales_research/`)
- Scenario framework (`src/main.py`, `src/workflow/`, `src/retrieval/`, `src/tools/`, `src/accelerator_baseline/`)
- Shipped Bicep modules + azd templates (`infra/`)
- Accelerator lint (`scripts/accelerator-lint.py`), scaffold CLI (`scripts/scaffold-scenario.py`), in-app FastAPI startup bootstrap (`src/bootstrap.py`)
- Schema files (`accelerator.yaml` contract) and the manifest loader (`src/workflow/registry.py`)
- Copilot instructions + custom agents (for prompt-injection-enabling issues)
- Eval runners (`evals/quality/`, `evals/redteam/`)

**Out of scope:**
- Partner-authored business logic in customer forks
- Custom scenarios scaffolded by partners (they own those forks)
- Customer's own Azure subscription policies or landing zone
- Bugs in Foundry, Entra, Azure AI Search, or other Azure services outside this repo

## Supported versions

- Current release + 2 prior minor versions receive security fixes.
- Older versions are unsupported; upgrade to receive fixes.

## Release signing

Release tags are GPG-signed by a maintainer. Verify with `git tag -v <tag>` before rebasing a partner fork onto a new release.
