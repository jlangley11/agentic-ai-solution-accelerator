# Hosted Agents preview workspace

This directory is an **explicit preview-only** Azure Developer CLI workspace for deploying the accelerator supervisor as a Microsoft Foundry Hosted Agent. Hosted Agents and the Python agent-server packages are prerelease and have no production SLA. Do not use this surface for production workloads without an approved preview exception.

The repository-root `azure.yaml` is unchanged: running `azd up` from the repository root continues to deploy the current self-hosted Container Apps solution.

## Prerequisites

- Azure Developer CLI 1.27.1 or newer; 1.28.0 is the verified version.
- Azure CLI authenticated to the target tenant and subscription.
- Python 3.13 or newer available locally as `python`.
- `microsoft.foundry` 1.0.0-beta.1 and `azure.ai.agents` 1.0.0-beta.6 or newer:

  ```console
  azd ext install microsoft.foundry
  azd ext install azure.ai.agents --version 1.0.0-beta.6
  ```

- Permission to create a resource group, Foundry resources, AI Search, Log Analytics, Application Insights, model deployments, connections, and role assignments.
- Hosted Agents and model capacity in the selected Azure region.
- A short local checkout path on Windows to avoid remote-build package path limits.

The deployed code runtime is Python 3.14. The repository's `agent-framework`
meta-package currently selects a Hyperlight backend on Python 3.13 whose Linux
wheel is unavailable to Hosted Agents remote build; Python 3.14 excludes that
conditional dependency.

## Deploy

Run these commands from the repository root.

1. Bootstrap the exact preview dependencies into the current Python
   environment:

   ```console
   python deploy/hosted-preview/hooks/bootstrap.py
   ```

2. Run the hosted deployment preflight:

   ```console
   python scripts/preflight-deploy.py --region eastus2 --deployment-target hosted-preview --acknowledge-preview
   ```

3. Stage the exact runtime source below this workspace:

   ```console
   python deploy/hosted-preview/hooks/prepare.py
   ```

4. Enter the isolated workspace. Use the working directory directly; the
   verified azd 1.28.0 binary does not reliably use `-C` for nested project
   discovery.

   ```console
   cd deploy/hosted-preview
   ```

5. Select an azd environment and set its subscription and location if needed:

   ```console
   azd env new hosted-preview
   azd env set AZURE_SUBSCRIPTION_ID <subscription-id>
   azd env set AZURE_LOCATION eastus2
   azd env set AZURE_PRINCIPAL_ID <operator-object-id>
   ```

   `infra/main.parameters.json` uses
   `${AZURE_PRINCIPAL_TYPE=User}` so local interactive deployments default to
   `User`. CI persists `ServicePrincipal` because the GitHub OIDC identity is
   an application service principal. For an interactive deployment, obtain the
   operator object ID with `az ad signed-in-user show --query id -o tsv`.

6. Provision the preview infrastructure:

   ```console
   azd provision
   ```

   The postprovision hook rewrites custom Foundry-provider outputs to canonical
   uppercase environment names before Linux code deployment.

7. Deploy the hosted-agent code. The ordered predeploy hooks repeat dependency
   bootstrap and source preparation for deterministic local behavior. The
   postdeploy hook runs the shared scenario provisioner:

   ```console
   azd deploy
   ```

Set `HOSTED_PREVIEW_CANARY=1` in the azd environment before deployment to run the shared post-provision canary.

## Invoke

The Responses protocol accepts a company name as free text:

```console
azd ai agent invoke hosted-supervisor --new-session "Contoso"
```

For the Invocations protocol, provide a JSON request matching the active scenario schema:

```console
azd ai agent invoke hosted-supervisor --protocol invocations --input-file request.json
```

## Remove the preview environment

```console
azd down --force --purge
```

The generated `app/src`, `app/accelerator.yaml`, `app/pyproject.toml`, and `app/README.md` are intentionally ignored. Re-run the prepare hook whenever validating the staged package independently of `azd deploy`.
