# Solution Brief — Contoso Manufacturing

> This sample is fictional and intended for QA testing of the accelerator discovery flow. It is a completed engagement brief with all required fields filled.

**Engagement:** `contoso-supplier-risk`
**Status:** Reviewed
**Last updated:** `2026-04-30`

---

## 1. Business context
- **Industry / segment:** Industrial manufacturing and distribution; enterprise.
- **Customer name + size:** Contoso Manufacturing, Inc. · enterprise · 18,000 employees · global procurement operations.
- **Executive sponsor:** Dana Scully · VP Procurement Operations · dana.scully@contoso.com.
- **Decision maker:** Priya Shah · CIO · priya.shah@contoso.com, with approval from Marco Silva · CISO · marco.silva@contoso.com.
- **Problem statement (one sentence):** Procurement risk analysts spend nearly two hours per supplier onboarding review collecting policy evidence, checking supplier records, and drafting risk cases before a sourcing decision can move forward.
- **In scope:**
  - Supplier onboarding and renewal risk intake for US-based procurement teams.
  - Evidence retrieval from approved Contoso SharePoint, Azure SQL, Dynamics 365 Finance, ServiceNow, and uploaded evidence packets.
  - Draft risk recommendation, missing-information summary, and approval-ready ServiceNow case.
  - Human approval before any ServiceNow or Dynamics 365 write.
- **Out of scope (explicit):**
  - Final supplier approval, rejection, suspension, or payment release.
  - Public-web or unsanctioned third-party risk lookups.
  - Contract negotiation, pricing optimization, and sourcing strategy recommendations.
  - Autonomous supplier-facing communications.

## 2. Target users & journeys
- **Primary persona:** Procurement risk analyst · monitors ServiceNow intake queues, reviews supplier master data in Dynamics 365 Finance, checks policy evidence in SharePoint, and prepares onboarding recommendations for category managers.
- **Secondary persona (if any):** Category manager · reviews the analyst recommendation, asks follow-up questions, and approves or rejects the next action.
- **Top 3 user journeys:**
  1. An analyst submits a supplier review request with supplier ID, category, country, spend band, and review reason; the solution returns an evidence-backed risk brief and missing-information list.
  2. The analyst reviews cited evidence, adjusts the recommendation if needed, and approves creation of a ServiceNow procurement-risk case.
  3. After HITL approval, the solution writes the approved recommendation and evidence summary to Dynamics 365 Finance supplier onboarding notes.

## 3. Success criteria (measurable)
| Metric | Current | Target | How measured |
|---|---:|---:|---|
| Time per task | 110 minutes median supplier review cycle time | 18 minutes median supplier review cycle time | ServiceNow queue timestamps plus App Insights `supplier_review_cycle_time` event |
| Volume / throughput | 45 completed reviews per week | 130 completed reviews per week | ServiceNow completed-case count by week |
| Quality bar | 72% reviewer agreement on sampled recommendations | >= 92% reviewer agreement on 60 sampled pilot cases; 0 critical audit misses | Blind review by Procurement Operations and Internal Audit |

**Must-not-do guardrails:**
- Must not approve, reject, or suspend a supplier without explicit human approval.
- Must not present a factual compliance, sanctions, or policy claim without a citation from an approved source.
- Must not send supplier-facing messages, update ERP records, or create ServiceNow cases without a HITL checkpoint.

## 4. ROI hypothesis
- **Baseline cost of status quo:** 14 FTE x $145,000 fully loaded annual cost x 60% time on supplier review = $1,218,000 annual manual cost.
- **Target savings ($/yr):** $708,912 net annual impact after estimated Azure run cost and agent-call cost.
- **Payback target:** <= 4 months; ROI workbook model shows approximately 3.0 months against a $180,000 implementation-cost assumption.
- **KPIs to instrument** (these become telemetry events in `src/accelerator_baseline/telemetry.py` and charts in `infra/dashboards/roi-kpis.json`):

| KPI event name | Type | Baseline | Target |
|---|---|---:|---:|
| `supplier_review_cycle_time` | duration_ms | 6600000 | 1080000 |
| `autonomous_triage_coverage` | ratio | 0.00 | 0.72 |
| `hitl_approval_rate` | ratio | 1.00 | 0.88 |

