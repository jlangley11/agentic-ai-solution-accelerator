// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ScenarioMetadata } from "../types/scenario";
import { ScenarioWorkbench } from "./ScenarioWorkbench";

const metadata: ScenarioMetadata = {
  id: "claims-review",
  title: "Claims Review",
  description: "Review a claim.",
  experience_kind: "form-report",
  endpoint_path: "/claims/stream",
  request_schema: { type: "object", properties: {} },
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
};

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("ScenarioWorkbench history", () => {
  it("does not display saved request values and lets the user clear local history", () => {
    localStorage.setItem(
      "accelerator-workbench-history:claims-review",
      JSON.stringify([
        {
          id: "run-1",
          createdAt: "2026-07-22T00:00:00Z",
          request: { customer_secret: "sensitive-account-value" },
          briefing: { result: "Complete" },
        },
      ]),
    );

    render(<ScenarioWorkbench metadata={metadata} />);

    expect(screen.getByText("Saved run")).toBeInTheDocument();
    expect(screen.queryByText("sensitive-account-value")).not.toBeInTheDocument();
    expect(
      screen.getByText("Saved only in this browser. Avoid saving sensitive customer data."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.queryByText("Saved run")).not.toBeInTheDocument();
    expect(localStorage.getItem("accelerator-workbench-history:claims-review")).toBeNull();
  });

  it("ignores malformed browser history entries", () => {
    localStorage.setItem(
      "accelerator-workbench-history:claims-review",
      JSON.stringify([
        null,
        { id: "missing-fields" },
        {
          id: "invalid-date",
          createdAt: "not-a-date",
          request: {},
          briefing: {},
        },
      ]),
    );

    render(<ScenarioWorkbench metadata={metadata} />);

    expect(screen.getByText("Save a completed run to return to it later.")).toBeInTheDocument();
    expect(screen.queryByText("Saved run")).not.toBeInTheDocument();
  });
});
