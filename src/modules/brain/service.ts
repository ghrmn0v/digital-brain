import "server-only";

import {
  HttpBrainClient,
  type ApiMethod,
  type ApiResponse,
  type JsonObject,
  type MethodParams,
  type MethodResult,
} from "@/lib/brain-client";
import {
  BRAIN_USER_ID,
  type BrainCapabilityDto,
  type BrainStatusDto,
} from "@/modules/brain/contracts";

function baseUrl(): string | null {
  const configured = process.env.CORE_BRAIN_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return process.env.NODE_ENV === "production" ? null : "http://127.0.0.1:8765";
}

function userId(): string {
  return process.env.CORE_BRAIN_USER_ID?.trim() || BRAIN_USER_ID.parse(undefined);
}

function client(): HttpBrainClient {
  const url = baseUrl();
  if (!url) {
    throw new Error("CORE_BRAIN_URL is required in production.");
  }
  return new HttpBrainClient({ baseUrl: url, userId: userId() });
}

/**
 * The Brain's own capability catalogue, grouped for presentation only.
 * `interactive` marks the methods the Product exposes as a real control.
 */
const CAPABILITIES: readonly BrainCapabilityDto[] = [
  {
    method: "chat",
    group: "converse",
    summary: "Ask the Brain a question. Grounded in memory, optional learning.",
    interactive: true,
  },
  {
    method: "understand",
    group: "understand",
    summary: "Extract intent, entities, topics and salience from free text.",
    interactive: true,
  },
  {
    method: "reason",
    group: "understand",
    summary: "Reason over a repository snapshot without proposing actions.",
    interactive: true,
  },
  {
    method: "search",
    group: "memory",
    summary: "Ranked retrieval over the Brain's long-term memory.",
    interactive: true,
  },
  {
    method: "build_context",
    group: "memory",
    summary: "Assemble a bounded, user-scoped context for a task.",
    interactive: false,
  },
  {
    method: "people_summary",
    group: "people",
    summary: "People, relationships and interaction references.",
    interactive: false,
  },
  {
    method: "people_timeline",
    group: "people",
    summary: "Chronological person history with provenance.",
    interactive: false,
  },
  {
    method: "resolve_person",
    group: "people",
    summary: "Resolve a person from a connector-supplied name or aliases.",
    interactive: true,
  },
  {
    method: "preferences",
    group: "preferences",
    summary: "Learned user preferences and evidence.",
    interactive: false,
  },
  {
    method: "developer_preferences",
    group: "preferences",
    summary: "Coding, testing and deployment preferences.",
    interactive: false,
  },
  {
    method: "record_preference",
    group: "preferences",
    summary: "Record a preference; re-recording supersedes the old one.",
    interactive: true,
  },
  {
    method: "learning_status",
    group: "preferences",
    summary: "Counted learning signals and topic affinities.",
    interactive: false,
  },
  {
    method: "personalization_profile",
    group: "preferences",
    summary: "Explainable assistance profile derived from learning.",
    interactive: false,
  },
  {
    method: "feedback_history",
    group: "preferences",
    summary: "Replay of recorded feedback signals.",
    interactive: false,
  },
  {
    method: "record_feedback",
    group: "preferences",
    summary: "Return an execution outcome so the Brain can learn from it.",
    interactive: false,
  },
  {
    method: "analyze_developer",
    group: "developer",
    summary: "Full developer pipeline: bugs, fixes, tests, review, deploy proposal.",
    interactive: true,
  },
  {
    method: "ingest",
    group: "ingest",
    summary: "Send a normalized source event into the Brain.",
    interactive: true,
  },
  {
    method: "ping",
    group: "system",
    summary: "Liveness check.",
    interactive: false,
  },
  {
    method: "describe",
    group: "system",
    summary: "Canonical method and schema registry.",
    interactive: false,
  },
];

export interface BrainCallResult<T = unknown> {
  readonly ok: boolean;
  readonly data: T | null;
  readonly error: string | null;
  readonly code: string | null;
}

function toCallResult<T>(response: ApiResponse<T>): BrainCallResult<T> {
  if (response.ok && response.result != null) {
    return { ok: true, data: response.result, error: null, code: null };
  }
  return {
    ok: false,
    data: null,
    error: response.error?.message ?? "Core Brain returned a failed response.",
    code: response.error?.code ?? null,
  };
}

export const brainService = {
  capabilities(): readonly BrainCapabilityDto[] {
    return CAPABILITIES;
  },

  async status(): Promise<BrainStatusDto> {
    const url = baseUrl();
    if (!url) {
      return {
        reachable: false,
        url: null,
        apiVersion: null,
        service: null,
        provider: null,
        methodCount: 0,
        capabilities: CAPABILITIES,
        error: "CORE_BRAIN_URL is not configured.",
      };
    }

    try {
      const api = client();
      const health = await api.health();
      const described = await api.call("describe", {});
      const methods = Array.isArray(described?.methods) ? described.methods : [];
      return {
        reachable: true,
        url,
        apiVersion: health.api_version ?? null,
        service: health.service ?? null,
        provider: readProvider(described),
        methodCount: methods.length,
        capabilities: CAPABILITIES,
        error: null,
      };
    } catch (caught) {
      return {
        reachable: false,
        url,
        apiVersion: null,
        service: null,
        provider: null,
        methodCount: 0,
        capabilities: CAPABILITIES,
        error: caught instanceof Error ? caught.message : "Brain is unreachable.",
      };
    }
  },

  /** Typed pass-through. `request()` never throws for a typed Brain failure. */
  async call<M extends ApiMethod>(
    method: M,
    params: MethodParams<M> | JsonObject,
  ): Promise<BrainCallResult<MethodResult<M>>> {
    try {
      const outcome = await client().request(method, params);
      return toCallResult<MethodResult<M>>(outcome);
    } catch (caught) {
      return {
        ok: false,
        data: null,
        error:
          caught instanceof Error
            ? caught.message
            : "Could not reach Core Brain.",
        code: null,
      };
    }
  },

  userId,
  baseUrl,
};

/** `describe` returns schemas, not a provider field; read it defensively. */
function readProvider(described: unknown): string | null {
  if (!described || typeof described !== "object") return null;
  const record = described as Record<string, unknown>;
  const direct = record.provider ?? record.llm_provider;
  if (typeof direct === "string" && direct.length > 0) return direct;
  return null;
}

export type { JsonObject };
