import { useEffect, useMemo, useRef, useState } from "react";
import type { ResearchBriefing, StreamEvent } from "../types/research";
import { JOKE_ROTATE_MS, PARTNER_JOKES } from "../data/jokes";

// ---------------------------------------------------------------------------
// Section configuration — accent colors, numbered badges
// ---------------------------------------------------------------------------

interface SectionMeta {
  num: number;
  label: string;
  accent: string;
  briefingKey?: keyof ResearchBriefing;
  workerId?: string;
  workerLabel?: string;
}

const SECTIONS: SectionMeta[] = [
  { num: 1, label: "Executive Summary", accent: "#3b82f6" },
  {
    num: 2, label: "Account Profile", accent: "#6366f1",
    briefingKey: "account_profile", workerId: "account_planner",
    workerLabel: "researching company news, signals, and buying committee",
  },
  {
    num: 3, label: "ICP Fit Analysis", accent: "#10b981",
    briefingKey: "icp_fit", workerId: "icp_fit_analyst",
    workerLabel: "scoring fit against your ICP",
  },
  {
    num: 4, label: "Competitive Play", accent: "#ef4444",
    briefingKey: "competitive_play", workerId: "competitive_context",
    workerLabel: "mapping competitor presence and differentiators",
  },
  {
    num: 5, label: "Recommended Outreach", accent: "#14b8a6",
    briefingKey: "recommended_outreach", workerId: "outreach_personalizer",
    workerLabel: "drafting outreach for the persona",
  },
  { num: 6, label: "Next Steps", accent: "#f59e0b" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

function humanise(key: string): string {
  const s = key.replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : key;
}

// ---------------------------------------------------------------------------
// Copy-as-markdown
// ---------------------------------------------------------------------------

function valueToMarkdown(v: unknown, depth = 0): string {
  if (v === null || v === undefined) return "_not available_";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) {
    if (v.length === 0) return "_(none)_";
    if (isStringArray(v)) return v.map((s) => `- ${s}`).join("\n");
    if (v.every(isRecord))
      return v
        .map((row) => recordToMarkdown(row as Record<string, unknown>, depth))
        .join("\n\n");
    return v.map(String).join(", ");
  }
  if (isRecord(v)) return recordToMarkdown(v, depth);
  return String(v);
}

function recordToMarkdown(rec: Record<string, unknown>, depth = 0): string {
  return Object.entries(rec)
    .map(([k, val]) => `**${humanise(k)}:** ${valueToMarkdown(val, depth + 1)}`)
    .join("\n");
}

function CopyButton({ data, label }: { data: unknown; label: string }) {
  const [copied, setCopied] = useState(false);
  async function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    const md = `## ${label}\n\n${valueToMarkdown(data)}`;
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      type="button"
      className="copy-md-btn"
      onClick={handleCopy}
      title="Copy as Markdown"
    >
      {copied ? "\u2713 Copied" : "\ud83d\udccb Copy"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Field-specific renderers
// ---------------------------------------------------------------------------

function NewsItem({ item }: { item: Record<string, unknown> }) {
  const title = String(item["title"] ?? "Untitled");
  const date = item["date"] ? String(item["date"]) : null;
  const summary = item["summary"] ? String(item["summary"]) : null;
  const url = item["url"] ? String(item["url"]) : null;
  return (
    <article className="news-card">
      <header>
        <span className="news-title">{title}</span>
        {Boolean(date) && <span className="badge">{date}</span>}
      </header>
      {Boolean(summary) && <p className="news-summary">{summary}</p>}
      {Boolean(url) && (
        <p className="muted news-source">
          source: <code>{url}</code>
        </p>
      )}
    </article>
  );
}

function CommitteeTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return <p className="muted">(none identified)</p>;
  return (
    <table className="mini-table">
      <thead>
        <tr>
          <th>Role</th>
          <th>Name</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            <td>{String(row["role"] ?? "\u2014")}</td>
            <td>
              {String(
                row["name_if_known"] ?? row["name"] ?? "not available",
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SignalList({ items }: { items: Record<string, unknown>[] }) {
  if (items.length === 0) return <p className="muted">(no signals)</p>;
  return (
    <ul className="signal-list">
      {items.map((s, i) => (
        <li key={i}>
          <span>{String(s["signal"] ?? "")}</span>
          {Boolean(s["source"]) && (
            <span className="muted signal-source">
              source: <code>{String(s["source"])}</code>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function StringList({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="muted">(none)</p>;
  return (
    <ul className="bullet-list">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}

function FlatKeyValues({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="muted">(empty)</p>;
  return (
    <dl className="kv">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt>{humanise(k)}</dt>
          <dd>
            <GenericValue fieldKey={k} value={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function CitationsList({ items }: { items: Record<string, unknown>[] }) {
  if (items.length === 0) return <p className="muted">(no citations)</p>;
  return (
    <ol className="citation-list">
      {items.map((c, i) => {
        const url = c["url"] ? String(c["url"]) : null;
        const quote = c["quote"] ? String(c["quote"]) : null;
        const title = c["title"] ? String(c["title"]) : null;
        let parsedHost: string | null = null;
        let isHttpUrl = false;
        if (url) {
          try {
            const parsed = new URL(url);
            isHttpUrl = parsed.protocol === "http:" || parsed.protocol === "https:";
            parsedHost = parsed.hostname.replace(/^www\./, "");
          } catch {
            // Citation `url` is not an absolute URL (e.g., a document name or
            // relative path). Fall through and render it as plain text.
          }
        }
        const label = title || parsedHost || (url ?? `Source ${i + 1}`);
        return (
          <li key={i} className="citation-item">
            <span className="citation-num">{i + 1}</span>
            {isHttpUrl && url ? (
              <a href={url} target="_blank" rel="noopener noreferrer" className="citation-link">{label}</a>
            ) : (
              <span className="citation-label">{label}</span>
            )}
            {quote && <span className="citation-quote">&ldquo;{quote}&rdquo;</span>}
          </li>
        );
      })}
    </ol>
  );
}

function GenericValue({
  fieldKey,
  value,
}: {
  fieldKey: string;
  value: unknown;
}) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">not available</span>;
  }
  if (typeof value === "string") {
    if (/^(https?:\/\/|document:)/.test(value)) return <code>{value}</code>;
    return <>{value}</>;
  }
  if (typeof value === "number" || typeof value === "boolean")
    return <>{String(value)}</>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">(none)</span>;
    if (isStringArray(value)) return <StringList items={value} />;
    if (value.every(isRecord)) {
      const sample = value[0] as Record<string, unknown>;
      const keys = new Set(Object.keys(sample));
      if (
        fieldKey === "recent_news" ||
        (keys.has("title") && keys.has("summary"))
      )
        return (
          <div className="news-list">
            {(value as Record<string, unknown>[]).map((it, i) => (
              <NewsItem key={i} item={it} />
            ))}
          </div>
        );
      if (
        fieldKey === "buying_committee" ||
        (keys.has("role") && (keys.has("name_if_known") || keys.has("name")))
      )
        return <CommitteeTable rows={value as Record<string, unknown>[]} />;
      if (
        fieldKey === "signal_evidence" ||
        (keys.has("signal") && keys.has("source"))
      )
        return <SignalList items={value as Record<string, unknown>[]} />;
      if (
        fieldKey === "citations" ||
        (keys.has("url") && keys.has("quote"))
      )
        return <CitationsList items={value as Record<string, unknown>[]} />;
      return (
        <div className="record-list">
          {(value as Record<string, unknown>[]).map((row, i) => (
            <div key={i} className="record-card">
              <FlatKeyValues data={row} />
            </div>
          ))}
        </div>
      );
    }
    return <>{value.map((v) => String(v)).join(", ")}</>;
  }
  if (isRecord(value)) return <FlatKeyValues data={value} />;
  return <code>{String(value)}</code>;
}

// ---------------------------------------------------------------------------
// Section-specific layouts (hybrid typed + generic fallback)
// ---------------------------------------------------------------------------

const ACCOUNT_OVERVIEW_KEYS = new Set([
  "company_name", "industry", "employee_count", "revenue", "hq_location",
  "domain", "website", "headquarters", "size", "sector", "founded",
  "description", "company_overview", "annual_revenue", "location",
]);
const ACCOUNT_SPECIAL_KEYS = new Set([
  ...ACCOUNT_OVERVIEW_KEYS,
  "buying_committee", "recent_news", "signal_evidence", "citations",
]);

function AccountProfileLayout({ data }: { data: Record<string, unknown> }) {
  const overview: Record<string, unknown> = {};
  const rest: Record<string, unknown> = {};
  // Extract company_overview / description as prose text
  let prose = "";
  for (const [k, v] of Object.entries(data)) {
    if (k === "company_overview" || k === "description") {
      if (typeof v === "string" && v.length > 0) prose = v;
    } else if (ACCOUNT_OVERVIEW_KEYS.has(k)) {
      overview[k] = v;
    } else if (!ACCOUNT_SPECIAL_KEYS.has(k)) {
      rest[k] = v;
    }
  }
  const committee = data.buying_committee;
  const news = data.recent_news;
  const signals = data.signal_evidence;
  const citations = data.citations;
  const hasOverview = Object.keys(overview).length > 0;
  const hasCommittee = Array.isArray(committee) && committee.length > 0;

  return (
    <div className="section-content">
      {prose && <div className="company-prose">{prose}</div>}
      {(hasOverview || hasCommittee) && (
        <div className="two-col-grid">
          {hasOverview && (
            <div className="sub-card" style={{ borderLeftColor: "#6366f1" }}>
              <h4 className="sub-card-title">Key Facts</h4>
              <FlatKeyValues data={overview} />
            </div>
          )}
          {hasCommittee && (
            <div className="sub-card" style={{ borderLeftColor: "#818cf8" }}>
              <h4 className="sub-card-title">Buying Committee</h4>
              <div className="committee-chips">
                {(committee as Record<string, unknown>[]).map((row, i) => (
                  <span key={i} className="committee-chip">
                    <span className="committee-chip-role">
                      {String(row["role"] ?? "—")}
                    </span>
                    {String(row["name_if_known"] ?? row["name"] ?? "")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {Array.isArray(news) && news.length > 0 && (
        <div className="sub-block">
          <h4 className="sub-block-title">Recent News</h4>
          <div className="news-list">
            {(news as Record<string, unknown>[]).map((it, i) => (
              <NewsItem key={i} item={it} />
            ))}
          </div>
        </div>
      )}
      {Array.isArray(signals) && signals.length > 0 && (
        <div className="sub-block">
          <h4 className="sub-block-title">Signal Evidence</h4>
          <SignalList items={signals as Record<string, unknown>[]} />
        </div>
      )}
      {Array.isArray(citations) && citations.length > 0 && (
        <div className="sub-block">
          <h4 className="sub-block-title">Citations</h4>
          <CitationsList items={citations as Record<string, unknown>[]} />
        </div>
      )}
      {Object.keys(rest).length > 0 && <FlatKeyValues data={rest} />}
    </div>
  );
}

const ICP_SCORE_KEYS = new Set([
  "fit_score", "score", "icp_score", "overall_score",
]);
const ICP_CRITERIA_KEYS = new Set([
  "fit_criteria", "criteria", "scoring_criteria", "fit_signals",
]);
const ICP_GAP_KEYS = new Set([
  "gaps", "gap_analysis", "missing_criteria", "risks",
]);
const ICP_SPECIAL_KEYS: ReadonlySet<string> = new Set([
  ...ICP_SCORE_KEYS, ...ICP_CRITERIA_KEYS, ...ICP_GAP_KEYS,
]);
void ICP_SPECIAL_KEYS; // referenced only in future guard clauses

function IcpFitLayout({ data }: { data: Record<string, unknown> }) {
  let fitScore: unknown;
  let criteria: unknown;
  let gaps: unknown;
  const rest: Record<string, unknown> = {};

  for (const [k, v] of Object.entries(data)) {
    if (ICP_SCORE_KEYS.has(k)) fitScore = v;
    else if (ICP_CRITERIA_KEYS.has(k)) criteria = v;
    else if (ICP_GAP_KEYS.has(k)) gaps = v;
    else rest[k] = v;
  }

  const scoreNum = typeof fitScore === "number" ? fitScore
    : typeof fitScore === "string" ? parseFloat(fitScore) : NaN;
  const scoreBg = !isNaN(scoreNum) && scoreNum >= 7 ? "#10b981"
    : !isNaN(scoreNum) && scoreNum >= 4 ? "#f59e0b" : "#ef4444";

  return (
    <div className="section-content">
      {fitScore !== undefined && (
        <div className="score-gauge">
          <div className="score-circle" style={{ background: scoreBg }}>
            {String(fitScore)}
          </div>
          <div>
            <div className="score-label">ICP Fit Score</div>
            <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 2 }}>
              {!isNaN(scoreNum) && scoreNum >= 7 ? "Strong fit" : !isNaN(scoreNum) && scoreNum >= 4 ? "Moderate fit" : "Weak fit"}
            </div>
          </div>
        </div>
      )}
      {(criteria != null || gaps != null) ? (
        <div className="two-col-grid">
          {criteria != null && (
            <div className="sub-card" style={{ borderLeftColor: "#10b981" }}>
              <h4 className="sub-card-title">✓ Fit Criteria</h4>
              <GenericValue fieldKey="fit_criteria" value={criteria} />
            </div>
          )}
          {gaps != null && (
            <div className="sub-card" style={{ borderLeftColor: "#f59e0b" }}>
              <h4 className="sub-card-title">⚠ Gaps / Risks</h4>
              <GenericValue fieldKey="gaps" value={gaps} />
            </div>
          )}
        </div>
      ) : null}
      {Object.keys(rest).length > 0 && <FlatKeyValues data={rest} />}
    </div>
  );
}

const COMP_COMPETITOR_KEYS = new Set([
  "competitors", "incumbent_vendors", "competitive_landscape",
]);
const COMP_DIFF_KEYS = new Set([
  "differentiators", "our_differentiators", "key_differentiators",
]);
const COMP_OBJ_KEYS = new Set([
  "objection_handlers", "objections", "common_objections",
]);
const COMP_SPECIAL_KEYS: ReadonlySet<string> = new Set([
  ...COMP_COMPETITOR_KEYS, ...COMP_DIFF_KEYS, ...COMP_OBJ_KEYS,
]);
void COMP_SPECIAL_KEYS; // referenced only in future guard clauses

function CompetitiveLayout({ data }: { data: Record<string, unknown> }) {
  let competitors: unknown;
  let differentiators: unknown;
  let objections: unknown;
  const rest: Record<string, unknown> = {};

  for (const [k, v] of Object.entries(data)) {
    if (COMP_COMPETITOR_KEYS.has(k)) competitors = v;
    else if (COMP_DIFF_KEYS.has(k)) differentiators = v;
    else if (COMP_OBJ_KEYS.has(k)) objections = v;
    else rest[k] = v;
  }

  // Render competitors as horizontal cards with stance badges
  const renderCompetitors = () => {
    if (competitors == null) return null;
    if (Array.isArray(competitors) && competitors.every(isRecord)) {
      return (
        <div className="competitor-row">
          {(competitors as Record<string, unknown>[]).map((c, i) => {
            const name = String(c["name"] ?? c["vendor"] ?? c["competitor"] ?? `Competitor ${i + 1}`);
            const stance = String(c["stance"] ?? c["position"] ?? c["type"] ?? "").toLowerCase();
            const stanceClass = stance.includes("incumbent") ? "stance-incumbent"
              : stance.includes("challenger") ? "stance-challenger" : "stance-default";
            return (
              <div key={i} className="competitor-card">
                <div className="competitor-name">{name}</div>
                {stance && <span className={`stance-badge ${stanceClass}`}>{stance}</span>}
                {c["notes"] ? <div className="muted" style={{ fontSize: "0.82rem", marginTop: 4 }}>{String(c["notes"])}</div> : null}
              </div>
            );
          })}
        </div>
      );
    }
    // Fallback for string arrays or other shapes
    return <GenericValue fieldKey="competitors" value={competitors} />;
  };

  // Render differentiators as numbered pills
  const renderDiffs = () => {
    if (differentiators == null) return null;
    if (isStringArray(differentiators as unknown)) {
      return (
        <div className="diff-pills">
          {(differentiators as string[]).map((d, i) => (
            <span key={i} className="diff-pill">
              <span className="diff-pill-num">{i + 1}</span>
              {d}
            </span>
          ))}
        </div>
      );
    }
    return <GenericValue fieldKey="differentiators" value={differentiators} />;
  };

  return (
    <div className="section-content">
      {competitors != null && (
        <div className="sub-block">
          <h4 className="sub-block-title">Competitive Landscape</h4>
          {renderCompetitors()}
        </div>
      )}
      {differentiators != null && (
        <div className="sub-block">
          <h4 className="sub-block-title">Our Differentiators</h4>
          {renderDiffs()}
        </div>
      )}
      {objections != null && (
        <div className="sub-block">
          <h4 className="sub-block-title">Objection Handlers</h4>
          <GenericValue fieldKey="objections" value={objections} />
        </div>
      )}
      {Object.keys(rest).length > 0 && <FlatKeyValues data={rest} />}
    </div>
  );
}

const OUTREACH_SUBJECT_KEYS = new Set([
  "subject_line", "subject", "email_subject",
]);
const OUTREACH_BODY_KEYS = new Set([
  "email_body", "body", "message_body", "email_draft",
]);
const OUTREACH_CTA_KEYS = new Set([
  "call_to_action", "cta", "next_step",
]);
const OUTREACH_SPECIAL_KEYS: ReadonlySet<string> = new Set([
  ...OUTREACH_SUBJECT_KEYS, ...OUTREACH_BODY_KEYS, ...OUTREACH_CTA_KEYS,
]);

function OutreachLayout({ data }: { data: Record<string, unknown> }) {
  let subject = "";
  let body = "";
  let cta = "";
  const rest: Record<string, unknown> = {};

  for (const [k, v] of Object.entries(data)) {
    if (OUTREACH_SUBJECT_KEYS.has(k) && typeof v === "string") subject = v;
    else if (OUTREACH_BODY_KEYS.has(k) && typeof v === "string") body = v;
    else if (OUTREACH_CTA_KEYS.has(k) && typeof v === "string") cta = v;
    else if (!OUTREACH_SPECIAL_KEYS.has(k)) rest[k] = v;
  }

  const hasEmail = subject || body;

  return (
    <div className="section-content">
      {hasEmail ? (
        <div className="email-preview">
          {subject && (
            <div className="email-subject">
              <span>✉</span> {subject}
            </div>
          )}
          {body && <div className="email-body">{body}</div>}
          {cta && <div style={{ padding: "0 14px 14px" }}><span className="email-cta">{cta}</span></div>}
        </div>
      ) : null}
      {Object.keys(rest).length > 0 && (
        <div style={{ marginTop: hasEmail ? 12 : 0 }}>
          <FlatKeyValues data={rest} />
        </div>
      )}
    </div>
  );
}

function renderSectionContent(
  sectionNum: number,
  data: Record<string, unknown>,
) {
  switch (sectionNum) {
    case 2:
      return <AccountProfileLayout data={data} />;
    case 3:
      return <IcpFitLayout data={data} />;
    case 4:
      return <CompetitiveLayout data={data} />;
    case 5:
      return <OutreachLayout data={data} />;
    default:
      return <FlatKeyValues data={data} />;
  }
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

interface Props {
  briefing: ResearchBriefing | null;
  events: StreamEvent[];
  isComplete: boolean;
  busy: boolean;
}

// Tab metadata for the 4 worker sections
const TABS = SECTIONS.filter((s) => s.num >= 2 && s.num <= 5);

export function ResultPanel({ briefing, events, busy }: Props) {
  const [showRaw, setShowRaw] = useState(false);
  const [activeTab, setActiveTab] = useState(2);
  const [manualOverride, setManualOverride] = useState(false);

  // Centralized joke rotation — single instance in the header
  const [jokeIdx, setJokeIdx] = useState(0);
  useEffect(() => {
    if (!busy) return;
    const t = window.setInterval(() => {
      setJokeIdx((prev) => (prev + 1) % PARTNER_JOKES.length);
    }, JOKE_ROTATE_MS);
    return () => window.clearInterval(t);
  }, [busy]);

  // Extract per-section data from worker partials for progressive render
  const partialsByWorker = useMemo(() => {
    const map: Record<string, unknown> = {};
    for (const e of events) {
      if (e.type === "partial") map[e.worker_id] = e.output;
    }
    return map;
  }, [events]);

  function dataFor(meta: SectionMeta): unknown | null {
    if (meta.briefingKey) {
      if (briefing) return briefing[meta.briefingKey];
      if (meta.workerId) {
        return partialsByWorker[meta.workerId] ?? null;
      }
    }
    return null;
  }

  // Auto-advance: switch to the latest tab that has data (unless user clicked)
  const tabDataCount = useMemo(() => {
    return TABS.filter((t) => {
      if (!t.briefingKey) return false;
      const d = briefing
        ? briefing[t.briefingKey]
        : (t.workerId ? (partialsByWorker[t.workerId] ?? null) : null);
      return d !== null && isRecord(d);
    }).length;
  }, [partialsByWorker, briefing]);

  const prevDataCountRef = useRef(0);

  useEffect(() => {
    if (tabDataCount > prevDataCountRef.current && !manualOverride) {
      const tabsWithData = TABS.filter((t) => {
        if (!t.briefingKey) return false;
        const d = briefing
          ? briefing[t.briefingKey]
          : (t.workerId ? (partialsByWorker[t.workerId] ?? null) : null);
        return d !== null && isRecord(d);
      });
      if (tabsWithData.length > 0) {
        setActiveTab(tabsWithData[tabsWithData.length - 1].num);
      }
    }
    prevDataCountRef.current = tabDataCount;
  }, [tabDataCount, manualOverride, briefing, partialsByWorker]);

  // Reset manual override on new submission
  useEffect(() => {
    if (busy && Object.keys(partialsByWorker).length === 0) {
      setManualOverride(false);
      prevDataCountRef.current = 0;
    }
  }, [busy, partialsByWorker]);

  // --- All hooks above this line ---
  const hasAnything =
    briefing !== null || Object.keys(partialsByWorker).length > 0;
  if (!hasAnything && !busy) return null;

  const activeData = dataFor(TABS.find((t) => t.num === activeTab) ?? TABS[0]);
  const activeHasData = activeData !== null && isRecord(activeData);

  const execItems = briefing?.executive_summary;
  const hasExec = !!execItems && execItems.length > 0;
  const nextItems = briefing?.next_steps;
  const hasNext = !!nextItems && nextItems.length > 0;

  return (
    <div className="result-card">
      <div className="result-header">
        <h2>
          {"\ud83d\udcca"} Research Briefing
          {!briefing && busy && (
            <span className="muted briefing-progress">
              {" "}&mdash; assembling&hellip;
            </span>
          )}
        </h2>
        <div className="result-header-actions">
          <label className="raw-toggle">
            <input
              type="checkbox"
              checked={showRaw}
              onChange={(e) => setShowRaw(e.target.checked)}
            />
            Raw JSON
          </label>
        </div>
      </div>

      {/* Single centralized joke — only when busy */}
      {busy && !briefing && (
        <div className="joke-banner">
          <span className="pulse" />
          <span>
            <span className="joke-prefix">While you wait … </span>
            <span className="joke-text" key={jokeIdx}>{PARTNER_JOKES[jokeIdx]}</span>
          </span>
        </div>
      )}

      {showRaw ? (
        <pre className="raw-json">
          {JSON.stringify(briefing ?? partialsByWorker, null, 2)}
        </pre>
      ) : (
        <>
          {/* Executive Summary — full width at top */}
          <div className="exec-strip">
            <div className="exec-strip-header">
              <span className="section-badge" style={{ background: "#3b82f6", color: "#fff" }}>1</span>
              <span className="exec-strip-title">Executive Summary</span>
              {hasExec && <CopyButton data={execItems} label="Executive Summary" />}
            </div>
            {hasExec ? (
              <div className="exec-callout">
                <ul className="bullet-list">
                  {execItems!.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="pending-placeholder">
                <span className="pulse" />
                <span className="muted">Waiting on supervisor…</span>
              </div>
            )}
          </div>

          {/* Tab bar for sections 2-5 */}
          <div className="tab-bar">
            {TABS.map((meta) => {
              const d = dataFor(meta);
              const ready = d !== null && isRecord(d);
              return (
                <button
                  key={meta.num}
                  type="button"
                  className={`tab-btn${activeTab === meta.num ? " active" : ""}${ready ? " has-data" : ""}`}
                  onClick={() => { setActiveTab(meta.num); setManualOverride(true); }}
                  style={{ "--tab-accent": meta.accent } as React.CSSProperties}
                >
                  <span className="tab-badge" style={{ background: meta.accent }}>{meta.num}</span>
                  <span className="tab-label">{meta.label}</span>
                  {ready && <span className="tab-ready-dot" />}
                  {!ready && busy && <span className="pulse tab-pulse" />}
                </button>
              );
            })}
          </div>

          {/* Active tab content */}
          <div className="tab-content" style={{ "--tab-accent": TABS.find((t) => t.num === activeTab)?.accent } as React.CSSProperties}>
            {activeHasData ? (
              <div className="tab-content-inner">
                <div className="tab-content-header">
                  <CopyButton
                    data={activeData}
                    label={TABS.find((t) => t.num === activeTab)?.label ?? ""}
                  />
                </div>
                {renderSectionContent(activeTab, activeData as Record<string, unknown>)}
              </div>
            ) : (
              <div className="pending-placeholder">
                <span className="pulse" />
                <span className="muted">
                  {TABS.find((t) => t.num === activeTab)?.workerLabel ?? "Pending…"}
                </span>
              </div>
            )}
          </div>

          {/* Next Steps — full width at bottom */}
          <div className="next-strip">
            <div className="exec-strip-header">
              <span className="section-badge" style={{ background: "#f59e0b", color: "#fff" }}>6</span>
              <span className="exec-strip-title">Next Steps</span>
              {hasNext && <CopyButton data={nextItems} label="Next Steps" />}
            </div>
            {hasNext ? (
              <ol className="bullet-list next-steps-list">
                {nextItems!.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ol>
            ) : (
              <div className="pending-placeholder">
                <span className="pulse" />
                <span className="muted">Waiting on supervisor…</span>
              </div>
            )}
          </div>

          {briefing?.requires_approval &&
            briefing.requires_approval.length > 0 && (
              <div className="hitl-section">
                <h4 className="sub-block-title">Pending Approvals</h4>
                {briefing.requires_approval.map((tool) => {
                  const args = briefing.tool_args[tool] ?? {};
                  return (
                    <div key={tool} className="hitl-card">
                      <header>
                        <code>{tool}</code>
                        <span className="badge warn">requires approval</span>
                      </header>
                      <FlatKeyValues data={args} />
                    </div>
                  );
                })}
              </div>
            )}

          {briefing?.usage && (
            <details className="usage-details">
              <summary className="muted">Token usage</summary>
              <FlatKeyValues
                data={briefing.usage as Record<string, unknown>}
              />
            </details>
          )}
        </>
      )}
    </div>
  );
}
