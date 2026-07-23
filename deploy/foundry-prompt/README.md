# Foundry prompt-agent target

This target provisions the Foundry project, models, Search/FoundryIQ resources,
prompt-agent versions, RBAC, monitoring, and provisioning readback checks. It does
not deploy Container Apps, ACR, or custom agent runtime code.

## Prerequisites

- Python 3.11 or newer available locally as `python`
- Azure Developer CLI 1.28.0 or newer
- `microsoft.foundry` azd extension 1.0.0-beta.1
- Azure principal ID/type configured for Foundry and Search RBAC

Use it only after `accel design` records an approved `prompt-agent` +
`single-agent` decision:

```powershell
accel deploy --env prompt-agent --region <region> --dry-run
accel deploy --env prompt-agent --region <region> --execute
accel deploy --env prompt-agent --region <region> --execute --apply
```

The workspace shares the slim Foundry infrastructure modules with
`deploy/hosted-preview/`, but it stops after provisioning prompt agents. System
instructions remain repo-owned under `docs/agent-specs/`.
