// ============================================================================
// STUDY-ONLY AVM exemplar — Log Analytics + Application Insights
// (Tier 2 `landing_zone.mode: avm`).
//
// This file is NOT wired into infra/main.bicep. It is a **drop-in
// replacement** for infra/modules/monitor.bicep — same param
// signature, same outputs — so a partner can `cp
// infra/avm-reference/monitor.bicep infra/modules/monitor.bicep`
// during local iteration without touching main.bicep.
//
// Two AVM modules compose the observability plane:
//   - br/public:avm/res/operational-insights/workspace:0.15.0  (LAW)
//   - br/public:avm/res/insights/component:0.7.0               (App Insights)
//
// Both are actively maintained. `ga-sdk-freshness` flags version drift.
// ============================================================================

targetScope = 'resourceGroup'

// --- drop-in signature (matches infra/modules/monitor.bicep) -----------------
param logAnalyticsName string
param appInsightsName string
param location string
param tags object

module law 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: 'law-${logAnalyticsName}'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
    dataRetention: 30
    skuName: 'PerGB2018'
  }
}

module ai 'br/public:avm/res/insights/component:0.7.0' = {
  name: 'ai-${appInsightsName}'
  params: {
    name: appInsightsName
    location: location
    tags: tags
    workspaceResourceId: law.outputs.resourceId
    kind: 'web'
    applicationType: 'web'
    disableLocalAuth: true
  }
}

// ROI-KPIs workbook — auto-deployed (signature parity with the hand-rolled
// monitor module). Hand-rolled here because the AVM workbook module surface is
// thin and would only add indirection for a single resource. See
// docs/customer-runbook.md section 2 for portal-edit / re-provision behavior.
resource roiWorkbook 'Microsoft.Insights/workbooks@2022-04-01' = {
  name: guid(resourceGroup().id, 'roi-kpis', appInsightsName)
  location: location
  tags: tags
  kind: 'shared'
  properties: {
    displayName: 'Agentic AI Accelerator — ROI KPIs'
    serializedData: loadTextContent('../dashboards/roi-kpis.json')
    sourceId: ai.outputs.resourceId
    category: 'workbook'
    version: '1.0'
  }
}

// Signature parity: hand-rolled module exports these outputs.
output logAnalyticsId string = law.outputs.resourceId
output appInsightsConnectionString string = ai.outputs.connectionString
output roiWorkbookId string = roiWorkbook.id
