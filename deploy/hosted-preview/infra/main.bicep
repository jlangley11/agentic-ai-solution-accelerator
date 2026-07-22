// Preview-only Foundry Hosted Agents infrastructure.
// Subscription scope matches the microsoft.foundry ejected provider contract.

targetScope = 'subscription'

@description('Azure region for all resources.')
param location string

@description('Name of the resource group to create and deploy resources into.')
@minLength(1)
@maxLength(90)
param resourceGroupName string

@description('Tags applied to all resources.')
param tags object = {}

@description('Foundry deployment surface sharing this slim infrastructure.')
@allowed([
  'foundry-prompt'
  'hosted-preview'
])
param deploymentSurface string = 'hosted-preview'

@description('Optional salt to vary resource names across re-provisions.')
param resourceTokenSalt string = ''

@description('Foundry project name supplied by the microsoft.foundry provider.')
@minLength(3)
@maxLength(32)
param foundryProjectName string

@description('Provider-generated model declarations. Accepted for the ejected contract; accelerator.yaml remains authoritative.')
param deployments array = []

@description('Provider-generated project connections. Accelerator Search and KB connections are declared in the resource module.')
param connections array = []

@description('Object id of the azd operator running provisioning.')
param principalId string = ''

@description('Operator principal type.')
@allowed([
  'ServicePrincipal'
  'User'
])
param principalType string = 'User'

@description('Accepted for microsoft.foundry compatibility. Hosted code deployment does not provision ACR.')
param includeAcr bool = false

@description('Public-only preview workspace compatibility parameter.')
param enableNetworkIsolation bool = false

@description('Public-only preview workspace compatibility parameter.')
param useManagedEgress bool = false

@description('Public-only preview workspace compatibility parameter.')
param vnetId string = ''

@description('Public-only preview workspace compatibility parameter.')
param agentSubnetName string = 'agent-subnet'

@description('Public-only preview workspace compatibility parameter.')
param agentSubnetPrefix string = ''

@description('Public-only preview workspace compatibility parameter.')
param createAgentSubnet bool = false

@description('Public-only preview workspace compatibility parameter.')
param peSubnetName string = 'pe-subnet'

@description('Public-only preview workspace compatibility parameter.')
param peSubnetPrefix string = ''

@description('Public-only preview workspace compatibility parameter.')
param createPESubnet bool = false

@description('Public-only preview workspace compatibility parameter.')
param managedIsolationMode string = ''

@description('Public-only preview workspace compatibility parameter.')
param dnsZonesResourceGroup string = ''

@description('Public-only preview workspace compatibility parameter.')
param dnsZonesSubscription string = ''

// Keep the repository manifest authoritative, exactly like root infra/main.bicep.
var manifest = loadYamlContent('../../../accelerator.yaml')
var modelsBlock = manifest.?models ?? []
var defaultEntries = filter(modelsBlock, m => (m.?default ?? false) == true)
var hasManifestDefault = !empty(defaultEntries)
var defaultModel = hasManifestDefault ? defaultEntries[0] : {
  deployment_name: 'gpt-5-mini'
  model: 'gpt-5-mini'
  version: '2025-08-07'
  capacity: 30
}
var extraModelEntries = filter(modelsBlock, m => (m.?default ?? false) != true)

var providerContract = {
  declaredDeploymentCount: length(deployments)
  declaredConnectionCount: length(connections)
  includeAcr: includeAcr
  networkInputs: {
    enableNetworkIsolation: enableNetworkIsolation
    useManagedEgress: useManagedEgress
    vnetId: vnetId
    agentSubnetName: agentSubnetName
    agentSubnetPrefix: agentSubnetPrefix
    createAgentSubnet: createAgentSubnet
    peSubnetName: peSubnetName
    peSubnetPrefix: peSubnetPrefix
    createPESubnet: createPESubnet
    managedIsolationMode: managedIsolationMode
    dnsZonesResourceGroup: dnsZonesResourceGroup
    dnsZonesSubscription: dnsZonesSubscription
  }
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: union(tags, {
    'hosted-agents': deploymentSurface == 'hosted-preview' ? 'preview' : 'none'
    'deployment-surface': 'deploy/${deploymentSurface}'
  })
}

