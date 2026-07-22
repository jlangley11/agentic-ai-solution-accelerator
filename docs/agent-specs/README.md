# Agent specs — durable Foundry system instructions

## Flagship agents at a glance

The flagship scenario (Sales Research & Personalised Outreach) ships with five Foundry agents. Detailed system instructions live in the per-agent files in this directory; a partner-facing summary first:

| Agent | Role | Output | HITL / tool posture |
|---|---|---|---|
| [`accel-sales-research-supervisor`](accel-sales-research-supervisor.md) | Orchestrator — routes the scenario across the four workers and composes their outputs | Composed account research + outreach payload | No tools of its own; downstream tool calls inherit each worker's HITL policy |
| [`accel-account-planner`](accel-account-planner.md) | Builds the account brief: company, segment, signals, decision-makers | Structured account profile (citations required) | Read-only retrieval; no HITL |
| [`accel-icp-fit-analyst`](accel-icp-fit-analyst.md) | Scores ICP fit + maps to a tier recommendation | Fit score + recommended play | Read-only retrieval; no HITL |
| [`accel-competitive-context`](accel-competitive-context.md) | Surfaces competitive context + cloud footprint signals | Competitive notes + footprint signals | Read-only retrieval; no HITL |
| [`accel-outreach-personalizer`](accel-outreach-personalizer.md) | Drafts the personalised outreach + invokes side-effect tools (CRM write, send email) | Outreach copy + tool-call results | **HITL required on every side-effect tool** (`crm_write_contact`, `send_email` use `HITL_POLICY = "always"`) |

Use the per-agent files below for the actual system instructions; everything else on this page is bootstrap mechanics.

---

## Provisioning mechanics

`src/provisioning.py` reads one Markdown file per manifest agent and creates or
updates the corresponding version in Foundry. Self-host invokes it through
`src/bootstrap.py`; Hosted preview invokes it from the postdeploy hook.

## File format

```markdown
# Agent: <agent_name>

**Pattern:** <one-line description of what shape this agent fills>

## Instructions
<system instructions the agent runs with>
```

The model deployment is not declared here. `accelerator.yaml.models[]` and
`scenario.agents[].model` select the provisioned deployment; omitting the agent
override uses the reserved `default` slug. Lint fails if a spec declares its
own `**Model:**` field.

## Important

**Authoring source of truth:** the `.md` files in this directory.
**Runtime location:** Foundry — shared provisioning syncs each spec verbatim to
the matching agent version. The portal displays the materialized runtime copy
but is not a durable authoring surface; manual instruction edits are
**transient** and will be overwritten on the next sync.

The supported loop is: edit the `.md` → apply `accel deploy` → run
`accel evaluate`. Rollback is the same path after reverting the spec.

!!! warning "Provisioning owns model, instructions, and the managed KB tool"
    `src/provisioning.py` creates a new `PromptAgentDefinition` version from
    the repo-owned spec and manifest. It refreshes the accelerator-managed
    FoundryIQ KB tool while preserving other existing catalog tools. Record
    governed catalog-tool intent in `scenario.agents[].catalog_tools[]`; do not
    treat portal state as the durable declaration.

Instructions never become portal-managed. `BOOTSTRAP_SKIP=1` exists for tests
and controlled diagnostics, not as a supported customer authoring mode.

Do NOT reference these `.md` files at runtime. Do NOT import from them.

## Flagship agents (5)

The flagship ships one supervisor plus four workers. Each agent's
`.md` file in this directory is the source of truth for its
instructions; the table at the top of this page is the partner-facing
summary. Add new agents to a scaffolded scenario with
`python scripts/scaffold-agent.py` (writes a matching spec stub).
