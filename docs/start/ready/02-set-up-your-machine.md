# 2. Set up your machine

*Step 2 of 10 · Get ready*

!!! info "Step at a glance"
    **🎯 Goal** — Install the toolchain you'll use on every engagement.

    **📋 Prerequisite** — [1. Get oriented](01-get-oriented.md) complete.

    **💻 Where you'll work** — Your workstation.

    **✅ Done when** — `gh --version`, `az --version`, `azd version`, `python --version` (3.11+) all succeed; Copilot Chat opens in VS Code; you can `az login` to a personal/dev subscription.

---

This step is **one-time per partner machine**. You do not re-do it per customer engagement. The production-only configuration (multi-environment GitHub secrets, OIDC, HITL approver webhooks, private networking) is out of scope here — that lands in *7. Provision the customer's Azure* once you have a real customer.

## Tools to install

| Tool | Why | Minimum |
|------|-----|---------|
| **VS Code** with **GitHub Copilot Chat** extension | Editor + Copilot is required for every custom agent (`/discover-scenario`, `/scaffold-from-brief`, etc.) | Latest |
| **Azure CLI** (`az`) | Tenant login + targeted `az` calls | `>= 2.55` |
| **Azure Developer CLI** (`azd`) | One-shot `azd up` provision + deploy | `>= 1.10` |
| **GitHub CLI** (`gh`) | Template clone + repo bootstrap | `>= 2.50` |
| **Git** | Branching + PR work | Any recent |
| **PowerShell 7** *(Windows only)* | `azd` lifecycle hooks (`postdeploy`) run with `pwsh` | `7.x` |
| **Python 3.11+** *(optional)* | Only if you want to run scripts, tests, or the FastAPI app locally — `azd up` itself does **not** require Python on your machine | `3.11`–`3.13` |
| **Docker / Podman** *(optional)* | Only for local container builds; `azd up` builds in ACR remotely by default | Any recent |

!!! warning "Microsoft Store Python alias"
    On Windows, `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe` is **not** a real interpreter. If you need Python locally, install from python.org, winget, scoop, or use an activated Conda env.

## Verify

```bash
gh --version
az --version
azd version
python --version    # only if you installed Python locally
```

Open VS Code, install the **GitHub Copilot Chat** extension, sign in. Confirm the chat sidebar opens (`Ctrl+Alt+I` or the 💬 icon) and the agents dropdown lists the repo's custom agents.

!!! note "About slash invocation"
    The agents dropdown is the **primary** way to invoke a custom agent. Slash invocation (`/scaffold-from-brief`, `/discover-scenario`, etc.) also works — but VS Code's `/` autocomplete may not list custom agents from `.github/agents/`. If you don't see them in autocomplete, type the full slug; it will still route to the right agent. This is a VS Code behavior, not a repo issue.

## Sign into a sandbox subscription

For step 3 you'll deploy to a **sandbox** — your own dev sub or an MSDN/Visual Studio benefits sub — not a customer subscription.

```bash
az login --tenant <your-sandbox-tenant-id>
azd auth login
```

Confirm Foundry **quota** in your target region (Azure portal → Foundry → Quotas). The accelerator deploys `gpt-5-mini` on `GlobalStandard` (default 30k TPM) — confirmable per region, partner per partner.

## Repo development extras *(optional, only if you'll edit code locally)*

```bash
pip install -e ".[dev]"
```

This installs `pytest`, `ruff`, `pyright`, and `mkdocs` so you can run the lint, tests, and docs build locally. CI runs all of them anyway, so this is convenience only.

---

## What you do **NOT** set up here

The items below are **per-customer**, not per-machine. They are explicitly skipped in this step and walked through during the delivery walkthrough:

- GitHub Environment-scoped secrets (`AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` / `AZURE_LOCATION`) — set in *7. Provision the customer's Azure*.
- Multi-environment manifest entries in `deploy/environments.yaml` — set via `/deploy-to-env` in *7. Provision the customer's Azure*.
- `HITL_APPROVER_ENDPOINT` webhook → set per environment in *7. Provision the customer's Azure*.
- Private networking (`enablePrivateLink=true`) → optional, picked during *7. Provision the customer's Azure* via `/configure-landing-zone`.

If you stumble on those names while reading other pages, that's where they're configured.

## Troubleshooting — top 5 (per-machine)

1. **`azd up` complains about model deployment not found** — the FastAPI startup bootstrap (`src/bootstrap.py`) verifies the deployment exists before agents are created. Confirm Foundry quota in the target region; edit `accelerator.yaml`'s `models:` block if you need a different SKU; re-run `azd up`.
2. **`az login` opens a browser but nothing happens** — most often a stale `~/.azure` cache. `az logout` then `az login --use-device-code` from the same shell.
3. **`gh repo create` fails with auth error** — `gh auth login` and pick **GitHub.com → HTTPS → Login with a web browser**. Confirm `gh auth status` shows your account.
4. **Copilot Chat sidebar doesn't show the agents dropdown** — Confirm the GitHub Copilot Chat extension is installed (not just GitHub Copilot — they're two extensions). Restart VS Code after install. Open the agents dropdown at the top of the chat panel; that's the primary entry point. Slash invocation (typing the full slug like `/scaffold-from-brief`) also works, but VS Code's `/` autocomplete may not list custom agents — type the slug in full when autocomplete doesn't surface it.
5. **`pwsh` not found on Windows** — Install PowerShell 7 from `winget install Microsoft.PowerShell`. The Windows-built-in `powershell.exe` (5.1) is not enough; `azd` lifecycle hooks call `pwsh` explicitly.

---

**Continue →** [3. Rehearse in a sandbox](03-rehearse-in-a-sandbox.md)
