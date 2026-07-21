# Phase 0 hosted-agent verification spike

**Run date:** 2026-07-20  
**Region:** East US 2 (hosted agents); West US 3 (temporary free AI Search capacity)  
**Outcome:** Hosted-agent code deployment works, but the modernization plan requires preview gating and several runtime adjustments before Hosted Agents can become the accelerator default.

## Executive decision

Do not flip the production default from the current self-hosted path yet. Foundry Agent Service is GA, but **Hosted Agents remain preview**, and every Python serving package needed by the target runtime is alpha or beta. Phase 1 may continue as an explicit hosted-preview implementation, but Phase 2 must not make it the default until either:

1. Hosted Agents and the serving packages reach GA, or
2. the accelerator adopts an explicit, time-bounded preview policy approved for the engagement.

The live spike otherwise validated code deployment, both protocol endpoints, incremental SSE, managed identity, AI Search egress, immutable versions, and sub-two-minute provisioning.

## Verified toolchain

| Component | Verified version | Result |
|---|---:|---|
| Azure Developer CLI | `1.28.0` | Required; installed as a signed portable binary because the existing MSI was administrator-managed |
| `microsoft.foundry` extension | `1.0.0-beta.1` | Meta-extension installed successfully |
| `azure.ai.agents` extension | `1.0.0-beta.6` | Supplies `azd ai agent`; effective minimum `azd` is 1.27.1 |
| Local Python | `3.13.14` | Required by the generated hosted-agent manifest |

The extension rejected Python 3.12.9. On Windows, the long session path also exceeded practical package-install path limits; moving the sample to a short path resolved the failure.

## Generated deployment contract

`azd ai agent init --deploy-mode code` adopted the official samples with this service shape:

```yaml
services:
  agent-framework-agent-basic-responses:
    host: azure.ai.agent
    kind: hosted
    language: python
    project: src/agent-framework-agent-basic-responses
    codeConfiguration:
      dependencyResolution: remote_build
      entryPoint: main.py
      runtime: python_3_13
    container:
      resources:
        cpu: "0.5"
        memory: 1Gi
    protocols:
      - protocol: responses
        version: 2.0.0
```

The current schema uses `codeConfiguration`; it does not use a `deploy-mode` field in `azure.yaml`. `entryPoint` is the code-deploy start contract. `startupCommand` is not present in the generated sample.

## Package verification

### Stable SDK pins

The following current GA releases imported successfully against the repository's existing Foundry and Search code:

| Package | Version |
|---|---:|
| `agent-framework` | `1.11.0` |
| `azure-ai-projects` | `2.3.0` |
| `azure-ai-agents` | `1.1.0` |
| `azure-identity` | `1.25.3` |
| `azure-search-documents` | `12.0.0` |
| `azure-mgmt-cognitiveservices` | `14.1.0` |

`src/scenarios/sales_research/retrieval.py::index_definition()` constructed and serialized its vector + semantic schema with `azure-search-documents==12.0.0`; the existing `AzureOpenAIVectorizerParameters` shape remains valid.

### Required prerelease packages

| Package | Version | Status |
|---|---:|---|
| `agent-framework-foundry-hosting` | `1.0.0a260709` | Alpha; no GA release |
| `azure-ai-agentserver-core` | `2.0.0b7` | Beta; no GA release |
| `azure-ai-agentserver-responses` | `1.0.0b8` | Beta; no GA release |
| `azure-ai-agentserver-invocations` | `1.0.0b6` | Beta; no GA release |

The versions are recorded under `ga-versions.yaml -> prerelease_exceptions`; Phase 5 must add lint enforcement for the exception shape.

## Provisioning and resource inventory

The official Responses sample provisioned in 87.6 seconds; the Invocations sample provisioned in 74.2 seconds. Initial code deploys completed in 134.8 seconds and 130.2 seconds respectively. Subsequent immutable versions deployed in 77-80 seconds.

The default code-mode resource group contained only:

- `Microsoft.CognitiveServices/accounts`
- `Microsoft.CognitiveServices/accounts/projects`

`AZD_AGENT_SKIP_ACR=true`; no ACR was created. No Container Apps, Key Vault, workload managed identity, Log Analytics, or App Insights resource appeared in the resource group.

Both temporary resource groups were removed with `azd down --force --purge` and verified absent after the spike.

## Protocol behavior

### Responses

After correcting the sample's model environment variable:

| Measurement | Result |
|---|---:|
| First successful server response | 14.423 s |
| First byte | 8.093 s |
| Immediate warm server response | 7.584 s |
| Immediate warm first byte | 1.695 s |

The generated sample deployed `gpt-5.4-mini`, but `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` resolved to an empty string. Version 1 therefore failed readiness with `session_not_ready`; explicitly setting `AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.4-mini` fixed version 2.

### Invocations and SSE

