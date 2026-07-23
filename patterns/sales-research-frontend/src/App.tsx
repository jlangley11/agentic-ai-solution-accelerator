import { useEffect, useRef, useState } from "react";
import { ResearchForm } from "./components/ResearchForm";
import { StreamingViewer } from "./components/StreamingViewer";
import { ResultPanel } from "./components/ResultPanel";
import { runResearch, RESEARCH_STREAM_URL } from "./services/researchClient";
import type { ResearchBriefing, ResearchRequest, StreamEvent } from "./types/research";
import type { ScenarioMetadata } from "./types/scenario";
import { fetchScenarioMetadata } from "./services/scenarioClient";
import { ScenarioWorkbench } from "./components/ScenarioWorkbench";

export default function App() {
  const [metadata, setMetadata] = useState<ScenarioMetadata | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(true);

  async function loadMetadata() {
    setMetadataLoading(true);
    setMetadataError(null);
    try {
      setMetadata(await fetchScenarioMetadata());
    } catch (error) {
      setMetadata(null);
      setMetadataError((error as Error).message);
    } finally {
      setMetadataLoading(false);
    }
  }

  useEffect(() => {
    void loadMetadata();
  }, []);

  if (metadataLoading) {
    return (
      <div className="app">
        <div className="card" role="status">
          Loading scenario metadata…
        </div>
      </div>
    );
  }
  if (metadataError || !metadata) {
    return (
      <main className="app metadata-failure">
        <section className="card error" role="alert">
          <h1>Scenario metadata is unavailable</h1>
          <p>
            The workbench cannot safely choose a scenario-specific interface
            without <code>/scenario/metadata</code>.
          </p>
          {metadataError && <p className="muted">{metadataError}</p>}
          <button type="button" className="primary" onClick={() => void loadMetadata()}>
            Retry
          </button>
        </section>
      </main>
    );
  }
  if (metadata && metadata.id !== "sales-research") {
    return (
      <div className="app">
        <ScenarioWorkbench metadata={metadata} />
      </div>
    );
  }
  return <SalesResearchApp />;
}

