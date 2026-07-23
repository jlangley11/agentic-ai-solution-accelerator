import type {
  GenericStreamEvent,
  ScenarioMetadata,
} from "../types/scenario";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "";

export async function fetchScenarioMetadata(): Promise<ScenarioMetadata> {
  const response = await fetch(`${API_BASE_URL}/scenario/metadata`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `Metadata request failed: ${response.status} ${response.statusText}`,
    );
  }
  return (await response.json()) as ScenarioMetadata;
}

interface RunScenarioOptions {
  signal?: AbortSignal;
  onEvent: (event: GenericStreamEvent) => void;
}

export async function runScenario(
  endpointPath: string,
  request: Record<string, unknown>,
  { signal, onEvent }: RunScenarioOptions,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${endpointPath}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) {
    throw new Error(
      `Request failed: ${response.status} ${response.statusText || "Unexpected response"}.`,
    );
  }
  if (!response.body) throw new Error("Response has no body to stream.");

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
      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        const message = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        separator = buffer.indexOf("\n\n");
        const data = message
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        try {
          const event = JSON.parse(data) as GenericStreamEvent;
          if ("seq" in event && typeof event.seq === "number") {
            const expected = lastSeq + 1;
            if (event.seq !== expected) {
              onEvent({
                type: "error",
                message: `SSE sequence error: expected ${expected}, received ${event.seq}.`,
              });
              await reader.cancel();
              return;
            }
            lastSeq = event.seq;
          }
          if (event.type === "done") sawDone = true;
          else lastEventType = event.type;
          onEvent(event);
        } catch {
          onEvent({
            type: "error",
            message: "The server returned a malformed SSE event.",
          });
        }
      }
    }
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

export async function submitScenarioFeedback(
  runId: string,
  section: string,
  rating: "up" | "down",
  comment = "",
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/scenario/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_id: runId,
      section,
      rating,
      comment,
    }),
  });
  if (!response.ok) {
    throw new Error(`Feedback request failed: ${response.status}`);
  }
}
