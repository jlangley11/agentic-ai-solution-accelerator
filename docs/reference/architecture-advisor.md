# Architecture Advisor

The Architecture Advisor turns approved discovery intent into a reviewed
Foundry and application architecture decision before scaffolding begins.

```powershell
accel design
```

The command is deterministic: it evaluates the approved solution brief and
approved requirement statements, reports matched signals, compares
alternatives, and proposes four independent decisions:

When the local evidence ledger contains approved requirements, export
`docs/discovery/requirements-traceability.md` before design. The fingerprint
uses that sanitized committed artifact so CI and other engineers calculate the
same result without access to private source excerpts.

| Dimension | Values |
|---|---|
| Foundry agent type | `prompt-agent` · `hosted-agent` |
| Orchestration pattern | `single-agent` · `deterministic-workflow` · `supervisor-routing` |
| Application shell | `none` · `existing-app` · `workbench` · `custom` |
| Accelerator deployment target | `foundry-prompt` · `hosted-preview` · `selfhost` |

!!! important "Workflow is not a third Agent Service runtime type"
    Microsoft Foundry Agent Service documents two main types: prompt agents and
    Hosted agents. A workflow describes control flow. Deterministic workflows
    and supervisor routing require custom orchestration code and therefore map
    to a Hosted agent or the self-hosted application target.

## Review and approval

Accept the recommendation:

```powershell
accel design --approved-by "<partner architect>" --apply
```

Override one or more dimensions:

```powershell
accel design `
  --agent-type hosted-agent `
  --orchestration-pattern supervisor-routing `
  --application-shell workbench `
  --deployment-target selfhost `
  --override-reason "<customer or platform constraint>" `
  --approved-by "<partner architect>" `
  --apply
```

An override without a reason fails closed. The decision is recorded in
`accelerator.yaml -> architecture`, including:

- the original recommendation and confidence
- matched requirement signals
- alternatives and rejection rationale
- the approved selection
- approver, timestamp, and override reason
- a requirements fingerprint

If the approved brief or requirement set changes, the fingerprint changes and
`accel next` returns to the design stage.

## Recommendation model

| Requirement signal | Typical recommendation |
|---|---|
| Simple FAQ, knowledge assistant, summarization, managed tools, no custom runtime | Prompt agent + single agent |
| Existing LangGraph/Agent Framework/custom code or dependencies | Hosted agent |
| Custom protocol, webhook payload, voice, persistent session files | Hosted agent |
| Deterministic branching, retries, approvals, or ordered steps | Hosted agent + deterministic workflow |
| Multiple specialists, delegation, or supervisor aggregation | Hosted agent + supervisor routing |
| No application UI; another system calls the agent | `none` |
| Existing portal or customer application | `existing-app` |
| Structured input and report UX | `workbench` |
| Customer-specific UX/auth/state requirements | `custom` |

Side-effect tools are a Hosted/self-host signal because they must pass through
the accelerator's in-process `hitl.checkpoint(...)` boundary.

## Target comparison

The following diagram was generated with the
[Azure Architecture Diagram Builder MCP](https://techcommunity.microsoft.com/blog/azurearchitectureblog/beyond-the-canvas-the-azure-architecture-diagram-builder-becomes-agent-ready/4534590)
using its deterministic `render_diagram` tool.
See [diagram provenance](../assets/diagrams/README.md).

<div class="architecture-diagram">
  <img src="../assets/diagrams/architecture-advisor-targets.svg" alt="Architecture Advisor target comparison">
</div>

## Prompt-agent target

`foundry-prompt` provisions the Foundry project, models, prompt-agent versions,
FoundryIQ/Search, RBAC, monitoring, and readback checks. It does **not** deploy Container
Apps, ACR, or custom runtime code.

<div class="architecture-diagram">
  <img src="../assets/diagrams/foundry-prompt-agent.svg" alt="Foundry prompt-agent architecture">
</div>

## Hosted-agent target

`hosted-preview` deploys custom Agent Framework or other supported agent code
with Foundry-managed endpoint, session compute, identity, scaling, and
observability. The platform capability is documented by Foundry, while this
accelerator keeps its target preview-gated until its pinned azd extensions and
protocol packages leave prerelease.

<div class="architecture-diagram">
  <img src="../assets/diagrams/foundry-hosted-agent.svg" alt="Foundry hosted-agent architecture">
</div>

## References

- [Foundry Agent Service overview](https://learn.microsoft.com/azure/foundry/agents/overview)
- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Engagement artifact authority](artifact-model.md)
- [Accelerator CLI reference](accelerator-cli.md)