## 5. Solution shape
- **Pattern:** supervisor-routing.
- **Rationale:** The workflow has separable intake validation, evidence retrieval, risk scoring, case drafting, and side-effect execution responsibilities. A supervisor can route to specialist workers, aggregate evidence, and emit a decision record that explains which workers were invoked and why.
- **Grounding sources:** SharePoint procurement policy library; Azure SQL supplier master and onboarding history replica; Dynamics 365 Finance supplier profile API; ServiceNow procurement-risk case API; analyst-uploaded evidence packets in blob storage.
- **Side-effect tools (list every one):**

  | Tool name | External system | Operation | Reversible? | HITL policy |
  |---|---|---|---|---|
  | `create_supplier_risk_case` | ServiceNow procurement-risk workspace | Create a draft procurement-risk case with cited evidence and recommended next action | Yes; case can be closed as void before workflow execution | required |
  | `update_supplier_review_status` | Dynamics 365 Finance supplier onboarding | Write approved recommendation, confidence, and evidence summary to supplier onboarding notes | Yes; audited correction entry can supersede prior note | required |

- **Out-of-scope tools (explicit):**
  - No supplier approval, rejection, suspension, or payment-release write.
  - No supplier-facing email or Teams message in v1.
  - No public-web search or third-party sanctions lookup in v1.
  - No contract-system or sourcing-event write.

## 5b. UX shape
- **`ux_shape`:** Structured form + report.
- **Rationale (one line):** Analysts need a repeatable intake form and a reviewable evidence report before approving any write-back.

## 5c. UX inputs
*Filled only when `ux_shape` is `Structured form + report`. Each row should match a field in `src/scenarios/<pkg>/schema.py` (`ScenarioRequest`).*

| Field | Type | Description | Required |
|---|---|---|---|
| `supplier_name` | text | Display name of the supplier under review. | yes |
| `supplier_id` | text | Contoso supplier master identifier from Dynamics 365 Finance. | yes |
| `review_reason` | select | Onboarding, renewal, spend increase, country risk change, or policy exception. | yes |
| `category` | select | Procurement category used to apply the category-risk matrix. | yes |
| `country` | text | Supplier operating country or primary risk jurisdiction. | yes |
| `annual_spend_usd` | number | Expected or current annual spend in USD. | yes |
| `due_date` | date | Date by which Procurement Operations needs the recommendation. | yes |
| `requested_by` | text | Analyst or category manager requesting the review. | yes |
| `evidence_packet_uri` | url | Optional URI for uploaded supplier documents or intake attachments. | no |

## 5d. UX output sections
*Filled only when `ux_shape` is `Structured form + report`. Each section is a panel rendered by the result UI; `Source agent` is the worker whose output populates it (or `supervisor` if composed).*

| Section | Content | Source agent |
|---|---|---|
| Intake Summary | Supplier identity, review reason, category, country, spend band, due date, and missing required inputs. | `intake_validator` |
| Evidence Pack | Cited source snippets from SharePoint, Azure SQL, Dynamics 365 Finance, ServiceNow, and uploaded evidence. | `evidence_retriever` |
| Risk Scorecard | Risk factors, confidence, rationale, and policy references. | `risk_scorer` |
| Recommended Next Actions | Draft recommendation, HITL decision prompt, and side-effect preview. | `case_drafter` |
| Audit Trail | Supervisor decision record naming invoked workers, confidence, citations, and HITL checkpoint outcomes. | `supervisor` |

## 6. Constraints & risks
- **Data residency:** US.
- **Identity:** Entra ID.
- **Compliance regime:** SOC 2, GDPR supplier-contact handling, SOX procurement controls.
- **Azure AI Landing Zone tier:** avm; private endpoints required for Key Vault, AI Search, Container Apps, and monitoring data paths.
- **RAI risks (3-5 specific to this scenario; become redteam cases):**
  1. The solution fabricates a supplier compliance or sanctions status that is not present in an approved source.
  2. The solution recommends approving a supplier despite missing mandatory evidence.
  3. The solution leaks supplier contact details or commercially sensitive spend data into an unauthorized output.
  4. The solution bypasses or weakens HITL for ServiceNow or Dynamics 365 write-back.
  5. The solution over-weights stale onboarding history and fails to cite the current policy matrix.

## 7. Acceptance evals
| Gate | Threshold | Wired to |
|---|---:|---|
| Quality (golden agreement) | >= 0.90 average agreement on supplier-risk golden cases | `evals/quality/golden_cases.jsonl` |
| Groundedness | >= 0.92 on RAG cases; every factual risk claim has at least one approved-source citation | `evals/quality/` |
| Safety (redteam) | must pass; zero successful XPIA, jailbreak, or HITL-bypass cases | `evals/redteam/` |
| Latency (P50 ms / P95 ms) | 45000 / 120000 | App Insights |
| Cost per call ($) | <= 0.42 | cost attribution telemetry |

---

**Next step:** use this brief as the completed discovery output for QA, then run `/scaffold-from-brief` in a new session if the test needs to materialize the Contoso scenario.
