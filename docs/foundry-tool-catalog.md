# Foundry tool catalog

> **Purpose.** Help the partner decide **which Foundry Agent Service
> tool** to attach to an agent for a given customer workload. This doc
> is a **when-to-use decision aid**, not a feature datasheet —
> authoritative status, regions, and pricing live on Microsoft Learn
> and drift faster than this repo's commit cadence.

Run `accel design` before selecting tools. Prompt agents and Hosted agents are
the Agent Service types; workflow/supervisor are orchestration patterns. Tool
and runtime requirements are Architecture Advisor inputs, not after-the-fact
deployment choices.

**Authoritative references (check these before a proposal):**

- Foundry Agent Service — tool catalog: <https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog>
- Foundry Agent Service — overview: <https://learn.microsoft.com/azure/foundry/agents/overview>
- Pricing (model + Agent Service + Search + Grounding): <https://azure.microsoft.com/pricing/details/ai-foundry/>

> **Do NOT trust the `Status at commit` column below for a customer proposal.** Look it up on Microsoft Learn every time. The column is the author's snapshot — it tells you which tools existed when this doc was written, nothing more.

---

## What this accelerator currently wires

Be clear about the baseline before picking tools:

- **Agent creation (`src/bootstrap.py`, runs at FastAPI startup):** creates each Foundry agent with **model + instructions + MCPTool** for retrieval agents. For agents with `retrieval.mode: foundry_tool`, bootstrap creates a Knowledge Source + Knowledge Base on AI Search, then wires an MCPTool pointing at the Bicep-provisioned RemoteTool MCP connection. AI Search retrieval shows under the agent's **Knowledge** section in the Foundry portal.
- **Flagship orchestration (`src/scenarios/sales_research/workflow.py`):** a Python-side `SupervisorDAG` invokes each Foundry agent independently by `agent_name` and composes their outputs. It is **not** the Foundry `Connected Agents` feature.
- **Grounding (retrieval agents):** handled server-side by the FoundryIQ Knowledge Base via MCPTool. For non-retrieval agents, no grounding is applied.
- **Side-effect tools (`src/tools/`):** `crm_read_account`, `crm_write_contact`, `send_email`, `web_search` are **local Python stubs** executed by the workflow after the supervisor decides they're needed. They are HITL-gated (see `src/accelerator_baseline/hitl.py`) but they are **not** Foundry Azure Functions tools.

!!! note "Two different MCP surfaces"
    Foundry agents use an `MCPTool` to reach the FoundryIQ Knowledge Base.
    Coding-agent clients may separately use the local `accel-mcp` stdio server
    to call lifecycle/status/preview/apply operations. `accel-mcp` is a delivery
    interface; it is not attached to the deployed customer agent.

**Why this matters for the catalog.** When the partner wants to attach
a *real* Foundry tool (File Search, Bing grounding, Code Interpreter,
OpenAPI, MCP, etc.), the current path is **one of**:

1. Record the governed tool intent in
   `scenario.agents[].catalog_tools[]`, attach the catalog tool in the
   **Foundry portal**, and verify it after deployment. Shared provisioning
   preserves non-managed existing tools when it refreshes the KB tool.
2. If the engagement requires deterministic automatic attachment, extend
   `src/provisioning.py` to resolve the manifest declaration and add
   provisioning/readback tests. Do not create a parallel runtime client path.

There is no generic catalog-tool resolver for path 2 yet. Portal attachment is
therefore an explicit, documented environment action; the manifest remains the
reviewed intent and handover record.

---

## Tool selection — decision cheat sheet

Use this **before** looking up the detailed catalog below.

| Need                                                            | Pick this first                          | Why                                                                    |
|-----------------------------------------------------------------|------------------------------------------|------------------------------------------------------------------------|
| Answer from a **small set of customer-uploaded docs** on a thread | File Search                              | Foundry-managed vector store; no infra to provision                   |
| Answer from a **curated enterprise corpus** (hybrid / semantic) | Azure AI Search                          | Scales, ACL-aware, semantic ranker                                     |
| **Public web** answer with citations                            | Web Search (Foundry built-in)            | GA starting point; simpler than Bing resource provisioning             |
| **Public web** with Bing-specific parameters (market, freshness) | Grounding with Bing Search               | Advanced option when Web Search isn't enough                           |
| **Python** for math / tables / charts                           | Code Interpreter                         | Sandboxed Python; **no network egress** — set expectation              |
| Call a **third-party REST API** via OpenAPI                     | OpenAPI tool                             | Declarative, per-op auth schemes                                       |
| Custom **per-call code** in customer tenant                     | Azure Functions tool (queue-based)       | MI-authenticated; durable                                              |
| Access a **tool exposed over MCP**                              | MCP tool                                 | Standard for tool servers; customer-hosted                              |
| Read from **SharePoint Online** for grounding                   | SharePoint (M365 Copilot Retrieval API)  | Preview — OBO user auth, same-tenant only; read/retrieval only         |
| Query **Fabric** via a published Fabric data agent              | Microsoft Fabric tool                    | Preview — OBO user auth, service principal not supported               |
| **Agent-to-agent** call to a **remote A2A endpoint**            | A2A tool                                 | Preview — partner/customer hosts an A2A-compatible agent; not the same-project "Connected Agents" concept |

