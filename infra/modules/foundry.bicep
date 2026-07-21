// Microsoft Foundry (Cognitive Services AIServices) — GA-only shape.
//
// Provisions:
//   - Cognitive Services account (kind=AIServices)         GA 2024-10-01
//   - RAI (content filter) policy                          GA 2024-10-01
//   - Model deployment bound to the RAI policy             GA 2024-10-01
//   - Foundry project                                      2025-04-01-preview *
//   - Role assignments for the workload managed identity   GA 2022-04-01
//
// * GA exception: the `accounts/projects` child resource does not yet have a
//   non-preview api-version in Azure. This is the single explicit preview
//   exemption in the accelerator and is allow-listed in
//   `infra/.ga-exceptions.yaml`. All other Foundry primitives (model
//   deployments, content filters, RBAC) are on GA api-versions so that the
//   `azd up` flow is truthful about what it provisions.
//
// Enforcement notes:
//   - Local auth is disabled on the account; workloads authenticate via MI.
//   - The model deployment references the RAI policy by name (raiPolicyName)
//     so that content filtering is never bypassable in the portal.
//   - All severities (Hate/Sexual/Violence/Selfharm) are blocked at threshold
//     "Medium" on both prompt and completion.

param projectName string
param location string
param tags object
param rbacPrincipalId string

@description('Principal type for rbacPrincipalId. Root self-host deployments keep the ServicePrincipal default; hosted preview may pass User for an interactive azd operator.')
@allowed([
  'ServicePrincipal'
  'User'
])
param rbacPrincipalType string = 'ServicePrincipal'

@description('Name of the model to deploy (OpenAI format).')
param modelName string = 'gpt-5-mini'

@description('Model version for the deployment.')
param modelVersion string = '2025-08-07'

@description('Deployment name used by the workload (becomes MODEL_DEPLOYMENT_NAME output).')
param modelDeploymentName string = 'gpt-5-mini'

@description('Deployment capacity (TPM in thousands for GlobalStandard SKU).')
param modelCapacity int = 30

@description('Embedding model deployment name. Used for AI Search query-time vectorization (FoundryIQ over a vector index). Bicep provisions the deployment; bootstrap configures the Search index vectorizer to call this deployment over AAD.')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('Embedding model name (OpenAI format).')
param embeddingModelName string = 'text-embedding-3-small'

@description('Embedding model version.')
param embeddingModelVersion string = '1'

@description('Embedding deployment capacity (TPM in thousands for GlobalStandard SKU). 30 is enough for the seed corpus + query-time vectorization at moderate QPS.')
param embeddingModelCapacity int = 30

@description('Extra model deployments beyond the default (object array). Each entry: {slug, deployment_name, model, version, capacity}. Default [] means only the default deployment is provisioned. Derived from the accelerator.yaml models block via loadYamlContent in main.bicep.')
param extraModelDeployments array = []

@description('Default project name inside the Foundry account.')
param foundryProjectName string = 'accelerator-default'

@description('When true, disables public network access on the Foundry account. Actual private endpoints + DNS zones require a pre-existing VNet and are wired via peSubnetId + privateDnsZoneIds (Tier 3); see docs/patterns/azure-ai-landing-zone/README.md.')
param enablePrivateLink bool = false

@description('Tier 3 only. Resource ID of the spoke subnet that hosts the Foundry PE.')
param peSubnetId string = ''

@description('Tier 3 only. Resource IDs of the hub private DNS zones that the Foundry PE needs to register into. An AIServices-kind Foundry account exposes endpoints on THREE DNS suffixes and all three must resolve privately for the shipped runtime (`services.ai.azure.com` project endpoint + `cognitiveservices.azure.com` account endpoint + `openai.azure.com` OpenAI inference). Pass all zone IDs the customer CCoE has provisioned — empty strings are skipped. The PE group is `account` (single sub-resource) but its DNS zone group contains one config per zone so every hostname resolves to the PE IP.')
param privateDnsZoneIds array = []

var deployPrivateEndpoint = !empty(peSubnetId) && !empty(privateDnsZoneIds)

var accountName = 'fdy${take(uniqueString(resourceGroup().id, projectName), 12)}'

// Cognitive Services built-in roles
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'        // Cognitive Services User
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
var aiDeveloperRoleId = '64702f94-c441-49e6-a78b-ef80e0188fee'                  // Azure AI Developer

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Required for the `accounts/projects` child resource. Without this the
    // control plane returns BadRequest: "Project can only created under
    // AIServices Kind account with allowProjectManagement set to true."
    allowProjectManagement: true
    customSubDomainName: accountName
    publicNetworkAccess: enablePrivateLink ? 'Disabled' : 'Enabled'
    disableLocalAuth: true
    networkAcls: {
      defaultAction: enablePrivateLink ? 'Deny' : 'Allow'
    }
  }
}

