# Use-case canvas — Contoso Manufacturing

A one-page scoping instrument for the **pre-workshop** phase of a
partner engagement. This filled sample is fictional and intended for QA
testing of the discovery workflow.

**Engagement slug:** `contoso-supplier-risk`
**Sponsor:** Dana Scully · VP Procurement Operations · dana.scully@contoso.com
**Partner lead:** Alex Morgan · Principal Solution Architect
**Date:** 2026-04-30
**Status:** Approved for workshop

---

## 1. The process in one sentence

**Process:** Procurement risk analysts spend nearly two hours per supplier onboarding review collecting policy evidence, checking supplier records, and drafting risk cases before a sourcing decision can move forward.

## 2. Who does this today, who pays for the change

- **Primary user persona** (the role whose day the agent changes): Procurement risk analyst in Contoso's Global Supplier Management team.
- **Volume** (how many people x how often): 14 analysts process about 45 supplier onboarding or renewal reviews per week today, with seasonal spikes above 70.
- **Budget owner** (who signs the invoice): Priya Shah · CIO, Contoso Manufacturing.
- **Executive sponsor** (who loses sleep if this fails): Dana Scully · VP Procurement Operations.

## 3. The one metric that matters

- **Metric name:** Supplier review cycle time
- **Unit** (minutes, $, %, count, etc.): Minutes from intake submission to analyst-ready recommendation.
- **Baseline today** (actual measurement — not a guess): 110 minutes median across 120 sampled reviews from March 2026.
- **Target** (what makes this worth doing): 18 minutes median by pilot exit, with all factual claims cited.
- **Measurement source** (where the number comes from: system of record, time study, sampled observation, etc.): ServiceNow procurement-risk queue timestamps plus a manual time study run by Procurement Operations.

## 4. Must-not-do guardrails

- The solution must not approve, reject, or suspend a supplier without explicit human approval.
- The solution must not state a supplier compliance status unless the claim is backed by a cited source from approved Contoso systems.
- The solution must not send supplier-facing messages, update ERP records, or create ServiceNow cases without a HITL checkpoint.

## 5. Data the agent can reach

- [x] SharePoint site(s): Procurement policy library, supplier due-diligence playbook, approved category-risk matrix.
- [x] SQL / Synapse database(s): Azure SQL supplier master and onboarding history replica.
- [x] Internal APIs (REST/GraphQL): Dynamics 365 Finance supplier profile API; ServiceNow procurement-risk case API.
- [x] Blob / files: Standard supplier evidence packets uploaded by analysts during intake.
- [x] SaaS systems (CRM, ITSM, HRIS, and related systems): ServiceNow procurement-risk workspace.
- [ ] Web search (bounded allow-list?): Out of scope for v1; no public-web claims.
- [ ] None (ask the sponsor why)

## 6. Side-effects the agent should perform

- Create a draft procurement-risk case in ServiceNow for human review and approval.
- Write a recommended review disposition and evidence summary back to Dynamics 365 Finance supplier onboarding after approval.

## 7. Constraints

- **Data residency:** US
- **Identity provider:** Entra ID
- **Compliance regime:** SOC 2, GDPR supplier-contact handling, SOX procurement controls
- **Tenant topology:** Customer tenant
- **Azure AI Landing Zone tier** (expected): avm
- **Hard deadlines:** Pilot readout due before the FY27 supplier renewal wave planning meeting.

## 8. Expected solution shape (partner hypothesis)

- [x] **supervisor-routing** — multiple specialists + aggregator + HITL. Flagship default. Pick when the task has >1 distinct reasoning step.
- [ ] **single-agent** — one agent + retrieval + 1-2 tools. Pick for narrow, repeated tasks (e.g., triage, summarization).
- [ ] **chat-with-actioning** — conversational UX with tools. Pick when the human drives the workflow and the agent executes.

**Rationale:** The workflow has distinct intake validation, evidence retrieval, risk scoring, case drafting, and side-effect execution steps that need separate validation and telemetry.

## 9. Why we're confident this is worth a workshop

- The current queue is a measurable bottleneck: 45 reviews per week against a renewal-wave demand forecast of 100+ reviews per week.
- Contoso already has the needed source systems and a named sponsor who can approve the HITL policy, KPI targets, and pilot acceptance gates.

---

## Go / no-go gate

Before scheduling the discovery workshop, confirm with the sponsor:

- [x] The process in Section 1 is the same thing everyone in the room thinks we're talking about.
- [x] Section 3 metric + baseline are real numbers, not placeholders.
- [x] Budget is identified.
- [x] The customer can bring the SMEs who do the work today — not just their managers — to the workshop.

**Decision:** Go. Schedule the discovery workshop and use the filled workbook in this folder as the workshop capture.
