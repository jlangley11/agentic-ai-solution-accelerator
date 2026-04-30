# 4. Clone for the customer

*Step 4 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Spin up a per-customer copy of the template, ready for the discovery workshop.

    **📋 Prerequisite** — Track 1 (*[Get ready](../ready/01-get-oriented.md)*) complete; engagement signed; customer short-name agreed.

    **💻 Where you'll work** — VS Code (terminal + Copilot sidebar).

    **✅ Done when** — `<customer-short-name>-agents` repo exists in your partner GitHub org, opens in VS Code, Copilot Chat sidebar shows the repo's custom agents in the agents dropdown (or via `/`).

---

You'll do this **first**, before the discovery workshop, because every downstream custom agent (`/discover-scenario`, `/scaffold-from-brief`, `/configure-landing-zone`, `/deploy-to-env`) writes into the cloned repo. Cloning is cheap; doing it before the workshop means the brief lands directly in the right place.

## Where you'll work

| Where | What you do here | How to open it |
|---|---|---|
| **VS Code** | Run all repo-local commands in the integrated terminal (`` Ctrl+` ``), edit files (`accelerator.yaml`, agent specs, `solution-brief.md`), and talk to GitHub Copilot Chat in the right sidebar (💬 icon or `Ctrl+Alt+I`; pick a custom agent from the agents dropdown, or type `/` for the slash equivalents) | After cloning, `code .` from any shell |
| **GitHub web** (github.com) | Confirm the new repo exists in your partner org; later you'll wire Settings → Environments | Browser, on the cloned repo |

## Clone the template

```bash
# Replace <customer-short-name> with the customer's short name (e.g., contoso, fabrikam)
gh repo create <customer-short-name>-agents --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <customer-short-name>-agents
code .
```

VS Code opens with Copilot already configured via `.github/copilot-instructions.md`. Copilot now knows the hard rules:

- Microsoft Agent Framework + Microsoft Foundry only.
- `DefaultAzureCredential` only — no keys.
- HITL required for every side-effect tool call.
- PR evals gate merges; a post-deploy regression suite guards `main`.
- Content filters configured via IaC, not the portal.

## Confirm the clone is healthy

```bash
git status                # should be clean on main
gh repo view --web        # should open the new repo in your partner org
```

Open the agents dropdown in Copilot Chat (or type `/`) — you should see at least these custom agents: `/discover-scenario`, `/ingest-prd`, `/scaffold-from-brief`, `/configure-landing-zone`, `/deploy-to-env`, `/add-tool`, `/explain-change`, `/delivery-guide`. If they're missing, the GitHub Copilot **Chat** extension isn't installed (see [2. Set up your machine](../ready/02-set-up-your-machine.md#tools-to-install)).

## Joining mid-engagement?

If someone else on your team already cloned the customer repo, ask them for the GitHub URL, then `gh repo clone <org>/<repo>` and `code .` instead of running the template-create command.

---

**Continue →** [5. Discover with the customer](02-discover-with-the-customer.md)
