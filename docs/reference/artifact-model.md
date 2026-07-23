# Engagement artifact authority

The accelerator uses different artifacts for different kinds of truth. No two
files should claim authority over the same concern.

| Artifact | Authority |
|---|---|
| `.accelerator/private/evidence.db` | Local source excerpts, hashes, citations, conflicts, and disclosure decisions |
| `docs/discovery/solution-brief.md` | Customer-approved business, UX, risk, and acceptance intent |
| `accelerator.yaml -> architecture` | Approved agent type, implementation pattern, orchestration, application shell, deployment target, rationale, and requirements fingerprint |
| Remaining `accelerator.yaml` | Executable deployment, scenario, model, control, and KPI contract |
| `scenario.architecture_diagram` + `docs/assets/diagrams/*.mcp.json` | Required scaffold diagram path, pinned MCP generator/tool contract, exact graph, WAF result, and SVG checksum |
| `src/scenarios/` and `docs/agent-specs/` | Runtime implementation and Foundry instructions |
| `evals/` | Machine-verifiable acceptance and safety contract |
| `.accelerator/artifacts/` | Local acceptance, UAT, migration, and handover records |

## Evidence ledger

The evidence database is gitignored and local-only. Adding a document does not
authorize its text for model use. Each source starts with
`disclosure_status=local_only`; an explicit user decision is required before a
model-assisted workflow may request its chunks.

The ledger never replaces the approved solution brief. It records why a
requirement exists and where it came from.

## Brief and manifest

The solution brief is the customer-readable approval contract.
`accelerator.yaml` is the executable projection consumed by provisioning,
runtime loading, lint, evaluation, and deployment.

Parity checks should fail when a required approved decision is absent from the
manifest. Narrative detail that has no runtime representation remains in the
brief.

### When brief and manifest diverge

The brief records customer intent; `accelerator.yaml` records the approved
executable decision. Runtime and deployment consume the manifest. If the brief
or sanitized requirement export changes after architecture approval, the
requirements fingerprint becomes stale and `accel next` returns to Design.
Reconcile and approve the new decision rather than silently deploying either
side.

## Architecture diagram

The scenario manifest declares the expected SVG and provenance paths under
`scenario.architecture_diagram`. The SVG is generated through Azure Architecture
Diagram Builder MCP, while the companion `.mcp.json` captures the canonical
service graph, connection labels, groups, render options, validation result,
generator version/tool sequence, and checksum.

The diagram is a reviewed visual projection, not a second deployment contract.
If it disagrees with `accelerator.yaml` or Bicep, the executable artifacts win
and the diagram must be regenerated. Lifecycle and lint keep the scaffold stage
blocked when the declared files are absent or the SVG no longer matches its
provenance checksum.

## Generated records

Acceptance reports, UAT sign-off, and handover packets are generated under
`.accelerator/artifacts/` by default because they can contain deployment URLs
or customer identities. Export reviewed copies into the customer's approved
operations location rather than committing them blindly.
