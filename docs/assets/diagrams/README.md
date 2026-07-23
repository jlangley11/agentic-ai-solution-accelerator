# Diagram provenance

The architecture SVGs below were generated with version `1.0.0` of the
[Azure Architecture Diagram Builder MCP](https://github.com/Arturo-Quiroga-MSFT/azure-architecture-diagram-builder/tree/main/mcp-server).
This follows the agent-ready workflow described in
[Beyond the Canvas](https://techcommunity.microsoft.com/blog/azurearchitectureblog/beyond-the-canvas-the-azure-architecture-diagram-builder-becomes-agent-ready/4534590).

The target-comparison diagrams use deterministic `list_services` and
`render_diagram` calls:

- `architecture-advisor-targets.svg`
- `foundry-prompt-agent.svg`
- `foundry-hosted-agent.svg`

The flagship scaffold sample uses `list_services`, `validate_architecture`, and
`render_diagram`:

- `sales-research-reference.svg`
- `sales-research-reference.mcp.json` — exact service graph, connections,
  render options, WAF result, generator version/source commit, and SHA-256 of
  the SVG

Each SVG embeds official Azure service icons and a generated-by footer. These
are design-time documentation artifacts; they do not deploy Azure resources.
Do not hand-edit MCP-generated SVGs; update the companion `.mcp.json` input and
regenerate through the pinned MCP version.

The navigation/process SVGs use Mermaid because they describe delivery flow
rather than Azure resource architecture.
