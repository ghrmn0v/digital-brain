import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";
import { apiData, withApiErrors } from "@/lib/api/response";
import { parseJsonBody } from "@/lib/api/request";

/**
 * Server-side proxy to the Core Brain's `chat` method.
 *
 * This route exists for a concrete reason: the browser cannot reach the Brain
 * directly. The Brain is a loopback service on a different port that sends no
 * CORS headers, so a client-side `fetch` to it would be blocked before it left
 * the page. Going through the server also keeps the Brain's address and the
 * owner's user id out of the client bundle.
 *
 * Nothing is invented here. The request is the Brain's own `ChatParams` and the
 * response is its own `ChatResultWire`, passed through untouched so the page
 * can show what the Brain actually said, how confident it was, which memories
 * it used and — when the model was unavailable — why.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const chatRequestSchema = z.object({
  message: z.string().trim().min(1).max(2_000),
  userId: z.string().trim().min(1).max(512).optional(),
  sessionId: z.string().trim().max(256).optional(),
  /** Optional reading aid: what the reader was looking at when they asked. */
  contextLabel: z.string().trim().max(200).optional(),
});

const TIMEOUT_MS = 60_000;

interface BrainEnvelope {
  ok?: boolean;
  result?: unknown;
  error?: { code?: string; message?: string } | null;
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { message, sessionId, contextLabel } = await parseJsonBody(
      request,
      chatRequestSchema,
    );

    const brainUrl = process.env.CORE_BRAIN_URL?.trim();
    if (!brainUrl) {
      throw new ApiError(
        503,
        "BRAIN_NOT_CONFIGURED",
        "CORE_BRAIN_URL is not set on the server, so the Brain cannot be reached.",
      );
    }

    const userId =
      process.env.CORE_BRAIN_USER_ID?.trim() || "local-user";

    // The context label is only a reading aid, so it is appended to the question
    // rather than sent as a field the Brain does not know about. It carries no
    // authority: the Brain still answers only from stored memory.
    const question = contextLabel
      ? `${message}\n\n(Asked while looking at: ${contextLabel})`
      : message;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(brainUrl, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "idempotency-key": `chat-${requestId}`,
        },
        body: JSON.stringify({
          id: `chat-${requestId}`,
          method: "chat",
          version: "v1",
          params: {
            user_id: userId,
            message: question,
            ...(sessionId ? { session_id: sessionId } : {}),
          },
        }),
        signal: controller.signal,
        cache: "no-store",
      });

      const text = await response.text();

      let envelope: BrainEnvelope;
      try {
        envelope = JSON.parse(text) as BrainEnvelope;
      } catch {
        throw new ApiError(
          502,
          "BRAIN_BAD_RESPONSE",
          "The Brain returned a response that was not valid JSON.",
          { cause: new Error(text.slice(0, 200)) },
        );
      }

      if (!response.ok) {
        throw new ApiError(
          502,
          "BRAIN_ERROR",
          envelope.error?.message ??
            `The Brain answered with HTTP ${response.status}.`,
          { details: envelope },
        );
      }

      return apiData(envelope, requestId);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      const aborted =
        error instanceof Error && error.name === "AbortError";
      throw new ApiError(
        aborted ? 504 : 502,
        aborted ? "BRAIN_TIMEOUT" : "BRAIN_UNREACHABLE",
        aborted
          ? `The Brain did not answer within ${TIMEOUT_MS / 1000} seconds.`
          : "The Brain could not be reached. Check that it is running.",
        { cause: error },
      );
    } finally {
      clearTimeout(timer);
    }
  });
}