---

## Catalog

Status legend:
- **GA at commit** — generally available on Microsoft Learn when this doc was written.
- **Preview at commit** — public preview when this doc was written.
- **Check Learn** — surface is evolving fast; verify before commit.

Each row links to Microsoft Learn as the authoritative source.

### Knowledge tools

| Tool                           | Status at commit | One-liner                                                                 | Pick when…                                                    | Avoid when…                                                      | Key prereq                                                                                              | Docs |
|--------------------------------|:----------------:|---------------------------------------------------------------------------|---------------------------------------------------------------|-------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|:-:|
| **File Search**                | GA at commit     | Agent/thread-scoped vector store over Files API uploads                   | Per-thread or per-agent corpora; no infra to provision        | Multi-tenant corpora; > ~10k docs; ACL / semantic ranking needs  | Nothing beyond Foundry project; files via `files.upload`                                                | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search) |
| **Azure AI Search**            | GA at commit     | Agent calls a pre-provisioned Search index (vector / hybrid / semantic)   | Curated enterprise corpora; ACL-aware; large scale            | Small per-thread files (use File Search)                         | Search service + index pre-provisioned. Keyless auth requires **Search Index Data Contributor** **and** **Search Service Contributor** on the project MI | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search) |
| **Web Search**                 | GA at commit     | Foundry-managed public-web grounding                                      | Default pick for "cite the public web"                        | Data that must stay in-tenant                                    | Nothing beyond Foundry project                                                                          | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/web-search) |
| **Grounding with Bing Search** | GA at commit     | Bing-specific web grounding with market / freshness / safe-search controls | Need Bing-specific parameters Web Search doesn't expose       | Web Search already meets the need (simpler; no extra resource)  | Separate **Grounding with Bing Search** resource + connection in Foundry                                 | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/bing-tools) |
| **SharePoint**                 | Preview at commit | **Retrieval only** — read SharePoint content for grounding via M365 Copilot Retrieval API (OBO) | Customer knowledge base lives in SharePoint Online             | Need SharePoint writes (not supported by this tool); multi-tenant scenarios | M365 Copilot license or PAYG retrieval; **Azure AI User** on project; **READ** on the site; same-tenant OBO user auth (no SP) | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/sharepoint) |
| **Microsoft Fabric**           | Preview at commit | Query a published Fabric data agent from the Foundry agent               | Customer analytical data on Fabric OneLake with a data agent  | Service-principal auth required (not supported by this tool)    | Published Fabric data agent; **Azure AI User** on project; **READ** on data agent + underlying sources; OBO user auth | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric) |

### Action tools

| Tool                          | Status at commit | One-liner                                                                        | Pick when…                                                    | Avoid when…                                                   | Key prereq                                                                                 | Docs |
|-------------------------------|:----------------:|----------------------------------------------------------------------------------|---------------------------------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------|:-:|
| **Code Interpreter**          | GA at commit     | Sandboxed Python with file IO and matplotlib; **no outbound network**            | Math, CSV/XLSX wrangling, chart generation                    | Needs network, long-running compute, GPU, custom packages from private feeds | Nothing beyond Foundry project                                                             | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/code-interpreter) |
| **Custom Code Interpreter**   | Preview at commit | Code Interpreter variant with BYO packages / custom runtime                      | Need custom libraries / language version the built-in doesn't ship | Built-in Code Interpreter covers the workload (simpler)           | Preview surface — verify regional availability                                              | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/custom-code-interpreter) |
| **Function calling**          | GA at commit     | Model emits a structured call; caller executes it locally                         | Tight loop tools where the calling process owns execution     | You want Foundry to invoke the function for you (use Azure Functions tool) | Nothing — tool is a JSON schema the caller handles                                          | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/function-calling) |
| **Azure Functions tool**      | GA at commit     | Queue-based `AzureFunctionTool` — Foundry invokes an Azure Function via Storage queues | Customer-hosted custom action code with managed identity    | Low-latency synchronous path (queue adds latency)             | Function App (queue-triggered) + MI; Storage queues for req/resp; standard-setup project    | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-functions) |
| **OpenAPI tool**              | GA at commit     | Agent invokes operations described by an OpenAPI 3.0 spec                        | Third-party SaaS APIs; Graph; any well-described REST API    | Streaming/binary APIs; auth flows outside OpenAPI security schemes | OpenAPI spec + connection (API key / Entra / MI)                                           | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/openapi) |
| **MCP tool**                  | Check Learn      | Connect to a **Model Context Protocol** server                                   | Partner / customer ships tools over MCP                      | Customer hasn't adopted MCP; prefer OpenAPI                    | Reachable MCP server; connection in Foundry                                                | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol) |
| **Image Generation**          | Preview at commit | Agent generates images via a deployed image model                                | Need in-line images in the agent response                    | No image-capable model in the project; cost-sensitive workloads | Image model deployment in the project                                                       | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/image-generation) |
| **Computer Use**              | Preview at commit | Agent controls a remote desktop / browser-like environment                       | UI automation scenarios where Browser Automation isn't enough | Customer has an API; early preview — high failure modes        | Preview surface — verify regional availability                                              | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/computer-use) |
| **Browser Automation**        | Preview at commit | Agent drives a headless browser session                                          | Web UIs without APIs; form-fill / scrape-from-UI scenarios    | Customer has an API; scale or cost sensitive workloads         | Preview surface — verify regional availability                                              | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/browser-automation) |
| **A2A (Agent-to-Agent)**      | Preview at commit | Agent calls a **remote A2A-compatible endpoint** hosted by partner / customer    | Typed hand-off to an external agent exposing the A2A protocol | Orchestrating agents **inside one Foundry project** (use the supervisor pattern externally — see `src/workflow/`); target doesn't expose an A2A endpoint | Remote A2A endpoint reachable from Foundry; connection wired per A2A docs                    | [Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/agent-to-agent) |
| **Toolbox / Connectors**      | Check Learn      | First-party connectors grouped under Foundry's Tools surface                     | The specific connector exists and matches the workload        | Anything niche — verify per-connector availability             | Per-connector; varies                                                                      | [Learn](https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog) |

