export interface JsonSchemaProperty {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  items?: JsonSchemaProperty;
  format?: string;
  anyOf?: JsonSchemaProperty[];
  $ref?: string;
  additionalProperties?: boolean | JsonSchemaProperty;
}

export interface JsonSchema {
  title?: string;
  description?: string;
  type?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  $defs?: Record<string, JsonSchemaProperty>;
}

export interface ScenarioOutputSection {
  key: string;
  label?: string;
  layout?: string;
}

export interface ScenarioMetadata {
  id: string;
  title: string;
  description: string;
  experience_kind: string;
  endpoint_path: string;
  request_schema: JsonSchema;
  response_schema: JsonSchema | null;
  agents: {
    id: string;
    foundry_name: string;
    grounding: string;
  }[];
  output_sections: ScenarioOutputSection[];
  approval: {
    mode: string;
    configured: boolean;
  };
  stream_contract: {
    validated_partial_event: string | null;
    final_event: string;
    terminal_event: string;
    unvalidated_chunk_event: string;
  };
}

type WithSeq<T> = T & { seq?: number };

export type GenericStreamEvent =
  | WithSeq<{ type: "status"; stage: string; stages?: string[][] }>
  | WithSeq<{ type: "worker_started"; worker_id: string; agent?: string }>
  | WithSeq<{ type: "partial"; worker_id: string; output: unknown }>
  | WithSeq<{ type: "worker_skipped"; worker_id: string; error?: string }>
  | WithSeq<{ type: "briefing_ready"; briefing: Record<string, unknown> }>
  | WithSeq<{ type: "tool_pending_approval"; tool: string; args?: Record<string, unknown> }>
  | WithSeq<{ type: "tool_skipped"; tool: string; reason: string }>
  | WithSeq<{ type: "tool_result"; tool: string; result: unknown }>
  | WithSeq<{ type: "tool_error"; tool: string; error: string }>
  | WithSeq<{ type: "final"; briefing: Record<string, unknown> }>
  | WithSeq<{ type: "error"; message: string }>
  | WithSeq<{ type: "done" }>
  | WithSeq<{ type: "chunk"; agent: string; worker_id?: string; delta: string }>
  | { type: "stream_interrupted"; last_seq: number; last_event?: string };

export interface WorkbenchHistoryItem {
  id: string;
  createdAt: string;
  request: Record<string, unknown>;
  briefing: Record<string, unknown>;
}
