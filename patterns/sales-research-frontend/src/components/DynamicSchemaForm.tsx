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

function allowsNull(property: JsonSchemaProperty): boolean {
  return (
    (Array.isArray(property.type) && property.type.includes("null"))
    || Boolean(property.anyOf?.some((item) => item.type === "null"))
  );
}

function arrayItemType(
  schema: JsonSchema,
  property: JsonSchemaProperty,
): string {
  return property.items ? fieldType(schema, property.items) : "string";
}

function isMultiline(name: string, property: JsonSchemaProperty): boolean {
  if (property.format) return false;
  if ((property.maxLength ?? 0) > 200) return true;
  return /(context|description|details|notes|query|prompt|instructions|summary)/i.test(
    name,
  );
}

function inputType(property: JsonSchemaProperty, type: string): string {
  if (type === "number" || type === "integer") return "number";
  if (property.format === "email") return "email";
  if (property.format === "uri" || property.format === "url") return "url";
  if (property.format === "date") return "date";
  if (property.format === "date-time") return "datetime-local";
  return "text";
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
  const [touched, setTouched] = useState<Set<string>>(() => new Set());

  function markTouched(name: string) {
    setTouched((current) => new Set(current).add(name));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const request: Record<string, unknown> = {};
    const nextErrors: Record<string, string> = {};
    for (const [name, property] of Object.entries(properties)) {
      const value = form[name];
      const type = fieldType(schema, property);
      const isRequired = required.has(name);
      const empty = (
        value === ""
        || value == null
        || (
          type === "object"
          && String(value).trim() === "{}"
          && !isRequired
        )
      );
      if (!isRequired && empty) {
        if (allowsNull(property)) request[name] = null;
        continue;
      }
      if (type === "boolean") {
        const resolved = resolveProperty(schema, property);
        const hasInitial = initialValues?.[name] !== undefined;
        if (
          !isRequired
          && !touched.has(name)
          && !hasInitial
          && resolved.default === undefined
        ) {
          continue;
        }
        request[name] = Boolean(value);
      }
      else if (type === "number" || type === "integer") {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
          nextErrors[name] = "Enter a valid number.";
        } else if (type === "integer" && !Number.isInteger(numeric)) {
          nextErrors[name] = "Enter a whole number.";
        } else {
          request[name] = numeric;
        }
      } else if (type === "array") {
        const itemType = arrayItemType(schema, property);
        const items = String(value ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        const converted = items.map((item) => {
          if (itemType === "number" || itemType === "integer") return Number(item);
          if (itemType === "boolean") return item.toLowerCase() === "true";
          return item;
        });
        if (
          (itemType === "number" || itemType === "integer")
          && converted.some(
            (item) =>
              typeof item !== "number"
              || !Number.isFinite(item)
              || (itemType === "integer" && !Number.isInteger(item)),
          )
        ) {
          nextErrors[name] = (
            itemType === "integer"
              ? "Enter comma-separated whole numbers."
              : "Enter comma-separated numbers."
          );
        } else {
          request[name] = converted;
        }
      } else if (type === "object") {
        try {
          const parsed = JSON.parse(String(value ?? "{}")) as unknown;
          if (
            typeof parsed !== "object"
            || parsed === null
            || Array.isArray(parsed)
          ) {
            nextErrors[name] = "Enter a valid JSON object.";
          } else {
            request[name] = parsed;
          }
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
          const helpId = resolved.description ? `field-${name}-help` : undefined;
          const errorId = errors[name] ? `field-${name}-error` : undefined;
          const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;
          const common = {
            id: `field-${name}`,
            required: isRequired,
            disabled: busy,
            "aria-describedby": describedBy,
            "aria-invalid": errors[name] ? true : undefined,
          };
          return (
            <div
              key={name}
              className={
                type === "object" || (type === "string" && isMultiline(name, resolved))
                  ? "form-field full"
                  : "form-field"
              }
            >
              <label htmlFor={common.id}>
                {label}
                {isRequired ? " *" : ""}
              </label>
              {type === "boolean" ? (
                <input
                  {...common}
                  required={false}
                  type="checkbox"
                  checked={Boolean(form[name])}
                  onChange={(event) => {
                    markTouched(name);
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.checked,
                    }));
                  }}
                />
              ) : options ? (
                <select
                  {...common}
                  value={String(form[name] ?? "")}
                  onChange={(event) => {
                    markTouched(name);
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }));
                  }}
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
                  onChange={(event) => {
                    markTouched(name);
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }));
                  }}
                />
              ) : type === "string" && isMultiline(name, resolved) ? (
                <textarea
                  {...common}
                  rows={3}
                  value={String(form[name] ?? "")}
                  onChange={(event) => {
                    markTouched(name);
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }));
                  }}
                />
              ) : (
                <input
                  {...common}
                  type={inputType(resolved, type)}
                  min={resolved.minimum}
                  max={resolved.maximum}
                  minLength={resolved.minLength}
                  maxLength={resolved.maxLength}
                  pattern={resolved.pattern}
                  step={type === "integer" ? 1 : type === "number" ? "any" : undefined}
                  value={String(form[name] ?? "")}
                  placeholder={type === "array" ? "comma-separated values" : undefined}
                  onChange={(event) => {
                    markTouched(name);
                    setForm((current) => ({
                      ...current,
                      [name]: event.target.value,
                    }));
                  }}
                />
              )}
              {resolved.description && (
                <small id={helpId} className="field-help">{resolved.description}</small>
              )}
              {errors[name] && (
                <small id={errorId} className="field-error">{errors[name]}</small>
              )}
            </div>
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
