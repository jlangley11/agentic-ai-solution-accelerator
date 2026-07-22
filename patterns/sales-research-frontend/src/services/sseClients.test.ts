// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { runResearch } from "./researchClient";
import { runScenario } from "./scenarioClient";
import type { ResearchRequest, StreamEvent } from "../types/research";
import type { GenericStreamEvent } from "../types/scenario";

function responseWithEvents(events: object[]): Response {
  const body = events
    .map((event) => `data: ${JSON.stringify(event)}\n\n`)
    .join("");
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SSE sequence validation", () => {
  it("rejects out-of-order generic scenario events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        responseWithEvents([
          { type: "status", stage: "one", seq: 1 },
          { type: "status", stage: "duplicate", seq: 1 },
        ]),
      ),
    );
    const received: GenericStreamEvent[] = [];

    await runScenario("/demo", { query: "test" }, {
      onEvent: (event) => received.push(event),
    });

    expect(received.map((event) => event.type)).toEqual(["status", "error"]);
    expect(
      (received[1] as Extract<GenericStreamEvent, { type: "error" }>).message,
    ).toContain("expected 2, received 1");
  });

  it("rejects sequence gaps in the sales client", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        responseWithEvents([
          { type: "status", stage: "one", seq: 1 },
          { type: "done", seq: 3 },
        ]),
      ),
    );
    const received: StreamEvent[] = [];
    const request: ResearchRequest = {
      company_name: "Contoso",
      domain: "",
      seller_intent: "Prepare",
      persona: "CIO",
      icp_definition: "Enterprise",
      our_solution: "Solution",
      context_hints: [],
    };

    await runResearch(request, {
      onEvent: (event) => received.push(event),
    });

    expect(received.map((event) => event.type)).toEqual(["status", "error"]);
    expect(
      (received[1] as Extract<StreamEvent, { type: "error" }>).message,
    ).toContain("expected 2, received 3");
  });
});
