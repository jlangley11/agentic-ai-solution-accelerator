# Custom agents — quick reference

## Unified accelerator agent

Use `/accelerator` for the complete engagement. It delegates persistent state
and deterministic operations to the portable `accel` CLI:

```powershell
accel next
```

The task-specific agents below remain compatibility and specialist surfaces.
They do not infer persistent lifecycle state; run `accel next` first.

The accelerator ships a portable Agent Skill plus GitHub-specific custom agents
under `.github/agents/`. The same deterministic operations are available from
Copilot CLI, Codex, Claude Code, MCP, or a normal terminal.

!!! info "How to invoke"
    1. Open the customer repository and run `accel next`.
    2. In VS Code, open Copilot Chat (`Ctrl+Alt+I`), or start `copilot` in the terminal.
    3. At the top of the Chat panel, click the **agents dropdown** (the
       selector showing `Agent` / `Ask` / `Plan`). Every agent shipped
       in `.github/agents/` appears in that dropdown — pick one and
       follow the prompts.
    4. Or invoke `/accelerator`; use a specialist such as
       `/discover-scenario` only when its focused conversation is needed.
       Slash-command invocation works without autocomplete suggestions.

    !!! warning "Workspace Trust required"
        VS Code auto-discovers files under `.github/agents/` — no
        workspace setting needed — but only after you **trust the
        workspace**. If you cloned with Restricted Mode enabled, click
        "Trust the authors" when prompted; otherwise the dropdown stays
        empty and the agents are silently ignored. Reload the window
        (`Ctrl+Shift+P` → **Developer: Reload Window**) after trusting.