function SalesResearchApp() {
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [briefing, setBriefing] = useState<ResearchBriefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toolWarnings, setToolWarnings] = useState<
    { tool: string; error: string }[]
  >([]);
  const [interruption, setInterruption] = useState<
    { last_seq: number; last_event?: string } | null
  >(null);
  // Per-agent character counters from `chunk` events. Raw unvalidated model
  // text is never retained; counts only drive human-readable progress copy.
  const [workerProgress, setWorkerProgress] = useState<Record<string, number>>({});
  const abortRef = useRef<AbortController | null>(null);

  async function handleSubmit(req: ResearchRequest) {
    setBusy(true);
    setEvents([]);
    setBriefing(null);
    setError(null);
    setToolWarnings([]);
    setInterruption(null);
    setWorkerProgress({});

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await runResearch(req, {
        signal: controller.signal,
        onEvent: (evt) => {
          // Token-stream chunks would drown the event log; route them
          // into a separate per-agent live buffer instead. The
          // StreamingViewer renders a "thinking" panel for any agent
          // that has thoughts but hasn't emitted ``partial`` yet.
          if (evt.type === "chunk") {
            const key = evt.worker_id ?? evt.agent;
            setWorkerProgress((prev) => ({
              ...prev,
              [key]: (prev[key] ?? 0) + evt.delta.length,
            }));
            return;
          }
          // ``stream_interrupted`` is synthesised by the client when
          // the response body EOFs without a terminal ``done`` event.
          // That means an intermediary (Vite dev proxy, ACA ingress,
          // browser fetch, etc.) cut the connection mid-flight. Show
          // an explicit banner so the user sees "this failed" instead
          // of "this finished with partial results".
          if (evt.type === "stream_interrupted") {
            setInterruption({
              last_seq: evt.last_seq,
              last_event: evt.last_event,
            });
            return;
          }
          // ``done`` is the terminal protocol marker. Nothing to render
          // — its absence is what matters (handled above).
          if (evt.type === "done") return;

          setEvents((prev) => [...prev, evt]);
          // ``briefing_ready`` makes the briefing renderable BEFORE
          // any side-effect tools fire, so a HITL/permission failure
          // afterwards no longer wipes the four agents' output.
          // ``final`` carries the same briefing — handle both.
          if (evt.type === "briefing_ready" || evt.type === "final") {
            setBriefing(evt.briefing);
          }
          if (evt.type === "tool_error") {
            setToolWarnings((prev) => [
              ...prev,
              { tool: evt.tool, error: evt.error },
            ]);
          }
          if (evt.type === "error") setError(evt.message);
        },
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setError("Cancelled.");
      } else {
        setError((err as Error).message);
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  // Partials that arrived before the stream died — exposed so the
  // interruption banner can tell the user how far we got.
  const partials = events
    .filter((e): e is Extract<StreamEvent, { type: "partial" }> => e.type === "partial")
    .map((e) => ({ worker_id: e.worker_id, output: e.output }));

  // An agent is "still thinking" if we've seen chunks but no partial yet.
  const completedWorkers = new Set(partials.map((p) => p.worker_id));
  const liveProgress = Object.entries(workerProgress).filter(
    ([agent]) => !completedWorkers.has(agent),
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>Sales Research — reference UI</h1>
        <p className="muted">
          Streaming client for <code>{RESEARCH_STREAM_URL}</code>. Reference
          starter — fork and customise for your customer.
        </p>
      </header>

      <main>
        {/* Collapse form while running OR when results are showing */}
        {busy || briefing ? (
          <details className="card form-collapsed" open={!busy && !briefing}>
            <summary className="form-collapsed-summary">
              <strong>Research request</strong>
              {busy && <span className="muted"> — running…</span>}
              {!busy && briefing && <span className="muted"> — complete</span>}
              {busy && (
                <button
                  type="button"
                  className="cancel-inline"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    handleCancel();
                  }}
                >
                  Cancel
                </button>
              )}
              {!busy && briefing && (
                <button
                  type="button"
                  className="new-research-btn"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setBriefing(null);
                    setEvents([]);
                    setError(null);
                    setToolWarnings([]);
                    setInterruption(null);
                    setWorkerProgress({});
                  }}
                >
                  New research
                </button>
              )}
            </summary>
            <ResearchForm busy={busy} onSubmit={handleSubmit} onCancel={handleCancel} />
          </details>
        ) : (
          <ResearchForm busy={busy} onSubmit={handleSubmit} onCancel={handleCancel} />
        )}
        {error && (
          <div className="card error" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}
        {interruption && !briefing && (
          <div className="card error" role="alert">
            <strong>Stream disconnected before the briefing was ready.</strong>
            <p className="muted">
              The connection was cut by an intermediary after{" "}
              <code>seq={interruption.last_seq}</code>
              {interruption.last_event && (
                <>
                  {" "}
                  (last event: <code>{interruption.last_event}</code>)
                </>
              )}
              . {partials.length > 0
                ? `${partials.length} of 4 worker output(s) arrived before the cut — see them under "Streaming activity" below.`
                : "No worker output arrived before the cut."}
              {" "}This is a transport issue, not a model failure — try again,
              or check the dev proxy / ingress timeouts.
            </p>
          </div>
        )}
        {interruption && briefing && (
          <div className="card warn" role="status">
            <strong>Stream disconnected after the briefing was ready.</strong>
            <p className="muted">
              The briefing below is complete, but the connection was cut at{" "}
              <code>seq={interruption.last_seq}</code> before we could confirm
              completion. Side-effect tool results may be missing.
            </p>
          </div>
        )}
        {toolWarnings.length > 0 && (
          <div className="card warn" role="status">
            <strong>Side-effect tools needed approval — briefing is below.</strong>
            <ul>
              {toolWarnings.map((w, i) => (
                <li key={i}>
                  <code>{w.tool}</code>: {w.error}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(events.length > 0 || busy) && (
          <details className="stream-drawer" open={busy && !briefing}>
            <summary className="stream-drawer-summary">
              <span>Live stream</span>
              {busy && <span className="pulse" />}
              <span className="muted"> ({events.length} events)</span>
            </summary>
            <StreamingViewer
              events={events}
              busy={busy}
              liveProgress={liveProgress}
            />
          </details>
        )}
        <ResultPanel
          briefing={briefing}
          events={events}
          isComplete={!busy && briefing !== null}
          busy={busy}
        />
      </main>

      <footer className="app-footer">
        <span>
          Pattern source:{" "}
          <code>patterns/sales-research-frontend/</code>
        </span>
      </footer>
    </div>
  );
}
