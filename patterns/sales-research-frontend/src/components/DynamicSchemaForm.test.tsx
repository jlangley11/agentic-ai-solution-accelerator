// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DynamicSchemaForm } from "./DynamicSchemaForm";

afterEach(cleanup);

describe("DynamicSchemaForm", () => {
  it("submits object fields as objects rather than strings", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          title: "Configuration",
          type: "object",
          properties: { config: { type: "object", title: "Config" } },
          required: ["config"],
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Config *"), {
      target: { value: '{"enabled":false}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenCalledWith({ config: { enabled: false } });
  });

  it("blocks invalid object JSON with a field error", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: { config: { type: "object", title: "Config" } },
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Config"), {
      target: { value: "{invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Enter a valid JSON object.")).toBeInTheDocument();
  });

  it("allows a required boolean to remain false", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: { enabled: { type: "boolean", title: "Enabled" } },
          required: ["enabled"],
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenCalledWith({ enabled: false });
  });

  it("resolves nullable numeric anyOf fields", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: {
            threshold: {
              title: "Threshold",
              anyOf: [{ type: "number" }, { type: "null" }],
            },
          },
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    const input = screen.getByLabelText("Threshold");
    expect(input).toHaveAttribute("type", "number");
    fireEvent.change(input, { target: { value: "0.75" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenCalledWith({ threshold: 0.75 });
  });
});