module resources 'modules/resources.bicep' = {
  name: 'hosted-preview-resources'
  scope: resourceGroup
  params: {
    location: location
    tags: resourceGroup.tags
    resourceTokenSalt: resourceTokenSalt
    foundryProjectName: foundryProjectName
    principalId: principalId
    principalType: principalType
    defaultModel: defaultModel
    extraModelDeployments: extraModelEntries
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_AI_PROJECT_ID string = resources.outputs.AZURE_AI_PROJECT_ID
output AZURE_AI_ACCOUNT_NAME string = resources.outputs.AZURE_AI_ACCOUNT_NAME
output AZURE_AI_PROJECT_NAME string = resources.outputs.AZURE_AI_PROJECT_NAME
output AZURE_OPENAI_ENDPOINT string = resources.outputs.AZURE_OPENAI_ENDPOINT
output FOUNDRY_PROJECT_ENDPOINT string = resources.outputs.FOUNDRY_PROJECT_ENDPOINT
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = ''
output AZURE_CONTAINER_REGISTRY_RESOURCE_ID string = ''
output AZURE_AI_PROJECT_ACR_CONNECTION_NAME string = ''
output AZURE_AI_PROJECT_CONNECTION_NAMES string = resources.outputs.AZURE_AI_PROJECT_CONNECTION_NAMES
output AZURE_FOUNDRY_NETWORK_MODE string = 'none'
output AZURE_FOUNDRY_MANAGED_ISOLATION_MODE string = ''

output AZURE_AI_FOUNDRY_ENDPOINT string = resources.outputs.AZURE_AI_FOUNDRY_ENDPOINT
output AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT string = resources.outputs.AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT
output AZURE_AI_FOUNDRY_ACCOUNT_NAME string = resources.outputs.AZURE_AI_FOUNDRY_ACCOUNT_NAME
output AZURE_AI_FOUNDRY_PROJECT_NAME string = resources.outputs.AZURE_AI_FOUNDRY_PROJECT_NAME
output AZURE_AI_FOUNDRY_OPENAI_ENDPOINT string = resources.outputs.AZURE_AI_FOUNDRY_OPENAI_ENDPOINT
output AZURE_AI_FOUNDRY_MODEL string = resources.outputs.AZURE_AI_FOUNDRY_MODEL
output AZURE_AI_FOUNDRY_MODEL_MAP object = resources.outputs.AZURE_AI_FOUNDRY_MODEL_MAP
output AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT string = resources.outputs.AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT
output AZURE_AI_FOUNDRY_RAI_POLICY string = resources.outputs.AZURE_AI_FOUNDRY_RAI_POLICY
output AZURE_AI_SEARCH_ENDPOINT string = resources.outputs.AZURE_AI_SEARCH_ENDPOINT
output AZURE_AI_SEARCH_RESOURCE_ID string = resources.outputs.AZURE_AI_SEARCH_RESOURCE_ID
output AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME string = resources.outputs.AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME
output AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME string = resources.outputs.AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME
output AZURE_AI_FOUNDRY_KB_NAME string = resources.outputs.AZURE_AI_FOUNDRY_KB_NAME
output APPLICATIONINSIGHTS_CONNECTION_STRING string = resources.outputs.APPLICATIONINSIGHTS_CONNECTION_STRING
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = resources.outputs.AZURE_AI_FOUNDRY_MODEL
output HOSTED_AGENT string = deploymentSurface == 'hosted-preview' ? '1' : '0'
output ENABLE_HOSTED_AGENTS string = deploymentSurface == 'hosted-preview' ? '1' : '0'
output HOSTED_PREVIEW_PROVIDER_CONTRACT object = providerContract
