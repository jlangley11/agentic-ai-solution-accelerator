# Custom agents — quick reference

The accelerator ships 13 **custom VS Code agents** under `.github/agents/`. Each one is a structured prompt that drives GitHub Copilot Chat through a specific delivery task — discover, scaffold, configure infra, add a tool, etc. They keep you on the supported path and prevent accidental architecture drift.

!!! info "How to invoke"
    1. Open the customer repo in VS Code.
    2. Open the Copilot Chat sidebar (`Ctrl+Alt+I` or the 💬 icon).
    3. At the top of the Chat panel, click the **agents dropdown** (the
       selector showing `Agent` / `Ask` / `Plan`). Every agent shipped
       in `.github/agents/` appears in that dropdown — pick one and
       follow the prompts.
    4. Or: type `/scaffold-from-brief` (etc.) directly in the chat input.
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

| Step | Agents you'll run |
|---|---|
| 1. Get oriented | — |
| 2. Set up your machine | — |
| 3. Rehearse in a sandbox | [`/scaffold-from-brief`](../agents/scaffold-from-brief.agent.md) |
| 4. Clone for the customer | — |
| **5. Discover with the customer** | [`/ingest-prd`](../agents/ingest-prd.agent.md) *(opt)* → [`/discover-scenario`](../agents/discover-scenario.agent.md) |
| **6. Scaffold from the brief** | [`/scaffold-from-brief`](../agents/scaffold-from-brief.agent.md) → [`/define-grounding`](../agents/define-grounding.agent.md) → [`/implement-workers`](../agents/implement-workers.agent.md) (or [`/implement-worker`](../agents/implement-worker.agent.md) one-at-a-time) · [`/switch-to-variant`](../agents/switch-to-variant.agent.md) *(opt)* |
| **7. Provision the customer's Azure** | [`/configure-landing-zone`](../agents/configure-landing-zone.agent.md) → [`/deploy-to-env`](../agents/deploy-to-env.agent.md) |
| **8. Iterate & evaluate** | [`/add-tool`](../agents/add-tool.agent.md) · [`/add-worker-agent`](../agents/add-worker-agent.agent.md) · [`/implement-worker(s)`](../agents/implement-worker.agent.md) · [`/explain-change`](../agents/explain-change.agent.md) · [`/switch-to-variant`](../agents/switch-to-variant.agent.md) |
| 9. UAT & handover | — (manual) |
| 10. Operate (Day 2) | — (manual) |
| Any time | [`/delivery-guide`](../agents/delivery-guide.agent.md) — engagement-wide co-pilot |

For full inputs/outputs of each agent, see the detailed table below.

---

## When to run which — by walkthrough step

