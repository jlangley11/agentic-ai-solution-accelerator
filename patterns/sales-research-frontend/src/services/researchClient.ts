import type { ResearchRequest, StreamEvent } from "../types/research";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "";

// Empty base URL means "same-origin" — the dev server proxies /research/*
// to the API, and the SWA prod build either uses the SWA `/api/*` rewrite
// or expects a VITE_API_BASE_URL set at build time.
export const RESEARCH_STREAM_URL = `${API_BASE_URL}/research/stream`;

export interface RunOptions {
  onEvent: (event: StreamEvent) => void;
  signal?: AbortSignal;
}

/**
 * POSTs to /research/stream and parses the text/event-stream body.
 * The backend emits one JSON object per SSE `data:` line; this helper
 * normalises chunked reads into per-event callbacks.
 */
export async function runResearch(
  request: ResearchRequest,
  { onEvent, signal }: RunOptions,
): Promise<void> {
  const response = await fetch(RESEARCH_STREAM_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(
      `Request failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail.slice(0, 300)}` : ""
      }`,
    );
  }
  if (!response.body) {
    throw new Error("Response has no body to stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSeq = 0;
  let lastEventType: string | undefined;
  let sawDone = false;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by a blank line.
      let sep = buffer.indexOf("\n\n");
      while (sep !== -1) {
        const rawMessage = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        sep = buffer.indexOf("\n\n");

        // Each SSE message can have multiple `data:` lines; concat per spec.
        // SSE comment lines start with ":" and are protocol-level
        // keepalives (the backend emits ": ka\n\n" every 15s of silence)
        // — we drop them entirely; they never reach the UI.
        const dataLines = rawMessage
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart());
        if (dataLines.length === 0) continue;

        const payload = dataLines.join("\n");
        try {
          const parsed = JSON.parse(payload) as StreamEvent;
          if ("seq" in parsed && typeof parsed.seq === "number") {
            const expected = lastSeq + 1;
            if (parsed.seq !== expected) {
              onEvent({
                type: "error",
                message: `SSE sequence error: expected ${expected}, received ${parsed.seq}.`,
              });
              await reader.cancel();
              return;
            }
            lastSeq = parsed.seq;
          }
          if (parsed.type === "done") {
            sawDone = true;
          } else {
            lastEventType = parsed.type;
          }
          onEvent(parsed);
        } catch (err) {
          onEvent({
            type: "error",
            message: `Malformed SSE chunk: ${(err as Error).message}`,
          });
        }
      }
    }
    // EOF without a terminal ``done`` event = stream was cut by an
    // intermediary. Surface this clearly so the UI does not silently
    // treat partial output as a degraded success. Aborts (user
    // cancelled) throw and skip this branch.
    if (!sawDone) {
      onEvent({
        type: "stream_interrupted",
        last_seq: lastSeq,
        last_event: lastEventType,
      });
    }
  } finally {
    reader.releaseLock();
  }
}
