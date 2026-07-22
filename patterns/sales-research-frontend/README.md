# Accelerator Workbench — Sales Research Reference

A **React + Vite + TypeScript** workbench that preserves the flagship sales
experience while also supporting other scenarios through
`GET /scenario/metadata`. It is self-contained and deployable to Azure Static
Web Apps.

## What this is

A reference UI that wraps the accelerator API in a runnable browser experience.
The sales scenario keeps its tailored form and briefing layouts. Other
scenarios receive a schema-generated form and validated dynamic result panels
from their request/response metadata.

## When to use it

- You need to **demo the API to a customer** without standing up a UI from scratch.
- You want a **baseline to extend** for your customer's bespoke UX.
- You want a working SSE client implementation to learn from when wiring the
  endpoint into the customer's existing apps (Power Apps, internal portals, etc).

## Generic workbench contract

The backend exposes:

- `GET /scenario/metadata` — request/response JSON Schema, endpoint, agents,
  experience metadata, and approval mode.
- `POST /scenario/feedback` — redacted section-level feedback telemetry.
- The scenario's SSE endpoint — generic mode renders only validated `partial`
  events and the final briefing; raw `chunk` output is never shown.

Completed generic runs can be saved to browser `localStorage` as a demo
history. Production deployments should replace this with an approved durable
store and Entra-backed user isolation.

## What this is NOT

- **Not production-ready.** No auth, no state persistence, no multi-user, no
  observability. Adding those is the partner's value-add for the customer.
- **Not a finished product.** Layout is single-column and intentionally plain.
- **Not coupled to the build.** This pattern is deliberately excluded from the
  CI build (it's reference material). Partners decide whether to lift it into
  their own pipeline once they've customised it.

## Run it locally

Requires Node.js 20.19+ or 22.12+ (the supported Vite 8 runtime range).

In one terminal, run the API:

```bash
# from the repo root
uvicorn src.main:app --reload --port 8000
```

In another:

```bash
cd patterns/sales-research-frontend
cp .env.example .env       # leave VITE_API_BASE_URL empty for dev
npm install
npm run dev                # http://localhost:5173
```

The dev server **proxies** `/research/*` and `/healthz` to the local API
(default `http://localhost:8000`, override with `VITE_DEV_API_PROXY`), so the
browser issues same-origin requests and CORS doesn't apply. The form is
pre-filled with sensible defaults so you can click **Run research**
immediately. The streaming viewer shows each SSE event as it arrives; the
result panel renders the final supervisor briefing (with a raw-JSON toggle).

## Deploy to Azure Static Web Apps

```bash
cd patterns/sales-research-frontend
npm install
npm test
npm run build              # outputs to dist/
swa deploy ./dist --env production
```

Set `VITE_API_BASE_URL` at build time to your deployed Container Apps URL.
For a CI-driven flow, see the
[Static Web Apps GitHub Actions guide](https://learn.microsoft.com/azure/static-web-apps/github-actions-workflow).

The browser calls the API directly, so the API has to allow the SWA origin.
The accelerator's API ships with CORS middleware controlled by the
`ALLOWED_ORIGINS` env var (see `src/main.py`).

The Bicep default already includes `http://localhost:5173` (the Vite dev
server) so `npm run dev` against a deployed API works without any extra
wiring during the lab walkthrough. **For a SWA deployment**, override with
your hostname before deploying:

```bash
azd env set ALLOWED_ORIGINS "https://<your-swa>.azurestaticapps.net"
azd provision
```

(That replaces the localhost default. To keep both, pass a comma-separated
list: `"http://localhost:5173,https://<your-swa>.azurestaticapps.net"`.)
`staticwebapp.config.json` also ships an optional `/api/*` rewrite — if
you'd rather front the API through SWA's reverse proxy than expose it to
the browser, edit the `rewrite` to point at your hostname; otherwise delete
that route and rely on the CORS path above.

## How to customize

| To change… | Edit |
|---|---|
| Form fields | `src/components/ResearchForm.tsx` (mirrors `ResearchRequest` in `src/scenarios/sales_research/schema.py`) |
| Default form values | `DEFAULTS` const at the top of `ResearchForm.tsx` |
| Streaming event rendering | `src/components/StreamingViewer.tsx` (`describe()` switch covers every `StreamEvent` type) |
| Final result rendering | `src/components/ResultPanel.tsx` — currently dumps each `ResearchBriefing` field as a section; restyle freely |
| SSE event types | `src/types/research.ts` — keep in sync with `src/workflow/supervisor.py` and the supervisor `transform.py` |
| Streaming client | `src/services/researchClient.ts` — vanilla `fetch` + `ReadableStream` SSE parser, no third-party dependency |
| Generic metadata/client | `src/services/scenarioClient.ts` |
| Generic form | `src/components/DynamicSchemaForm.tsx` |
| Generic validated results | `src/components/DynamicResultPanel.tsx` |
| Look & feel | `src/styles.css` (~150 lines, no framework) |

## What this pattern does *not* try to do

- **Auth.** The accelerator template ships an unauthenticated API; partners
  add auth (Entra ID, easy-auth on Container Apps, App Gateway in front, …)
  before exposing to a real customer. This UI does not assume any auth layer.
- **HITL approval UI.** The supervisor returns `requires_approval` and
  `tool_args`; this pattern surfaces them as a read-only block. The actual
  approval flow (Logic Apps, Teams adaptive card, ticketing system) is partner-wired
  per `docs/patterns/rai/README.md`.
- **State persistence.** Each run is in-memory only. Partners add storage
  (Cosmos, Postgres, browser IndexedDB) if their UX needs it.

## Where to go from here

- See [`patterns/single-agent/README.md`](../single-agent/README.md) and
  [`patterns/chat-with-actioning/README.md`](../chat-with-actioning/README.md)
  for backend pattern variants.
- See [`docs/patterns/architecture/README.md`](../../docs/patterns/architecture/README.md)
  for the full reference architecture (the frontend layer is partner-owned).
