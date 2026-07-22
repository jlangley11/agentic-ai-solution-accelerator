# Version matrix

Known-good GA versions of the accelerator's canonical SDKs, plus narrowly documented prerelease exceptions for the Foundry hosted-agent serving stack. A weekly CI job (`.github/workflows/version-matrix.yml`) runs `scripts/ga-sdk-freshness.py`, which queries PyPI for the latest non-prerelease version of each package under `ga-versions.yaml -> sdks`. The script classifies each package into one of three buckets:

- **drift** — PyPI has a newer GA than the pinned `min`. The workflow fails and opens a tracking issue.
- **unknown** — PyPI lookup failed (404, network, JSON decode, or no GA release). The workflow surfaces the warning in the run summary but does **not** fail and does **not** open an issue — a transient PyPI hiccup should not generate noise.
- **ok** — PyPI returned a GA `<=` the pinned `min`.

Deprecation policy: **N-1 minor** supported.

Stable packages are pinned in `pyproject.toml`; `ga-versions.yaml` is the manifest lint enforces drift against. Update all three together: this table, `pyproject.toml`, and `ga-versions.yaml`.

| Package | Pinned range | Last validated | Latest tested | Notes |
|---|---|---|---|---|
| `agent-framework` | `>=1.11.0,<2.0.0` | 2026-07-20 | 1.11.0 | Microsoft Agent Framework orchestration |
| `azure-ai-projects` | `>=2.3.0,<3.0.0` | 2026-07-20 | 2.3.0 | Stable hosted-agent versioning and code-upload APIs |
| `azure-ai-agents` | `>=1.1.0,<2.0.0` | 2026-07-20 | 1.1.0 | Foundry prompt-agent operations |
| `azure-ai-evaluation` | `>=1.0.0,<2.0.0` | 1.0.x |  | Evals SDK |
| `azure-identity` | `>=1.25.3,<2.0.0` | 2026-07-20 | 1.25.3 | `DefaultAzureCredential`, `ManagedIdentityCredential` |
| `azure-keyvault-secrets` | `>=4.8.0,<5.0.0` | 4.8.x |  | KV references |
| `azure-search-documents` | `>=12.0.0,<13.0.0` | 2026-07-20 | 12.0.0 | Search schema/vectorizer compatibility verified |
| `azure-mgmt-cognitiveservices` | `>=14.1.0,<15.0.0` | 2026-07-20 | 14.1.0 | Foundry control-plane provisioning |
| `azure-monitor-opentelemetry` | `>=1.6.0,<2.0.0` | 1.6.x |  | App Insights distro |
| `opentelemetry-api` / `-sdk` | `>=1.27.0,<2.0.0` | 1.27.x |  | Pinned together to avoid protocol drift |
| `fastapi` | `>=0.115.0,<1.0.0` | 0.115.x |  | HTTP surface |
| `pydantic` | `>=2.9.0,<3.0.0` | 2.9.x |  | Schemas |

## Local delivery and workbench tooling

| Tool/package | Pinned range | Purpose |
|---|---|---|
| `mcp` | `>=1.28.1,<2.0.0` *(optional extra)* | `accel-mcp` local stdio adapter |
| `python-pptx` | `>=1.0.2,<2.0.0` | Local PowerPoint evidence extraction |
| `openpyxl` | `>=3.1.5,<4.0.0` | Local Excel evidence extraction |
| Node.js | `20.19+` or `22.12+` | Vite 8 reference workbench |
| Vite | `^8.1.4` | Frontend build/dev server |
| Vitest | `^4.1.10` | Frontend behavior and protocol tests |
| Azure Architecture Diagram Builder MCP | `1.0.0` *(design-time external tool)* | Generates committed Azure-branded architecture SVGs |

## Hosted-agent toolchain prerelease exceptions

Foundry documentation lists Hosted agents as a main Agent Service type. The
accelerator nevertheless keeps `hosted-preview` explicitly gated because its
pinned azd extensions and Python protocol-serving packages remain prerelease.
These packages are outside the GA freshness loop.

Install the preview serving entrypoint explicitly with
`pip install -e ".[hosted-preview]"` (or `".[dev,hosted-preview]"` for
development). The self-hosted FastAPI application remains the default; importing
or running `src.agent_host` is an explicit preview opt-in.

Provision the selected environment before starting the hosted entrypoint:

```powershell
python scripts/foundry-provision.py --env <env>
python -m src.agent_host
```

The nested workspace now wires predeploy staging, provision/deploy, shared
postdeploy provisioning, and the protocol smoke. Root selfhost remains the
default.

| Package | Verified version | Status | Revisit |
|---|---|---|---|
| `agent-framework-foundry-hosting` | `1.0.0a260709` | Alpha; no GA release | 2026-10 |
| `azure-ai-agentserver-core` | `2.0.0b7` | Beta; no GA release | 2026-10 |
| `azure-ai-agentserver-responses` | `1.0.0b8` | Beta; no GA release | 2026-10 |
| `azure-ai-agentserver-invocations` | `1.0.0b6` | Beta; no GA release | 2026-10 |

See [Phase 0 hosted-agent spike report](plans/phase0-spike-report.md) for the live deployment evidence and required plan adjustments.

## Platform targets
- Current self-hosted runtime: Python **3.11** and **3.12**.
- Hosted-agent code runtime: Python **3.14** for the accelerator workspace. Python
  3.13 starts the protocol server locally, but remote build cannot resolve the
  current `agent-framework` Hyperlight Linux dependency; 3.14 excludes that
  conditional package and has been dependency-tested. The extension rejects
  Python 3.12.
- Azure Developer CLI: **1.28.0** verified.
- Foundry extensions: `microsoft.foundry` **1.0.0-beta.1** and `azure.ai.agents` **1.0.0-beta.6** verified.
- Accelerator Hosted target: **preview-gated toolchain** despite Hosted agents
  being documented as a main Foundry Agent Service type.
- Foundry model deployments: default `gpt-5-mini` (flagship; parameterized via `modelName` / `modelDeploymentName` in `infra/main.bicep`). Partners override per engagement; the weekly freshness script validates canonical GA SDKs against PyPI regardless of model choice.
- Azure regions: the current hosted-agent list contains 29 regions; model and AI Search capacity remain separate constraints.

## ARM api-versions
- The lint rule `no_preview_api_versions` rejects any `*-preview` api-version in `infra/**`. Narrow, documented exemptions live in `infra/.ga-exceptions.yaml`. Each exemption must carry a `reason` and a `revisit_by` month.
- **Current exemption set** (2 entries): the parent `Microsoft.CognitiveServices/accounts` and child `Microsoft.CognitiveServices/accounts/projects` use `2025-04-01-preview` because project management is not exposed by the GA parent shape and the project child has no GA api-version. Model deployments, RAI policy, and RBAC remain on GA `2024-10-01`. Revisit: 2026-10.

## Cadence
- **Weekly** (`version-matrix.yml`): `ga-sdk-freshness.py` hits PyPI; opens an issue only on real drift. Transient lookup failures land in the workflow summary as warnings.
- **Monthly**: maintainer review; cut a minor release of the template if fixes or new features land.
- **Quarterly**: blessed-pattern promotions (see `CONTRIBUTING.md`).
