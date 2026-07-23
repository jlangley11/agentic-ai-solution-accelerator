import { useMemo, useRef, useState } from "react";
import { runScenario } from "../services/scenarioClient";
import type {
  GenericStreamEvent,
  ScenarioMetadata,
  WorkbenchHistoryItem,
} from "../types/scenario";
import { DynamicResultPanel } from "./DynamicResultPanel";
import { DynamicSchemaForm } from "./DynamicSchemaForm";

interface Props {
  metadata: ScenarioMetadata;
}

function historyKey(scenarioId: string): string {
  return `accelerator-workbench-history:${scenarioId}`;
}

function readHistory(scenarioId: string): WorkbenchHistoryItem[] {
  try {
    const value = JSON.parse(localStorage.getItem(historyKey(scenarioId)) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is WorkbenchHistoryItem => {
      if (typeof item !== "object" || item === null || Array.isArray(item)) return false;
      const candidate = item as Record<string, unknown>;
      return (
        typeof candidate.id === "string"
        && typeof candidate.createdAt === "string"
        && Number.isFinite(Date.parse(candidate.createdAt))
        && typeof candidate.request === "object"
        && candidate.request !== null
        && !Array.isArray(candidate.request)
        && typeof candidate.briefing === "object"
        && candidate.briefing !== null
        && !Array.isArray(candidate.briefing)
      );
    }).slice(0, 20);
  } catch {
    return [];
  }
}

