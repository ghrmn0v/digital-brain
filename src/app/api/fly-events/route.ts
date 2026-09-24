import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { withApiErrors } from "@/lib/api/response";
import type { NormalizedEvent } from "@/lib/events";
import { PRODUCT_EVENTS, eventBus } from "@/lib/events/event-bus";
import { integrationEventService } from "@/modules/events";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async () => {
    authorizeRequest(request);

    const encoder = new TextEncoder();
    let closeStream: (() => void) | undefined;

    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        let closed = false;
        const seen = new Set<string>();
        let unsubscribe: () => void = () => {};

        const send = (event: NormalizedEvent) => {
          if (closed || seen.has(event.id)) return;
          seen.add(event.id);
          controller.enqueue(
            encoder.encode(
              `id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`,
            ),
          );
        };
        const cleanup = () => {
          if (closed) return;
          closed = true;
          unsubscribe();
          clearInterval(heartbeat);
          try {
            controller.close();
          } catch {}
        };

        unsubscribe = eventBus.on(PRODUCT_EVENTS.CONNECTOR_EVENT, send);
        const heartbeat = setInterval(() => {
          if (!closed) controller.enqueue(encoder.encode(": heartbeat\n\n"));
        }, 15_000);

        request.signal.addEventListener("abort", cleanup, { once: true });
        closeStream = cleanup;

        try {
          const recent = await integrationEventService.recent(100);
          for (const event of recent) send(event.normalized);
        } catch {
          cleanup();
        }
      },
      cancel() {
        closeStream?.();
      },
    });

    return new Response(stream, {
      headers: {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-cache, no-transform",
        connection: "keep-alive",
        "x-accel-buffering": "no",
      },
    });
  });
}
