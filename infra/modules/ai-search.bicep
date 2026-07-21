param name string
param location string
param tags object
param rbacPrincipalId string

@description('Principal type for rbacPrincipalId. Root self-host deployments keep the ServicePrincipal default; hosted preview may pass User for an interactive azd operator.')
@allowed([
  'ServicePrincipal'
  'User'
])
param rbacPrincipalType string = 'ServicePrincipal'
param enablePrivateLink bool = false

@description('Tier 3 only. Resource ID of the spoke subnet that hosts the Search PE.')
param peSubnetId string = ''

@description('Tier 3 only. Resource ID of the hub private DNS zone `privatelink.search.windows.net`.')
param privateDnsZoneId string = ''

var deployPrivateEndpoint = !empty(peSubnetId) && !empty(privateDnsZoneId)

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'standard' }
  // System-assigned MI lets the Search service authenticate to Azure
  // OpenAI as itself when query-time AAD vectorizers fire (integrated
  // vectorization). main.bicep grants this principal Cognitive
  // Services OpenAI User on the Foundry account inline.
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    semanticSearch: 'standard'
    publicNetworkAccess: enablePrivateLink ? 'Disabled' : 'Enabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http403'
      }
    }
  }
}

// Search Index Data Contributor + Search Service Contributor.
// Data Contributor is required for src/bootstrap.py (running inside the Container App as the workload MI) to upload seed documents at FastAPI startup
// provision time. Data Reader alone fails the seed step during `azd up`.
var indexDataContributorId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var serviceContributorId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource searchDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(rbacPrincipalId)) {
  name: guid(search.id, rbacPrincipalId, indexDataContributorId)
  scope: search
  properties: {
    principalId: rbacPrincipalId
    principalType: rbacPrincipalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', indexDataContributorId)
  }
}

resource searchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(rbacPrincipalId)) {
  name: guid(search.id, rbacPrincipalId, serviceContributorId)
  scope: search
  properties: {
    principalId: rbacPrincipalId
    principalType: rbacPrincipalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', serviceContributorId)
  }
}

// Tier 3: private endpoint + DNS zone group. See key-vault.bicep for pattern.
resource searchPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (deployPrivateEndpoint) {
  name: '${name}-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${name}-plsc'
        properties: {
          privateLinkServiceId: search.id
          groupIds: [ 'searchService' ]
        }
      }
    ]
  }
}

resource searchPrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (deployPrivateEndpoint) {
  parent: searchPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'default'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output endpoint string = 'https://${search.name}.search.windows.net'
output name string = search.name
output id string = search.id
output principalId string = search.identity.principalId
