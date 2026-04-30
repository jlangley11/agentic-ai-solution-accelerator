# Use-case canvas — `<Customer>`

<!-- Template-fill marker: Replace `<customer-slug>` with the engagement slug (e.g., contoso-q4-research) and `<Customer>` with the customer display name. -->


A one-page scoping instrument for the **pre-workshop** phase of a
partner engagement. Send this to the customer sponsor after the first
scoping call; use the answers to decide whether to schedule the
discovery workshop.

> If the sponsor can't fill this in ~30 minutes of their time, the
> engagement isn't ready for a workshop. Iterate on framing first.

**Engagement slug:** `<customer-slug>`
**Sponsor:** `<name · role · email>`
**Partner lead:** `<your name>`
**Date:** `<YYYY-MM-DD>`
**Status:** Draft / Reviewed with sponsor / Approved for workshop

---

## 1. The process in one sentence

> Write ONE sentence describing the current-state process this
> engagement will change. No "AI", no "agent" in this sentence.
> Example: "Our sales reps spend ~3 hours per account preparing a
> briefing before a discovery call."

**Process:** …

## 2. Who does this today, who pays for the change

- **Primary user persona** (the role whose day the agent changes):
- **Volume** (how many people × how often):
- **Budget owner** (who signs the invoice):
- **Executive sponsor** (who loses sleep if this fails):

## 3. The one metric that matters

Pick **one** primary metric the sponsor will judge the engagement on.
Everything else is secondary. Resist the urge to list five.

- **Metric name:**
- **Unit** (minutes, $, %, count, …):
- **Baseline today** (actual measurement — not a guess):
- **Target** (what makes this worth doing):
- **Measurement source** (where the number comes from: system of
  record, time study, sampled observation, …):

## 4. Must-not-do guardrails

Hard rules the agent must not violate. Compliance, policy, brand, or
customer-promise constraints. Think: "If the agent did X, we would
pull the plug tomorrow."

- …
- …
- …

## 5. Data the agent can reach

What the agent can read from on day 1. Check all that apply and note
the access mechanism.

- [ ] SharePoint site(s): …
- [ ] SQL / Synapse database(s): …
- [ ] Internal APIs (REST/GraphQL): …
- [ ] Blob / files: …
- [ ] SaaS systems (CRM, ITSM, HRIS, …): …
- [ ] Web search (bounded allow-list?): …
- [ ] None (ask the sponsor why)

## 6. Side-effects the agent should perform

What the agent **writes** or **sends** on day 1. List each; every
non-trivial side-effect will be a `src/tools/*.py` module with an
HITL policy per `accelerator.yaml:solution.hitl`.

- …
- …

If the answer is "none" — i.e., the agent only reads and summarizes —
that's fine; note the pattern as **single-agent** in Section 8.

## 7. Constraints

- **Data residency:** US / EU / APAC / custom / no constraint
- **Identity provider:** Entra ID / External ID / other
- **Compliance regime:** SOC 2 / GDPR / HIPAA / PCI / none / other
- **Tenant topology:** Customer tenant / partner-hosted / ISV-hosted
- **Azure AI Landing Zone tier** (expected): standalone / avm /
  alz-integrated — see `docs/patterns/azure-ai-landing-zone/`
- **Hard deadlines:** …

## 8. Expected solution shape (partner hypothesis)

The partner's guess before the workshop validates it. Three shapes
ship in the template; the custom agent `/discover-scenario` will
recommend one after the workshop.

- [ ] **supervisor-routing** — multiple specialists + aggregator +
  HITL. Flagship default. Pick when the task has >1 distinct
  reasoning step.
- [ ] **single-agent** — one agent + retrieval + 1–2 tools. Pick for
  narrow, repeated tasks (e.g., triage, summarization).
- [ ] **chat-with-actioning** — conversational UX with tools. Pick
  when the human drives the workflow and the agent executes.

**Rationale:** …

## 9. Why we're confident this is worth a workshop

Two-sentence answer. If the answer is "the customer asked us to
explore AI" — stop. Come back with a framing that ties to the metric
in Section 3.

- …

---

## Go / no-go gate

Before scheduling the discovery workshop, confirm with the sponsor:

- [ ] The process in Section 1 is the same thing everyone in the room thinks
  we're talking about.
- [ ] Section 3 metric + baseline are real numbers, not placeholders.
- [ ] Budget is identified.
- [ ] The customer can bring the SMEs who do the work today — not
  just their managers — to the workshop.

**If any checkbox is unchecked, do not schedule the workshop yet.**
Use the next scoping call to close the gaps.

---

## Next step

Once the canvas is approved, schedule the workshop and open
`docs/discovery/SOLUTION-BRIEF-GUIDE.md` to run the session. The
workshop fills `docs/discovery/discovery-workbook.csv` live, then
`/discover-scenario` turns the workbook into
`docs/discovery/solution-brief.md`.