> **No Logic Apps row.** At commit time, the Foundry Agent Service
> does not ship a dedicated GA built-in "Logic App tool" in the
> catalog. Use the **OpenAPI tool** pointed at a Logic App HTTP
> trigger, or call the Logic App from a Function invoked by the
> **Azure Functions tool**. Re-check Learn before committing — this is
> the surface most likely to change.

---

## Guidance for partners

### When to use which knowledge path

```
Is the corpus per-thread / per-user?
├─ yes  → File Search
└─ no   → Is it curated & pre-indexed?
          ├─ yes → Azure AI Search
          └─ no  → Web Search (add Bing Grounding only if Bing-specific params are needed)
```

### When to add Foundry tools vs orchestrate in Python

This accelerator defaults to **orchestrate in Python** (supervisor DAG
+ local stubs) because the flagship scenario wants typed results,
HITL approval gates, and evals against deterministic transforms.
Foundry tools are easier to wire when:

- The operation is read-only (for example SharePoint or Search retrieval).
- The tool is a **purely knowledge-grounding** step (File Search / AI Search / Web Search).
- You're happy for the Foundry Agent Service to own tool retries + telemetry.

Keep the Python-side pattern when:

- The tool writes to a system of record (CRM, email, finance). HITL gating in Python gives you a single approval surface and deterministic evals.
- You need to compose multiple tool calls into a single typed result before returning to the caller.
- Your evals exercise the tool call shape (the accelerator's `evals/quality` cases do).

### What to watch out for

- **Code Interpreter has no network egress.** Customers often assume "Python means it can `requests.get()`." Set expectations.
- **Grounding with Bing** exposes customer queries to the public web. Data protection officers in regulated workloads will veto it. Raise it during `/discover-scenario`.
- **SharePoint** uses the **M365 Copilot Retrieval API** with **OBO user auth** — service-principal auth isn't supported. A **signed-in user** in the calling tenant is required.
- **Fabric** integrates with a **published Fabric data agent** using **OBO user auth** — service-principal auth isn't supported. A **signed-in user** with `READ` on the data agent and its underlying sources is required. Note: this is *not* the M365 Copilot Retrieval API — it's Fabric's own data-agent surface.
- Neither tool is suitable for headless batch scenarios.
- **Preview tools** (SharePoint, Fabric, Browser Automation) can change their contract. Don't bake a preview tool into a production customer SOW without preview-SLA acceptance.
- **Logic Apps** are reachable today via OpenAPI or Azure Functions, not as a first-party tool. If the customer expects a native "Logic App tool," educate them.

---

## Cost-awareness

Tool costs in this catalog are intentionally not reproduced — they
drift. Price every proposal off the live pages:

- Foundry Agent Service: <https://azure.microsoft.com/pricing/details/ai-foundry/>
- Azure AI Search: <https://azure.microsoft.com/pricing/details/search/>
- Grounding with Bing Search: resource-specific — see the Foundry agent tools docs linked above.
- Azure Functions / Logic Apps: per standard Azure pricing.

The ROI hypothesis in `docs/discovery/solution-brief.md` Section 6 should
reflect the tools actually attached at deploy time.

---

## Change policy for this catalog

Adding or updating a tool row:

1. Verify GA vs Preview on Microsoft Learn **at commit time** — cite the exact Learn URL in the `Docs` column.
2. Don't promote a tool from Preview to GA without a link to the GA announcement.
3. Every tool gets a **Pick when…** **and** an **Avoid when…** cell — partners need both sides.
4. Don't copy prices or hard region lists into the doc. Link the authoritative page.
5. If the Foundry catalog adds a tool this repo should wire automatically (e.g. AI Search via manifest), update `src/bootstrap.py` and `accelerator.yaml` first — then this doc.
