import { useEffect, useRef } from "react";
import type { StreamEvent } from "../types/research";
import { labelForAgent, statusForAgent } from "../data/agentStatus";

interface Props {
  events: StreamEvent[];
  busy: boolean;
  // Per-agent progress counters accumulated from chunk lengths. Raw model
  // text is never retained or rendered; the character count drives a
  // rotating, human-readable status copy per agent so the user knows
  // the model is making progress during 30-60s gpt-5-mini calls.
  liveProgress?: [agent: string, characters: number][];
}

function describe(event: StreamEvent): { label: string; tone: string } {
  switch (event.type) {
    case "status":
      return { label: `status · ${event.stage}${(event as any).elapsed_s ? ` (${(event as any).elapsed_s}s)` : ""}`, tone: "info" };
    case "partial":
      return {
        label: `${labelForAgent(event.worker_id)} finished${(event as any).elapsed_s ? ` (${(event as any).elapsed_s}s)` : ""}`,
        tone: "ok",
      };
    case "worker_skipped":
      return {
        label: `${labelForAgent(event.worker_id)} skipped${event.error ? ` (${event.error})` : ""}`,
        tone: "warn",
      };
    case "briefing_ready":
      return { label: "Briefing ready — rendering", tone: "ok" };
    case "tool_skipped":
      return { label: `tool skipped · ${event.tool} (${event.reason})`, tone: "warn" };
    case "tool_result":
      return { label: `tool result · ${event.tool}`, tone: "ok" };
    case "tool_error":
      return { label: `tool error · ${event.tool} (${event.error})`, tone: "warn" };
    case "final":
      return { label: "Final briefing assembled", tone: "ok" };
    case "error":
      return { label: `error · ${event.message}`, tone: "err" };
    // ``chunk`` is routed before reaching this list, but TypeScript
    // wants the union exhausted.
    case "chunk":
      return { label: `chunk · ${labelForAgent(event.agent)}`, tone: "info" };
    // ``done`` and ``stream_interrupted`` are protocol-level — App.tsx
    // routes them away from the event log too, but the union must be
    // exhausted for the type checker.
    case "done":
      return { label: "stream complete", tone: "ok" };
    case "stream_interrupted":
      return {
        label: `stream interrupted · last seq ${event.last_seq}${event.last_event ? ` (${event.last_event})` : ""}`,
        tone: "err",
      };
    case "worker_started":
      return {
        label: `${labelForAgent(event.worker_id)} started`,
        tone: "info",
      };
    case "tool_pending_approval":
      return {
        label: `tool pending approval · ${event.tool}`,
        tone: "warn",
      };
    default:
      return { label: `unknown event`, tone: "info" };
  }
}

export function StreamingViewer({ events, busy, liveProgress }: Props) {
  const thoughtsRef = useRef<HTMLDivElement | null>(null);
  // Auto-scroll the thoughts panel to the bottom as new chunks arrive.
  useEffect(() => {
    if (thoughtsRef.current) {
      thoughtsRef.current.scrollTop = thoughtsRef.current.scrollHeight;
    }
  }, [liveProgress]);

  if (events.length === 0 && !busy && !liveProgress?.length) return null;
  return (
    <div className="card">
      <h2>
        Live stream
        {busy && <span className="pulse" aria-label="streaming" />}
      </h2>
      <ol className="event-log">
        {events.map((evt, i) => {
          const { label, tone } = describe(evt);
          return (
            <li key={i} className={`event event-${tone}`}>
              <span className="event-index">{i + 1}</span>
              <span className="event-label">{label}</span>
            </li>
          );
        })}
      </ol>
      {liveProgress && liveProgress.length > 0 && (
        <div className="live-thoughts" ref={thoughtsRef}>
          {liveProgress.map(([agent, characters]) => (
            <div key={agent} className="live-thought">
              <span className="thought-agent">
                <span className="pulse" aria-hidden="true" />{" "}
                {labelForAgent(agent)} is working…
              </span>
              <p className="thought-status">{statusForAgent(agent, characters)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