The full prompt for each agent is published in the navigation under [Reference → Custom agents](#when-to-run-which--by-walkthrough-step) — open one if you want to see exactly what Copilot will be told.

---

## At a glance — agents grouped by walkthrough step

If you're following the linear walkthrough, here's where each agent shows up. Optional ones are marked *(opt)*.

| Step | Authoritative CLI | Specialist agents |
|---|---|---|
| 1–4. Get ready + clone | `accel next` | `/accelerator`, `/delivery-guide` |
| **5. Discover** | `accel intake …` → `accel discover` | `/ingest-prd` → `/discover-scenario` |
| **6. Design + scaffold** | `accel design` → approval → `accel scaffold --dry-run/apply` | `/define-grounding`, `/implement-workers`, `/switch-to-variant` |
| **7. Provision** | `accel environment list` → `accel deploy --dry-run/execute/apply` | `/configure-landing-zone`, `/deploy-to-env` |
| **8. Iterate & evaluate** | `accel review` → `accel validate --execute` → `accel evaluate` | `/add-tool`, `/add-worker-agent`, `/implement-worker`, `/explain-change` |
| **9. UAT & handover** | `accel uat report/signoff` → `accel handover generate/approve` | `/accelerator` |
| **10. Operate** | `accel operate status` | `/delivery-guide` |
| **End of engagement** | Human-run destructive commands | `/teardown` |

For full inputs/outputs of each agent, see the detailed table below.

---

## When to run which — by walkthrough step

| Walkthrough step | Custom agent | What it does | Inputs you provide | What it writes |
|---|---|---|---|---|
| [5. Discover with the customer](start/deliver/02-discover-with-the-customer.md) | [`/ingest-prd`](../.github/agents/ingest-prd.agent.md) *(optional)* | Drafts from approved local evidence | Sources registered through `accel intake` | Draft brief with opaque evidence-reference comments; source text remains private |
| [5. Discover](start/deliver/02-discover-with-the-customer.md) | [`/discover-scenario`](../.github/agents/discover-scenario.agent.md) | Runs the structured discovery interview; proposes approved intent and manifest updates | Live workshop answers, notes, or PRD-draft TBDs | `docs/discovery/solution-brief.md` (approved intent), `accelerator.yaml` (executable contract) |
| [6. Decide and scaffold](start/deliver/03-scaffold-from-the-brief.md) | [`/accelerator`](../.github/agents/accelerator.agent.md) | Presents the Architecture Advisor recommendation and approval boundary | Approved brief + requirements | `accelerator.yaml -> architecture` through `accel design` |
| [6. Decide and scaffold](start/deliver/03-scaffold-from-the-brief.md) | [`/scaffold-from-brief`](../.github/agents/scaffold-from-brief.agent.md) | Compatibility specialist for authoring after `accel design/scaffold` | Approved architecture decision | Customer-specific prompt, grounding, tool, and eval edits |
| [6. Decide and scaffold](start/deliver/03-scaffold-from-the-brief.md) | [`/define-grounding`](../.github/agents/define-grounding.agent.md) | Picks FoundryIQ vs `none`, declares Search indexes, and records read-only catalog tools | Approved hosted architecture + grounding requirements | `scenario.agents[].retrieval/catalog_tools[]` + `scenario.retrieval.indexes[]` |
| [6. Decide and scaffold](start/deliver/03-scaffold-from-the-brief.md) | [`/implement-workers`](../.github/agents/implement-workers.agent.md) | Walks the supervisor DAG and fills every scaffolded worker's `prompt.py` / `transform.py` / `validate.py` + Foundry spec in dependency order | Approved hosted supervisor/workflow decision | Real implementations of every stub three-layer file + Foundry agent spec under `docs/agent-specs/` |
| [7. Provision the customer's Azure](start/deliver/04-provision-the-customers-azure.md) | [`/configure-landing-zone`](../.github/agents/configure-landing-zone.agent.md) | Picks the landing-zone tier and aligns `infra/` accordingly | Customer environment shape (pilot / mid-market / regulated) | `accelerator.yaml -> landing_zone.mode`; `infra/` shape selection |
| [7. Provision](start/deliver/04-provision-the-customers-azure.md) | [`/deploy-to-env`](../.github/agents/deploy-to-env.agent.md) | Registers a new Azure environment, wires OIDC, dispatches first deploy | Env name (`dev` / `uat` / `prod`), customer Entra app reg, target subscription | `deploy/environments.yaml` entry, GitHub Environment, OIDC federated credential |
| [8. Iterate & evaluate](start/deliver/05-iterate-and-evaluate.md) | [`/add-tool`](../.github/agents/add-tool.agent.md) | Scaffolds a side-effect tool with HITL + redteam baked in | Tool name, external system, side-effect category | `src/tools/<tool>.py`, unit test, redteam case, registration on the right worker |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/add-worker-agent`](../.github/agents/add-worker-agent.agent.md) | Runs `scripts/scaffold-agent.py` and the manual follow-ups | Agent id, scenario id, one-sentence capability | New `src/scenarios/<scenario>/agents/<agent_name>/` (3-layer module), `WORKERS` registry entry, Foundry agent spec stub |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/implement-worker`](../.github/agents/implement-worker.agent.md) | Fills a single scaffolded worker (`prompt.py` / `transform.py` / `validate.py` + Foundry spec) from brief + manifest | Worker id (reads scenario id, capability, retrieval mode from manifest) | Real implementation of the three-layer files for that one worker + matching Foundry spec |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/explain-change`](../.github/agents/explain-change.agent.md) | Preflight: maps your current diff to lint rules, evals, deploy steps that will fire | (Reads current git diff) | Read-only readout — does not modify files |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/switch-to-variant`](../.github/agents/switch-to-variant.agent.md) | Walks through re-authoring the scenario as `single-agent` or `chat-with-actioning` | Target variant + scenario id | New `src/scenarios/<id>/` package shaped for the variant; manual follow-ups for prompts/tests |
| Any (engagement-wide) | [`/accelerator`](../.github/agents/accelerator.agent.md) | Presents `accel` lifecycle state and approval boundaries | Free-form question | Delegates deterministic operations to the local CLI |
| Any (engagement-wide) | [`/delivery-guide`](../.github/agents/delivery-guide.agent.md) | Explains delivery rationale and role ownership | Free-form question | No lifecycle state of its own |
| End of engagement | [`/teardown`](../.github/agents/teardown.agent.md) | Pre-teardown checklist (KPI/cost export, customer signoff, HITL approver disable) + post-teardown soft-delete sweep for Cognitive Services accounts and Key Vaults that survive `azd down --purge` | `--env <env-name>` matching `deploy/environments.yaml` | No file writes; surfaces destructive `azd down` and `az ... purge` commands for the operator to run manually |

---

## When you can skip a custom agent

| Situation | Why you can skip |
|---|---|
| Customer handed you a clean PRD already | Skip `/ingest-prd`, but still register/review the source with `accel intake` before model-assisted extraction |
| Returning engineer, no scenario change | Skip the scaffold specialist; use `accel next` and keep the existing package when `accelerator.yaml` matches the approved intent |
| Pilot in your own dev sub | Skip `/configure-landing-zone` — Tier 1 (`standalone`) is the default and works for a sandbox |
| Tool is read-only (a retriever) | Skip `/add-tool` — add a module under `src/retrieval/` instead; HITL is for side-effects |
| Adding a single agent in the existing scenario | `/add-worker-agent` is preferred; `python scripts/scaffold-agent.py` is the low-level fallback |

---

## Where the prompts live

Every custom agent is a Markdown file under [`.github/agents/`](https://github.com/Azure-Samples/agentic-ai-solution-accelerator/tree/main/.github/agents) in the repo. The header `description:` field is what Copilot Chat shows in the picker; the body is the prompt Copilot follows. You can read or fork them — they're plain Markdown, version-controlled, and reviewable.

If you want to add a custom agent for your partner practice, follow the existing files as templates and PR it back; the accelerator team welcomes new patterns.