| Walkthrough step | Custom agent | What it does | Inputs you provide | What it writes |
|---|---|---|---|---|
| [5. Discover with the customer](start/deliver/02-discover-with-the-customer.md) | [`/ingest-prd`](../.github/agents/ingest-prd.agent.md) *(optional)* | Pre-drafts the brief from a customer PRD / BRD / spec | Path to PRD (`.md` / `.txt` / `.docx` / `.pdf`) | Draft `docs/discovery/solution-brief.md` with `STATUS: AI-extracted draft` banner + per-section evidence comments |
| [5. Discover](start/deliver/02-discover-with-the-customer.md) | [`/discover-scenario`](../.github/agents/discover-scenario.agent.md) | Runs the structured discovery interview; fills `solution-brief.md` and `accelerator.yaml` | Live workshop answers, notes, or PRD-draft TBDs | `docs/discovery/solution-brief.md` (canonical), `accelerator.yaml` (`solution.*`, `acceptance.*`, `kpis[]`) |
| [6. Scaffold from the brief](start/deliver/03-scaffold-from-the-brief.md) | [`/scaffold-from-brief`](../.github/agents/scaffold-from-brief.agent.md) | Materialises the brief into code, infra, evals, telemetry | Filled `solution-brief.md` (zero TBDs) | New `src/scenarios/<id>/` package, `accelerator.yaml` `scenario:` block, eval golden cases, redteam cases |
| [6. Scaffold from the brief](start/deliver/03-scaffold-from-the-brief.md) | [`/define-grounding`](../.github/agents/define-grounding.agent.md) | Picks FoundryIQ vs `none` per worker, declares AI Search indexes underneath FoundryIQ, lists Foundry portal catalog tools | Filled brief (section 5 grounding sources + external systems) | Populated `scenario.agents[].retrieval` + `scenario.agents[].catalog_tools[]` blocks; `scenario.retrieval.indexes[]` |
| [6. Scaffold from the brief](start/deliver/03-scaffold-from-the-brief.md) | [`/implement-workers`](../.github/agents/implement-workers.agent.md) | Walks the supervisor DAG and fills every scaffolded worker's `prompt.py` / `transform.py` / `validate.py` + Foundry spec in dependency order | Scenario id (reads everything else from manifest + brief) | Real implementations of every stub three-layer file + Foundry agent spec under `docs/agent-specs/` |
| [7. Provision the customer's Azure](start/deliver/04-provision-the-customers-azure.md) | [`/configure-landing-zone`](../.github/agents/configure-landing-zone.agent.md) | Picks the landing-zone tier and aligns `infra/` accordingly | Customer environment shape (pilot / mid-market / regulated) | `accelerator.yaml -> landing_zone.mode`; `infra/` shape selection |
| [7. Provision](start/deliver/04-provision-the-customers-azure.md) | [`/deploy-to-env`](../.github/agents/deploy-to-env.agent.md) | Registers a new Azure environment, wires OIDC, dispatches first deploy | Env name (`dev` / `uat` / `prod`), customer Entra app reg, target subscription | `deploy/environments.yaml` entry, GitHub Environment, OIDC federated credential |
| [8. Iterate & evaluate](start/deliver/05-iterate-and-evaluate.md) | [`/add-tool`](../.github/agents/add-tool.agent.md) | Scaffolds a side-effect tool with HITL + redteam baked in | Tool name, external system, side-effect category | `src/tools/<tool>.py`, unit test, redteam case, registration on the right worker |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/add-worker-agent`](../.github/agents/add-worker-agent.agent.md) | Runs `scripts/scaffold-agent.py` and the manual follow-ups | Agent id, scenario id, one-sentence capability | New `src/scenarios/<scenario>/agents/<agent_name>/` (3-layer module), `WORKERS` registry entry, Foundry agent spec stub |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/implement-worker`](../.github/agents/implement-worker.agent.md) | Fills a single scaffolded worker (`prompt.py` / `transform.py` / `validate.py` + Foundry spec) from brief + manifest | Worker id (reads scenario id, capability, retrieval mode from manifest) | Real implementation of the three-layer files for that one worker + matching Foundry spec |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/explain-change`](../.github/agents/explain-change.agent.md) | Preflight: maps your current diff to lint rules, evals, deploy steps that will fire | (Reads current git diff) | Read-only readout — does not modify files |
| [8. Iterate](start/deliver/05-iterate-and-evaluate.md) | [`/switch-to-variant`](../.github/agents/switch-to-variant.agent.md) | Walks through re-authoring the scenario as `single-agent` or `chat-with-actioning` | Target variant + scenario id | New `src/scenarios/<id>/` package shaped for the variant; manual follow-ups for prompts/tests |
| Any (engagement-wide) | [`/delivery-guide`](../.github/agents/delivery-guide.agent.md) | End-to-end engagement co-pilot — answers "what's next?" across the whole motion | Free-form question | No file writes; conversational guidance |

---

## When you can skip a custom agent

| Situation | Why you can skip |
|---|---|
| Customer handed you a clean PRD already | Skip `/ingest-prd` — you can pre-fill the brief by hand if the doc is short |
| Returning engineer, no scenario change | Skip `/scaffold-from-brief` — the existing scaffold is fine if `accelerator.yaml` matches the brief |
| Pilot in your own dev sub | Skip `/configure-landing-zone` — Tier 1 (`standalone`) is the default and works for a sandbox |
| Tool is read-only (a retriever) | Skip `/add-tool` — add a module under `src/retrieval/` instead; HITL is for side-effects |
| Adding a single agent in the existing scenario | Skip the custom agent and run `python scripts/scaffold-agent.py` directly — same code path |

---

## Where the prompts live

Every custom agent is a Markdown file under [`.github/agents/`](https://github.com/Azure-Samples/agentic-ai-solution-accelerator/tree/main/.github/agents) in the repo. The header `description:` field is what Copilot Chat shows in the picker; the body is the prompt Copilot follows. You can read or fork them — they're plain Markdown, version-controlled, and reviewable.

If you want to add a custom agent for your partner practice, follow the existing files as templates and PR it back; the accelerator team welcomes new patterns.
