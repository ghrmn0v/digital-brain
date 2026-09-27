import { NextRequest } from "next/server";
import { z } from "zod";
import { requireLocalUser } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  brainChatInputSchema,
  brainIngestInputSchema,
  brainPreferenceInputSchema,
  brainReasonInputSchema,
  brainResolvePersonInputSchema,
  brainSearchInputSchema,
  brainService,
  brainUnderstandInputSchema,
} from "@/modules/brain";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const requestSchema = z
  .object({
    method: z.enum([
      "chat",
      "search",
      "understand",
      "reason",
      "resolve_person",
      "record_preference",
      "analyze_developer",
      "ingest",
      "people_summary",
      "people_timeline",
      "preferences",
      "developer_preferences",
      "learning_status",
      "personalization_profile",
      "feedback_history",
      "build_context",
    ]),
    input: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

/**
 * A narrow, validated bridge to the Brain. Product never invents Brain params:
 * each accepted `input` shape is converted to the exact Brain contract here and
 * the Brain's own response is passed back untouched.
 */
export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    const { method, input } = await parseJsonBody(request, requestSchema, 200_000);
    const userId = brainService.userId();
    const result = await dispatch(method, input, userId);
    return apiData(result, requestId);
  });
}

async function dispatch(
  method: string,
  input: Record<string, unknown>,
  userId: string,
) {
  switch (method) {
    case "chat": {
      const parsed = brainChatInputSchema.parse(input);
      return brainService.call("chat", {
        user_id: userId,
        message: parsed.message,
        session_id: parsed.sessionId ?? null,
        record_learning: parsed.recordLearning,
      });
    }
    case "search": {
      const parsed = brainSearchInputSchema.parse(input);
      return brainService.call("search", {
        user_id: userId,
        text: parsed.text ?? null,
        importance_min: parsed.importanceMin ?? null,
        limit: parsed.limit,
      });
    }
    case "understand": {
      const parsed = brainUnderstandInputSchema.parse(input);
      return brainService.call("understand", { corpus: parsed.corpus });
    }
    case "reason":
    case "build_context": {
      const parsed = brainReasonInputSchema.parse(input);
      return brainService.call(method, {
        context: {
          user_id: userId,
          repository: parsed.repository,
          files: [
            {
              path: parsed.filePath,
              language: parsed.language,
              content: parsed.content,
            },
          ],
        },
        task: parsed.task ?? null,
      });
    }
    case "analyze_developer": {
      const parsed = brainReasonInputSchema.parse(input);
      return brainService.call("analyze_developer", {
        context: {
          user_id: userId,
          repository: parsed.repository,
          files: [
            {
              path: parsed.filePath,
              language: parsed.language,
              content: parsed.content,
            },
          ],
        },
        task: parsed.task ?? null,
        correlation_id: `product-${Date.now()}`,
      });
    }
    case "resolve_person": {
      const parsed = brainResolvePersonInputSchema.parse(input);
      return brainService.call("resolve_person", {
        user_id: userId,
        name: parsed.name,
        aliases: parsed.aliases,
      });
    }
    case "record_preference": {
      const parsed = brainPreferenceInputSchema.parse(input);
      return brainService.call("record_preference", {
        user_id: userId,
        preference: parsed.preference,
        value: parsed.value,
        domain: parsed.domain ?? null,
      });
    }
    case "ingest": {
      const parsed = brainIngestInputSchema.parse(input);
      const occurredAt = parsed.occurredAt ?? new Date().toISOString();
      return brainService.call("ingest", {
        event: {
          version: "v1",
          id: `product-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: parsed.type,
          timestamp: new Date().toISOString(),
          occurred_at: occurredAt,
          user_id: userId,
          source: { provider: parsed.provider },
          subject: parsed.personName ? { person_name: parsed.personName } : null,
          payload: parsed.payload,
        },
      });
    }
    default:
      return brainService.call(method as never, { user_id: userId } as never);
  }
}
