// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App metadata bootstrap", () => {
  it("fails visibly instead of silently rendering the sales UI and can retry", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("metadata endpoint unavailable"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "claims-review",
          title: "Claims Review",
          description: "Review a claim.",
          experience_kind: "form-report",
          endpoint_path: "/claims/stream",
          request_schema: {
            title: "Claim",
            type: "object",
            properties: { claim_id: { type: "string", title: "Claim ID" } },
            required: ["claim_id"],
          },
          response_schema: null,
          implementation: {
            agent_type: "prompt-agent",
            implementation_pattern: "managed-prompt",
            orchestration_pattern: "single-agent",
            application_shell: "workbench",
          },
          agents: [],
          output_sections: [],
          approval: { mode: "external" },
          stream_contract: {
            validated_partial_event: null,
            final_event: "final",
            terminal_event: "done",
            unvalidated_chunk_event: "chunk",
          },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Scenario metadata is unavailable",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Sales Research — reference UI" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Claims Review" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
