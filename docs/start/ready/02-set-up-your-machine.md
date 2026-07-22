# 2. Set up your machine

*Step 2 of 10 · Get ready*

!!! info "Step at a glance"
    **🎯 Goal** — Install the toolchain you'll use on every engagement.

    **📋 Prerequisite** — [1. Get oriented](01-get-oriented.md) complete.

    **💻 Where you'll work** — Your workstation.

    **✅ Done when** — core CLIs succeed, `pip install -e ".[dev]"` completes,
    `accel --help` works, and `accel next` reports repository state.

---

This step is **one-time per partner machine**. You do not re-do it per customer engagement. The production-only configuration (multi-environment GitHub secrets, OIDC, HITL approver webhooks, private networking) is out of scope here — that lands in *7. Provision the customer's Azure* once you have a real customer.

## Tools to install

| Tool | Why | Minimum |
|------|-----|---------|
| **Coding-agent client** | Copilot CLI/VS Code, Codex, or Claude Code for conversational authoring | Current supported release |
| **VS Code** *(optional)* | Editor and GitHub custom-agent dropdown | Latest |
| **Azure CLI** (`az`) | Tenant login + targeted `az` calls | `>= 2.55` |
| **Azure Developer CLI** (`azd`) | Underlying Azure provision/deploy engine selected by `accel deploy` | `>= 1.10` |
| **GitHub CLI** (`gh`) | Template clone + repo bootstrap | `>= 2.50` |
| **Git** | Branching + PR work | Any recent |
| **PowerShell 7** *(Windows only)* | `azd` lifecycle hooks (`postdeploy`) run with `pwsh` | `7.x` |
| **Python 3.11+** | Preferred `accel` lifecycle, scripts, tests, and local app | `3.11`–`3.13` |
| **Docker / Podman** *(optional)* | Only for local container builds; self-host deploys build in ACR remotely by default | Any recent |

!!! warning "Microsoft Store Python alias"
    On Windows, `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe` is **not** a real interpreter. If you need Python locally, install from python.org, winget, scoop, or use an activated Conda env.

## Verify

```bash
gh --version
az --version
azd version
python --version
python -m pip install -e ".[dev]"
accel --help
accel next
```

Open your chosen coding agent. Copilot and Codex discover
`.agents/skills/accelerator`; Claude uses the synchronized `.claude/skills`
copy. In VS Code, confirm `/accelerator` appears in the agents dropdown.

!!! note "About slash invocation"
    `accel next` is the primary lifecycle entry. The VS Code agents dropdown
    and slash commands invoke conversational specialists; they do not replace
    persistent CLI state.

## Sign into a sandbox subscription

For step 3 you'll deploy to a **sandbox** — your own dev sub or an MSDN/Visual Studio benefits sub — not a customer subscription.

```bash
az login --tenant <your-sandbox-tenant-id>
azd auth login
```

Confirm Foundry **quota** in your target region (Azure portal → Foundry → Quotas). The accelerator deploys `gpt-5-mini` on `GlobalStandard` (default 30k TPM) — confirmable per region, partner per partner.

## Install repository tooling

```bash
pip install -e ".[dev]"
```

This installs the CLI entry point plus pytest, Ruff, Pyright, hosted-preview
type dependencies, and build tooling. Documentation dependencies remain in
`requirements-docs.txt`.

---

## What you do **NOT** set up here

The items below are **per-customer**, not per-machine. They are explicitly skipped in this step and walked through during the delivery walkthrough:

- GitHub Environment-scoped secrets (`AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` / `AZURE_LOCATION`) — set in *7. Provision the customer's Azure*.
- Multi-environment manifest entries in `deploy/environments.yaml` — set via `/deploy-to-env` in *7. Provision the customer's Azure*.
- `HITL_APPROVER_ENDPOINT` webhook → set per environment in *7. Provision the customer's Azure*.
- Private networking (`enablePrivateLink=true`) → optional, picked during *7. Provision the customer's Azure* via `/configure-landing-zone`.

If you stumble on those names while reading other pages, that's where they're configured.

## Troubleshooting — top 5 (per-machine)

1. **Deployment reports a missing model** — confirm Foundry quota in the target
   region, edit `accelerator.yaml.models[]` if needed, then re-run the approved
   `accel deploy` flow.
2. **`az login` opens a browser but nothing happens** — most often a stale `~/.azure` cache. `az logout` then `az login --use-device-code` from the same shell.
3. **`gh repo create` fails with auth error** — `gh auth login` and pick **GitHub.com → HTTPS → Login with a web browser**. Confirm `gh auth status` shows your account.
4. **The custom agent isn't visible** — first confirm `accel next` works. For
   VS Code, trust the workspace and reload. For skill changes, run
   `python scripts/sync-agent-skill.py`.
5. **`pwsh` not found on Windows** — Install PowerShell 7 from `winget install Microsoft.PowerShell`. The Windows-built-in `powershell.exe` (5.1) is not enough; `azd` lifecycle hooks call `pwsh` explicitly.

---

**Continue →** [3. Rehearse in a sandbox](03-rehearse-in-a-sandbox.md)
