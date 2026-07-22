import { useMemo, useState } from "react";
import type {
  JsonSchema,
  JsonSchemaProperty,
} from "../types/scenario";

interface Props {
  schema: JsonSchema;
  busy: boolean;
  initialValues?: Record<string, unknown>;
  onSubmit: (request: Record<string, unknown>) => void;
  onCancel: () => void;
}

function resolveProperty(
  schema: JsonSchema,
  property: JsonSchemaProperty,
): JsonSchemaProperty {
  let referenced: JsonSchemaProperty = {};
  if (property.$ref?.startsWith("#/$defs/")) {
    const name = property.$ref.slice("#/$defs/".length);
    referenced = schema.$defs?.[name] ?? {};
  }
  const alternative = property.anyOf?.find(
    (item) => item.type !== "null",
  );
  return {
    ...referenced,
    ...alternative,
    ...property,
    type: property.type ?? alternative?.type ?? referenced.type,
  };
}

function fieldType(schema: JsonSchema, property: JsonSchemaProperty): string {
  const resolved = resolveProperty(schema, property);
  if (Array.isArray(resolved.type)) {
    return resolved.type.find((item) => item !== "null") ?? "string";
  }
  return resolved.type ?? "string";
}

function enumValues(
  schema: JsonSchema,
  property: JsonSchemaProperty,
): unknown[] | undefined {
  const resolved = resolveProperty(schema, property);
  return resolved.enum;
}

function initialState(
  schema: JsonSchema,
  values?: Record<string, unknown>,
): Record<string, string | boolean> {
  const output: Record<string, string | boolean> = {};
  for (const [name, property] of Object.entries(schema.properties ?? {})) {
    const resolved = resolveProperty(schema, property);
    const value = values?.[name] ?? resolved.default;
    const type = fieldType(schema, property);
    if (type === "boolean") output[name] = Boolean(value);
    else if (type === "array" && Array.isArray(value)) output[name] = value.join(", ");
    else if (type === "object") {
      output[name] = JSON.stringify(value ?? {}, null, 2);
    }
    else output[name] = value == null ? "" : String(value);
  }
  return output;
}

function humanize(value: string): string {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function DynamicSchemaForm({
  schema,
  busy,
  initialValues,
  onSubmit,
  onCancel,
}: Props) {
  const properties = schema.properties ?? {};
  const required = useMemo(() => new Set(schema.required ?? []), [schema.required]);
  const [form, setForm] = useState(() => initialState(schema, initialValues));
  const [errors, setErrors] = useState<Record<string, string>>({});

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const request: Record<string, unknown> = {};
    const nextErrors: Record<string, string> = {};
    for (const [name, property] of Object.entries(properties)) {
      const value = form[name];
      const type = fieldType(schema, property);
      if (type === "boolean") request[name] = Boolean(value);
      else if (type === "number" || type === "integer") {
        request[name] = value === "" ? null : Number(value);
      } else if (type === "array") {
        request[name] = String(value ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
      } else if (type === "object") {
        try {
          request[name] = JSON.parse(String(value ?? "{}")) as unknown;
        } catch {
          nextErrors[name] = "Enter a valid JSON object.";
        }
      } else request[name] = String(value ?? "");
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    onSubmit(request);
  }

  return (
    <form className="card dynamic-form" onSubmit={submit}>
      <h2>{schema.title ?? "Request"}</h2>
      {schema.description && <p className="muted">{schema.description}</p>}
      <div className="grid">
        {Object.entries(properties).map(([name, property]) => {
          const resolved = resolveProperty(schema, property);
          const type = fieldType(schema, property);
          const options = enumValues(schema, property);
          const label = resolved.title ?? humanize(name);
          const isRequired = required.has(name);
          const common = {
            id: `field-${name}`,
            required: isRequired,
            disabled: busy,
          };
          return (
            <label
              key={name}
              className={
                type === "object" || (type === "string" && resolved.description)
                  ? "full"
                  : undefined
              }
            >
              <span>
                {label}
                {isRequired ? " *" : ""}
              </span>
              {type === "boolean" ? (
                <input
                  id={common.id}
                  disabled={common.disabled}
                  type="checkbox"
                  checked={Boolean(form[name])}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.checked,
                    }))
                  }
                />
              ) : options ? (
                <select
                  {...common}
                  value={String(form[name] ?? "")}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }))
                  }
                >
                  {!isRequired && <option value="">Select…</option>}
                  {options.map((option) => (
                    <option key={String(option)} value={String(option)}>
                      {String(option)}
                    </option>
                  ))}
                </select>
              ) : type === "object" ? (
                <textarea
                  {...common}
                  rows={6}
                  className="json-input"
                  value={String(form[name] ?? "{}")}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }))
                  }
                />
              ) : type === "string" && resolved.description ? (
                <textarea
                  {...common}
                  rows={3}
                  value={String(form[name] ?? "")}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }))
                  }
                />
              ) : (
                <input
                  {...common}
                  type={type === "number" || type === "integer" ? "number" : "text"}
                  value={String(form[name] ?? "")}
                  placeholder={type === "array" ? "comma-separated values" : undefined}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }))
                  }
                />
              )}
              {resolved.description && (
                <small className="field-help">{resolved.description}</small>
              )}
              {errors[name] && <small className="field-error">{errors[name]}</small>}
            </label>
          );
        })}
      </div>
      <div className="actions">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Running…" : "Run"}
        </button>
        {busy && (
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
