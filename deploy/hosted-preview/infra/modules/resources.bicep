// Resource-group-scoped resources and cross-resource wiring for the preview workspace.

targetScope = 'resourceGroup'

param location string = resourceGroup().location
param tags object = {}
param resourceTokenSalt string = ''
param foundryProjectName string
param principalId string

@allowed([
  'ServicePrincipal'
  'User'
])
param principalType string = 'User'

param defaultModel object
param extraModelDeployments array = []

var resourceToken = empty(resourceTokenSalt)
  ? uniqueString(subscription().id, resourceGroup().id, foundryProjectName, location)
  : uniqueString(subscription().id, resourceGroup().id, foundryProjectName, location, resourceTokenSalt)
var foundryAccountSeed = 'hosted-${foundryProjectName}-${resourceToken}'
var foundryAccountName = 'fdy${take(uniqueString(resourceGroup().id, foundryAccountSeed), 12)}'
var searchName = 'srch-${take(resourceToken, 20)}'
var searchConnectionName = 'accel-search'
var kbMcpConnectionName = 'accel-kb-mcp'
var knowledgeBaseName = 'accel-accounts-kb'

var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var searchIndexDataContribRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var searchServiceContribRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var rbacAdminRoleId = 'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
var searchRolesAssignableExpr = '@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${searchIndexDataReaderRoleId}, ${searchIndexDataContribRoleId}, ${searchServiceContribRoleId}}'

module monitor '../../../../infra/modules/monitor.bicep' = {
  name: 'hosted-preview-monitor'
  params: {
    logAnalyticsName: 'log-${take(resourceToken, 20)}'
    appInsightsName: 'appi-${take(resourceToken, 19)}'
    location: location
    tags: tags
  }
}

module search '../../../../infra/modules/ai-search.bicep' = {
  name: 'hosted-preview-search'
  params: {
    name: searchName
    location: location
    tags: tags
    rbacPrincipalId: principalId
    rbacPrincipalType: principalType
    enablePrivateLink: false
    peSubnetId: ''
    privateDnsZoneId: ''
  }
}

module foundry '../../../../infra/modules/foundry.bicep' = {
  name: 'hosted-preview-foundry'
  params: {
    projectName: foundryAccountSeed
    foundryProjectName: foundryProjectName
    location: location
    tags: tags
    rbacPrincipalId: principalId
    rbacPrincipalType: principalType
    modelName: defaultModel.model
    modelVersion: defaultModel.version
    modelDeploymentName: defaultModel.deployment_name
    modelCapacity: defaultModel.capacity
    extraModelDeployments: extraModelDeployments
    enablePrivateLink: false
    peSubnetId: ''
    privateDnsZoneIds: []
  }
}

resource searchExisting 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchName
}

resource foundryAccountExisting 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryAccountName
}

resource foundryProjectExisting 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: foundryAccountExisting
  name: foundryProjectName
}

resource projectReadsSearchIndex 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchExisting.id, foundryAccountName, 'projectReadsSearchIndex')
  scope: searchExisting
  properties: {
    principalId: foundry.outputs.projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      searchIndexDataReaderRoleId
    )
  }
  dependsOn: [
    search
  ]
}

resource searchCallsAoai 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccountExisting.id, searchName, 'searchCallsAoai')
  scope: foundryAccountExisting
  properties: {
    principalId: search.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveServicesOpenAIUserRoleId
    )
  }
  dependsOn: [
    foundry
  ]
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
  parent: foundryProjectExisting
  name: searchConnectionName
  properties: {
    authType: 'AAD'
    category: 'CognitiveSearch'
    target: search.outputs.endpoint
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.outputs.id
      Location: location
    }
  }
  dependsOn: [
    projectReadsSearchIndex
  ]
}

resource kbMcpConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
  parent: foundryProjectExisting
  name: kbMcpConnectionName
  properties: {
    authType: 'ProjectManagedIdentity'
    category: 'RemoteTool'
    target: '${search.outputs.endpoint}/knowledgebases/${knowledgeBaseName}/mcp?api-version=2025-11-01-preview'
    isSharedToAll: true
    audience: 'https://search.azure.com/'
    metadata: {
      ApiType: 'Azure'
    }
  }
  dependsOn: [
    searchConnection
  ]
}

resource operatorAssignsSearchRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(searchExisting.id, principalId, 'hostedOperatorAssignsSearchRoles')
  scope: searchExisting
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      rbacAdminRoleId
    )
    description: 'Hosted preview provisioner may grant Foundry prompt-agent identities only the accelerator Search roles.'
    conditionVersion: '2.0'
    condition: '((!(ActionMatches{\'Microsoft.Authorization/roleAssignments/write\'})) OR (${searchRolesAssignableExpr})) AND ((!(ActionMatches{\'Microsoft.Authorization/roleAssignments/delete\'})) OR (${searchRolesAssignableExpr}))'
  }
  dependsOn: [
    search
  ]
}

output AZURE_AI_PROJECT_ID string = foundryProjectExisting.id
output AZURE_AI_ACCOUNT_NAME string = foundry.outputs.accountName
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_OPENAI_ENDPOINT string = 'https://${foundry.outputs.accountName}.openai.azure.com/'
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_AI_PROJECT_CONNECTION_NAMES string = join([
  searchConnection.name
  kbMcpConnection.name
], ',')

output AZURE_AI_FOUNDRY_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT string = foundry.outputs.accountEndpoint
output AZURE_AI_FOUNDRY_ACCOUNT_NAME string = foundry.outputs.accountName
output AZURE_AI_FOUNDRY_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_AI_FOUNDRY_OPENAI_ENDPOINT string = 'https://${foundry.outputs.accountName}.openai.azure.com'
output AZURE_AI_FOUNDRY_MODEL string = foundry.outputs.modelDeploymentName
output AZURE_AI_FOUNDRY_MODEL_MAP object = foundry.outputs.modelMap
output AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT string = foundry.outputs.embeddingDeploymentName
output AZURE_AI_FOUNDRY_RAI_POLICY string = foundry.outputs.raiPolicyName
output AZURE_AI_SEARCH_ENDPOINT string = search.outputs.endpoint
output AZURE_AI_SEARCH_RESOURCE_ID string = search.outputs.id
output AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME string = searchConnection.name
output AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME string = kbMcpConnection.name
output AZURE_AI_FOUNDRY_KB_NAME string = knowledgeBaseName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitor.outputs.appInsightsConnectionString
