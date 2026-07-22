import { useState } from "react";
import { submitScenarioFeedback } from "../services/scenarioClient";
import type {
  ScenarioMetadata,
  ScenarioOutputSection,
} from "../types/scenario";

interface Props {
  metadata: ScenarioMetadata;
  runId: string;
  briefing: Record<string, unknown> | null;
  partials: Record<string, unknown>;
  pendingApprovals: { tool: string; args?: Record<string, unknown> }[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function humanize(value: string): string {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function Value({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="muted">Not available</span>;
  if (typeof value === "string" || typeof value === "number") return <>{String(value)}</>;
  if (typeof value === "boolean") return <>{value ? "Yes" : "No"}</>;
  if (Array.isArray(value)) {
    return (
      <ul className="bullet-list">
        {value.map((item, index) => (
          <li key={index}>
            <Value value={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (isRecord(value)) {
    return (
      <dl className="kv">
        {Object.entries(value).map(([key, item]) => (
          <div key={key}>
            <dt>{humanize(key)}</dt>
            <dd><Value value={item} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  return <>{String(value)}</>;
}

function Feedback({ runId, section }: { runId: string; section: string }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  const [failed, setFailed] = useState(false);
  async function send(rating: "up" | "down") {
    try {
      await submitScenarioFeedback(runId, section, rating);
      setSent(rating);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }
  return (
    <div className="section-feedback" aria-label={`Feedback for ${section}`}>
      <span className={failed ? "event-err" : "muted"}>
        {failed ? "Feedback failed" : sent ? "Feedback recorded" : "Useful?"}
      </span>
      <button type="button" onClick={() => void send("up")} disabled={sent !== null}>
        Yes
      </button>
      <button type="button" onClick={() => void send("down")} disabled={sent !== null}>
        No
      </button>
    </div>
  );
}

export function DynamicResultPanel({
  metadata,
  runId,
  briefing,
  partials,
  pendingApprovals,
}: Props) {
  const data = briefing ?? partials;
  const configured = metadata.output_sections;
  const sections: ScenarioOutputSection[] =
    configured.length > 0
      ? configured
      : Object.keys(data).map((key) => ({ key, label: humanize(key) }));

  if (Object.keys(data).length === 0 && pendingApprovals.length === 0) return null;

  return (
    <div className="result-card dynamic-results">
      <div className="result-header">
        <h2>{briefing ? "Result" : "Validated progress"}</h2>
      </div>
      <div className="dynamic-section-grid">
        {sections.map((section) => {
          const value = data[section.key];
          if (value === undefined) return null;
          return (
            <section key={section.key} className="dynamic-section">
              <header>
                <h3>{section.label ?? humanize(section.key)}</h3>
                {briefing && <Feedback runId={runId} section={section.key} />}
              </header>
              <Value value={value} />
            </section>
          );
        })}
      </div>
      {pendingApprovals.length > 0 && (
        <section className="hitl-section">
          <h3>Pending approvals</h3>
          <p className="muted">
            Approvals are handled by the configured external approver. This
            workbench does not bypass the accelerator HITL checkpoint.
          </p>
          {pendingApprovals.map((approval) => (
            <div key={approval.tool} className="hitl-card">
              <header>
                <code>{approval.tool}</code>
                <span className="badge warn">awaiting external approval</span>
              </header>
              <Value value={approval.args ?? {}} />
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
