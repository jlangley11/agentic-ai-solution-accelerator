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

  it("rejects valid JSON that is not an object", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{ properties: { config: { type: "object", title: "Config" } } }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Config"), {
      target: { value: "[]" },
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

  it("omits an untouched optional boolean but preserves an explicit false", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: {
            include_archived: {
              type: "boolean",
              title: "Include archived",
            },
          },
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onSubmit).toHaveBeenLastCalledWith({});

    const checkbox = screen.getByLabelText("Include archived");
    fireEvent.click(checkbox);
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenLastCalledWith({ include_archived: false });
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

  it("omits empty optional non-null fields but preserves nullable fields", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: {
            nickname: { type: "string", title: "Nickname" },
            count: { type: "integer", title: "Count" },
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

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenCalledWith({ threshold: null });
  });

  it("rejects fractional values for integer fields", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{ properties: { count: { type: "integer", title: "Count" } } }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    const input = screen.getByLabelText("Count");
    expect(input).not.toHaveAttribute("aria-invalid");
    fireEvent.change(input, {
      target: { value: "1.5" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter a whole number.")).toBeInTheDocument();
  });

  it("validates numeric array items before submitting", () => {
    const onSubmit = vi.fn();
    render(
      <DynamicSchemaForm
        schema={{
          properties: {
            scores: {
              type: "array",
              title: "Scores",
              items: { type: "number" },
            },
          },
        }}
        busy={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Scores"), {
      target: { value: "1.5, not-a-number" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Enter comma-separated numbers.")).toBeInTheDocument();
  });

  it("uses a compact input for described short fields", () => {
    render(
      <DynamicSchemaForm
        schema={{
          properties: {
            company_name: {
              type: "string",
              title: "Company name",
              description: "The customer account.",
            },
            context_notes: {
              type: "string",
              title: "Context notes",
              description: "Additional context.",
            },
          },
        }}
        busy={false}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(screen.getByLabelText("Company name")).toHaveProperty("tagName", "INPUT");
    expect(screen.getByLabelText("Context notes")).toHaveProperty("tagName", "TEXTAREA");
  });
});
