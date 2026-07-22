# Engagement artifact authority

The accelerator uses different artifacts for different kinds of truth. No two
files should claim authority over the same concern.

| Artifact | Authority |
|---|---|
| `.accelerator/private/evidence.db` | Local source excerpts, hashes, citations, conflicts, and disclosure decisions |
| `docs/discovery/solution-brief.md` | Customer-approved business, UX, risk, and acceptance intent |
| `accelerator.yaml` | Executable deployment, scenario, model, control, and KPI contract |
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

## Generated records

Acceptance reports, UAT sign-off, and handover packets are generated under
`.accelerator/artifacts/` by default because they can contain deployment URLs
or customer identities. Export reviewed copies into the customer's approved
operations location rather than committing them blindly.