function displayTag(value: string): string {
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function ScenarioWorkbench({ metadata }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<GenericStreamEvent[]>([]);
  const [partials, setPartials] = useState<Record<string, unknown>>({});
  const [briefing, setBriefing] = useState<Record<string, unknown> | null>(null);
  const [request, setRequest] = useState<Record<string, unknown>>({});
  const [runId, setRunId] = useState<string>(() => crypto.randomUUID());
  const [history, setHistory] = useState(() => readHistory(metadata.id));
  const abort = useRef<AbortController | null>(null);

  const pendingApprovals = useMemo(
    () =>
      events
        .filter(
          (
            event,
          ): event is Extract<
            GenericStreamEvent,
            { type: "tool_pending_approval" }
          > => event.type === "tool_pending_approval",
        )
        .map((event) => ({ tool: event.tool, args: event.args })),
    [events],
  );
  const warnings = useMemo(
    () =>
      events.flatMap((event) => {
        if (event.type === "tool_error") {
          return [`Tool ${event.tool} failed: ${event.error}`];
        }
        if (event.type === "tool_skipped") {
          return [`Tool ${event.tool} was skipped: ${event.reason}`];
        }
        if (event.type === "worker_skipped") {
          return [
            `Worker ${event.worker_id} was skipped${
              event.error ? `: ${event.error}` : "."
            }`,
          ];
        }
        return [];
      }),
    [events],
  );
  const currentRunSaved = history.some((item) => item.id === runId);

  async function submit(nextRequest: Record<string, unknown>) {
    const nextRunId = crypto.randomUUID();
    setRunId(nextRunId);
    setRequest(nextRequest);
    setBusy(true);
    setError(null);
    setEvents([]);
    setPartials({});
    setBriefing(null);
    const controller = new AbortController();
    abort.current = controller;
    try {
      await runScenario(metadata.endpoint_path, nextRequest, {
        signal: controller.signal,
        onEvent: (event) => {
          if (event.type === "chunk" || event.type === "done") return;
          setEvents((current) => [...current, event]);
          if (event.type === "partial") {
            if (metadata.stream_contract.validated_partial_event !== "partial") {
              return;
            }
            setPartials((current) => {
              if (
                typeof event.output === "object"
                && event.output !== null
                && !Array.isArray(event.output)
              ) {
                return {
                  ...current,
                  ...(event.output as Record<string, unknown>),
                };
              }
              return { ...current, [event.worker_id]: event.output };
            });
          }
          if (event.type === "briefing_ready" || event.type === "final") {
            setBriefing(event.briefing);
          }
          if (event.type === "error") setError(event.message);
          if (event.type === "stream_interrupted") {
            setError("The stream ended before the terminal event arrived.");
          }
        },
      });
    } catch (caught) {
      setError(
        (caught as Error).name === "AbortError"
          ? "Cancelled."
          : (caught as Error).message,
      );
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }

  function saveHistory() {
    if (!briefing) return;
    const item: WorkbenchHistoryItem = {
      id: runId,
      createdAt: new Date().toISOString(),
      request,
      briefing,
    };
    const next = [item, ...history.filter((existing) => existing.id !== item.id)].slice(
      0,
      20,
    );
    try {
      localStorage.setItem(historyKey(metadata.id), JSON.stringify(next));
      setHistory(next);
    } catch {
      setError("This browser could not save the run locally.");
    }
  }

  function restore(item: WorkbenchHistoryItem) {
    abort.current?.abort();
    abort.current = null;
    setBusy(false);
    setRunId(item.id);
    setRequest(item.request);
    setBriefing(item.briefing);
    setPartials({});
    setEvents([]);
    setError(null);
  }

  function clearHistory() {
    try {
      localStorage.removeItem(historyKey(metadata.id));
      setHistory([]);
    } catch {
      setError("This browser could not clear saved runs.");
    }
  }

  return (
    <div className="workbench-layout">
      <aside className="history-panel" aria-label="Saved runs">
        <div className="history-panel-header">
          <h2>History</h2>
          {history.length > 0 && (
            <button
              type="button"
              className="history-clear"
              onClick={clearHistory}
              disabled={busy}
            >
              Clear
            </button>
          )}
        </div>
        <p className="history-privacy">
          Saved only in this browser. Avoid saving sensitive customer data.
        </p>
        {history.length === 0 ? (
          <p className="muted">Save a completed run to return to it later.</p>
        ) : (
          history.map((item) => (
            <button
              key={item.id}
              type="button"
              className="history-entry"
              onClick={() => restore(item)}
              disabled={busy}
              aria-label={`Restore run from ${new Date(item.createdAt).toLocaleString()}`}
            >
              <strong>{new Date(item.createdAt).toLocaleString()}</strong>
              <span>Saved run</span>
            </button>
          ))
        )}
      </aside>
      <div className="workbench-main">
        <header className="app-header">
          <h1>{metadata.title}</h1>
          <p className="muted">{metadata.description}</p>
          {metadata.implementation && (
            <div className="implementation-tags" aria-label="Scenario architecture">
              <span>{displayTag(metadata.implementation.agent_type)}</span>
              <span>{displayTag(metadata.implementation.implementation_pattern)}</span>
              <span>{displayTag(metadata.implementation.orchestration_pattern)}</span>
              <span>{displayTag(metadata.implementation.application_shell)}</span>
            </div>
          )}
        </header>
        <DynamicSchemaForm
          key={JSON.stringify(request)}
          schema={metadata.request_schema}
          busy={busy}
          initialValues={request}
          onSubmit={(value) => void submit(value)}
          onCancel={() => abort.current?.abort()}
        />
        {error && <div className="card error" role="alert">{error}</div>}
        {warnings.length > 0 && (
          <div className="card warn" role="status">
            <strong>This run completed with warnings.</strong>
            <ul>
              {warnings.map((warning, index) => (
                <li key={`${index}-${warning}`}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
        {busy && (
          <div className="card" role="status" aria-live="polite">
            <span className="pulse" /> Working through validated stages…
          </div>
        )}
        <DynamicResultPanel
          metadata={metadata}
          runId={runId}
          briefing={briefing}
          partials={partials}
          pendingApprovals={pendingApprovals}
        />
        {briefing && (
          <div className="actions history-actions">
            <button type="button" onClick={saveHistory} disabled={currentRunSaved}>
              {currentRunSaved ? "Saved to this browser" : "Save to this browser"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
