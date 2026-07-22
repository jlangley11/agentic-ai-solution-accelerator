# 4. Clone for the customer

*Step 4 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Spin up a per-customer copy of the template, ready for the discovery workshop.

    **📋 Prerequisite** — Track 1 (*[Get ready](../ready/01-get-oriented.md)*) complete; engagement signed; customer short-name agreed.

    **💻 Where you'll work** — Terminal, editor, and your preferred coding-agent client.

    **✅ Done when** — `<customer-short-name>-agents` exists in your partner GitHub org and `accel next` returns structured engagement state.

---

You'll do this **first**, before the discovery workshop, because lifecycle
artifacts and customer-specific code belong in the cloned repo. Cloning is
cheap; doing it before the workshop means evidence decisions, the brief, and
the executable manifest land in the right place.

## Where you'll work

| Where | What you do here | How to open it |
|---|---|---|
| **Terminal / editor** | Run `accel`, edit `accelerator.yaml`, agent specs, and the brief, and review diffs | `code .`, `copilot`, `codex`, or `claude` |
| **GitHub web** (github.com) | Confirm the new repo exists in your partner org; later you'll wire Settings → Environments | Browser, on the cloned repo |

## Clone the template

```bash
# Replace <customer-short-name> with the customer's short name (e.g., contoso, fabrikam)
gh repo create <customer-short-name>-agents --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <customer-short-name>-agents
code .
```

All supported agents read the portable rules in `AGENTS.md`; Copilot also reads
`.github/copilot-instructions.md`, and Claude reads `CLAUDE.md`.

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

Install the local CLI and inspect the first deterministic action:

```powershell
python -m pip install -e ".[dev]"
accel --json --pretty next
```

Copilot users can also select `/accelerator`; Codex and Claude Code use the
shared `.agents/skills/accelerator/SKILL.md`.

## Joining mid-engagement?

If someone else on your team already cloned the customer repo, ask them for the GitHub URL, then `gh repo clone <org>/<repo>` and `code .` instead of running the template-create command.

---

**Continue →** [5. Discover with the customer](02-discover-with-the-customer.md)