resource raiPolicy 'Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01' = {
  parent: account
  name: 'accelerator-default-policy'
  properties: {
    basePolicyName: 'Microsoft.Default'
    mode: 'Blocking'
    contentFilters: [
      { name: 'Hate',     severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Hate',     severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Sexual',   severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Sexual',   severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Violence', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Violence', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Selfharm', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Selfharm', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
    ]
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: modelDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    raiPolicyName: raiPolicy.name
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// Embedding deployment for Azure AI Search integrated vectorization.
// Sequenced AFTER the default chat deployment via dependsOn so Foundry's
// provisioning queue doesn't reject concurrent creates on cold capacity
// (same reason as the @batchSize(1) loop below).
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: embeddingDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: embeddingModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [
    modelDeployment
  ]
}

// Extra deployments driven by accelerator.yaml `models:` block.
// `@batchSize(1)` serialises creates inside the loop so Foundry's
// provisioning queue doesn't reject concurrent creates on cold
// capacity. The explicit dependsOn also serialises the whole loop
// behind the default deployment. The `extraModelDeployments` array
// is derived from the manifest at compile time via loadYamlContent
// in main.bicep — Bicep parses accelerator.yaml directly, no Python
// preprocessing required.

@batchSize(1)
resource extraModelDeps 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for dep in extraModelDeployments: {
  parent: account
  name: dep.deployment_name
  sku: {
    name: 'GlobalStandard'
    capacity: dep.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: dep.model
      version: dep.version
    }
    raiPolicyName: raiPolicy.name
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [
    modelDeployment
    embeddingDeployment
  ]
}]

// slug -> deployment_name map. The default deployment is always bound
// to slug 'default'. Agents in accelerator.yaml reference a slug
// (or omit it -> 'default') and src/bootstrap.py resolves here at FastAPI startup.
var defaultSlugMap = {
  default: modelDeployment.name
}
var extrasSlugMap = toObject(
  extraModelDeployments,
  dep => dep.slug,
  dep => dep.deployment_name
)
var modelMap = union(defaultSlugMap, extrasSlugMap)

// Foundry project (preview api-version — see GA exception note at top of file).
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: foundryProjectName
    description: 'Default project for the agentic-ai-solution-accelerator flagship workload.'
  }
}

// RBAC: workload MI can call models and manage agents.
resource oaiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(rbacPrincipalId)) {
  name: guid(account.id, rbacPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: account
  properties: {
    principalId: rbacPrincipalId
    principalType: rbacPrincipalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
  }
}

resource csUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(rbacPrincipalId)) {
  name: guid(account.id, rbacPrincipalId, cognitiveServicesUserRoleId)
  scope: account
  properties: {
    principalId: rbacPrincipalId
    principalType: rbacPrincipalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
  }
}

resource aiDeveloperAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(rbacPrincipalId)) {
  name: guid(project.id, rbacPrincipalId, aiDeveloperRoleId)
  scope: project
  properties: {
    principalId: rbacPrincipalId
    principalType: rbacPrincipalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', aiDeveloperRoleId)
  }
}

// Tier 3: private endpoint + multi-zone DNS group. A single PE on
// `Microsoft.CognitiveServices/accounts` with groupId `account`
// fronts ALL endpoints the runtime uses (account, project, openai);
// the DNS zone group binds one config per zone so every hostname
// (`*.cognitiveservices.azure.com`, `*.services.ai.azure.com`,
// `*.openai.azure.com`) resolves to the PE IP.
resource foundryPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (deployPrivateEndpoint) {
  name: '${account.name}-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${account.name}-plsc'
        properties: {
          privateLinkServiceId: account.id
          groupIds: [ 'account' ]
        }
      }
    ]
  }
}

resource foundryPrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (deployPrivateEndpoint) {
  parent: foundryPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [for (zoneId, i) in privateDnsZoneIds: {
      name: 'zone-${i}'
      properties: {
        privateDnsZoneId: zoneId
      }
    }]
  }
}

output accountName string = account.name
output accountId string = account.id
output accountEndpoint string = account.properties.endpoint
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
output projectName string = project.name
// Project system-assigned MI principal id. Used by main.bicep to grant
// the project access to AI Search (Search Index Data Reader) so the
// FoundryIQ Knowledge Base can resolve documents from the connected
// Search index via the RemoteTool MCP connection.
output projectPrincipalId string = project.identity.principalId
output modelDeploymentName string = modelDeployment.name
output modelName string = modelName
output embeddingDeploymentName string = embeddingDeployment.name
output raiPolicyName string = raiPolicy.name
output modelMap object = modelMap