The raw endpoint returned HTTP/2 `200`, `Content-Type: text/event-stream`, `X-Agent-Session-Id`, `X-Agent-Invocation-Id`, and `X-Platform-Server`.

Direct bearer authentication succeeded with scope:

```text
https://ai.azure.com/.default
```

A 20-line response arrived as 31 network chunks. A longer response produced 197 chunks between 7.251 seconds and 9.898 seconds, while the full request completed in 14.915 seconds. The platform therefore passed bytes incrementally rather than buffering until request completion.

### Dual protocol

A single version declaring both protocols deployed successfully and exposed both endpoint URLs:

```yaml
protocols:
  - protocol: invocations
    version: 2.0.0
  - protocol: responses
    version: 2.0.0
```

Declaration is not implementation. The raw `InvocationAgentServerHost` process continued to serve Invocations, while the declared Responses endpoint returned HTTP 404. The current `agent-framework-foundry-hosting` package exports separate `ResponsesHostServer` and `InvocationsHostServer` classes but no documented composite host. Phase 1 must prototype and test a shared ASGI composition layer or wait for a supported composite API.

## Runtime environment

The hosted probe observed:

| Variable/behavior | Result |
|---|---|
| `FOUNDRY_AGENT_ID`, `FOUNDRY_AGENT_NAME`, `FOUNDRY_AGENT_VERSION` | Present |
| `FOUNDRY_AGENT_SESSION_ID` | Present |
| `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_PROJECT_ARM_ID` | Present |
| `HOME` | `/home/session` |
| `PORT` | `8088` |
| `SSE_KEEPALIVE_INTERVAL` | `15` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Present only after explicit azd env configuration |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Not present |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Not present |

The protocol server logged that tracing was configured, but the request span was non-recording. A custom child span inherited the request trace ID, proving context propagation, but there was no recording/export pipeline. Phase 1 must retain explicit Azure Monitor configuration until a deployed environment proves recording and export.

## Identity and egress

Each hosted agent exposed a dedicated agent identity. The spike granted the Invocations agent only `Search Index Data Reader` on a temporary AI Search service. Using `DefaultAzureCredential`, the hosted process:

1. acquired a token for `https://ai.azure.com/.default`,
2. queried the cross-region Search index, and
3. returned the seeded document.

This verifies Foundry/model and Azure AI Search data-plane egress. Repository scanning found runtime ARM use only in `src/bootstrap.py` for Search role assignment; that operation should move to the deploy-time provisioner as planned.

## Session behavior

The automatically persisted Responses session became stopped after idle. Reusing it failed twice with HTTP 500 after 35-37 seconds. `--new-session` incorrectly reused the same stopped session ID and also failed.

Creating a session explicitly succeeded:

| Operation | Result |
|---|---:|
| `azd ai agent sessions create` | 10.6 s |
| First invocation on explicit session | 8.645 s |
| First byte on explicit session | 1.872 s |

Until the extension fixes stopped-session recovery, clients should create fresh sessions explicitly for independent research requests and avoid relying on automatic resume.

## CLI and sample defects found

1. `azd ai agent doctor --local-only` requires `agent.yaml`, but the official initialized samples do not include it.
2. The official model deployment does not populate `AZURE_AI_MODEL_DEPLOYMENT_NAME`.
3. `azd ai agent run` ignores `codeConfiguration.entryPoint` and auto-detects `main.py`; a non-default entry point requires `--start-command`.
4. Local tracing probes IMDS before falling back to developer credentials, producing noisy error spans.
5. `--new-session` can reuse a stopped session instead of allocating a new one.
6. East US 2 had no capacity for a new free AI Search service during the spike; West US 3 succeeded. This is Search capacity, not Hosted Agents region support.

## Required plan adjustments

1. Treat Hosted Agents as an explicit preview target until service and serving packages are GA.
2. Require `azd>=1.27.1`; recommend the verified stable `1.28.0`.
3. Use the live `codeConfiguration` schema and Python 3.13 in Phase 1/2.
4. Set the model deployment environment variable explicitly.
5. Preserve explicit Azure Monitor wiring; platform injection was absent.
6. Build and test dual-protocol ASGI composition before replacing FastAPI.
7. Make fresh-session creation the default for stateless research requests.
8. Add Windows short-path guidance to preflight and troubleshooting.
9. Add lint enforcement for `ga-versions.yaml -> prerelease_exceptions`.

## Authoritative references

- [Hosted Agents concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Hosted-agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- [Azure YAML reference](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/azure-yaml-reference)
- [Source-code deployment](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-code)
- [Hosted-agent runtime contract](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agent-contract)
- [Hosted-agent permissions](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agent-permissions)
- [Hosted-agent sessions](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-sessions)
- [Hosted-agent private networking](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks)
- [Official Foundry samples](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)
- [Azure Developer CLI releases](https://github.com/Azure/azure-dev/releases)
