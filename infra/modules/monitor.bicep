param logAnalyticsName string
param appInsightsName string
param location string
param tags object

resource la 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: la.id
    IngestionMode: 'LogAnalytics'
  }
}

// ROI-KPIs workbook — auto-deployed so partners don't paste-install via the
// portal. The portal copy stays editable; the next ``azd provision`` overwrites
// it from infra/dashboards/roi-kpis.json (source of truth, same pattern as the
// content-filter policy on Foundry). See docs/customer-runbook.md section 2.
resource roiWorkbook 'Microsoft.Insights/workbooks@2022-04-01' = {
  name: guid(resourceGroup().id, 'roi-kpis', appInsightsName)
  location: location
  tags: tags
  kind: 'shared'
  properties: {
    displayName: 'Agentic AI Accelerator — ROI KPIs'
    serializedData: loadTextContent('../dashboards/roi-kpis.json')
    sourceId: ai.id
    category: 'workbook'
    version: '1.0'
  }
}

output appInsightsConnectionString string = ai.properties.ConnectionString
output logAnalyticsId string = la.id
output roiWorkbookId string = roiWorkbook.id
