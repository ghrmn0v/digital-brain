/**
 * Minimal RFC 6455 server used only as a test fixture.
 *
 * The real Core WebSocket adapter (`core/transport/websocket.py`) needs the
 * `websockets` package, which is not installed in this environment, so this
 * tiny spec-compliant server is what lets the client be exercised over a real
 * TCP socket with Node's native `WebSocket`: handshake, `user_id` admission,
 * masked client frames, text/binary server frames and the close handshake.
 *
 * It is NOT a Brain implementation: it answers every request from a canned map
 * and pushes one event per `emit_event` request.
 */

import { createHash } from "node:crypto";
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { Duplex } from "node:stream";

const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

export interface WsTestServer {
  readonly url: string;
  /** The `user_id` query value the client sent, or `null` for a rejected handshake. */
  readonly admittedUserId: string | null;
  readonly rejectedPaths: string[];
  readonly requests: unknown[];
  stop(): Promise<void>;
}

interface Frame {
  readonly opcode: number;
  readonly payload: Buffer;
}

function accept(key: string | undefined): string | null {
  if (key === undefined) {
    return null;
  }
  return createHash("sha1")
    .update(key + GUID)
    .digest("base64");
}

function encodeFrame(opcode: number, payload: Buffer): Buffer {
  const length = payload.length;
  let header: Buffer;
  if (length < 126) {
    header = Buffer.alloc(2);
    header[1] = length;
  } else if (length < 65_536) {
    header = Buffer.alloc(4);
    header[1] = 126;
    header.writeUInt16BE(length, 2);
  } else {
    header = Buffer.alloc(10);
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(length), 2);
  }
  header[0] = 0x80 | opcode;
  return Buffer.concat([header, payload]);
}

class FrameReader {
  private buffer = Buffer.alloc(0);
  private readonly handlers: ((frame: Frame) => void)[] = [];

  constructor(socket: Duplex) {
    socket.on("data", (chunk: Buffer) => {
      this.buffer = Buffer.concat([this.buffer, chunk]);
      this.drain();
    });
  }

  private drain(): void {
    for (;;) {
      if (this.buffer.length < 2) {
        return;
      }
      const first = this.buffer[0] ?? 0;
      const second = this.buffer[1] ?? 0;
      const opcode = first & 0x0f;
      const masked = (second & 0x80) !== 0;
      let length = second & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (this.buffer.length < offset + 2) {
          return;
        }
        length = this.buffer.readUInt16BE(offset);
        offset += 2;
      } else if (length === 127) {
        if (this.buffer.length < offset + 8) {
          return;
        }
        length = Number(this.buffer.readBigUInt64BE(offset));
        offset += 8;
      }
      let mask: Buffer | null = null;
      if (masked) {
        if (this.buffer.length < offset + 4) {
          return;
        }
        mask = this.buffer.subarray(offset, offset + 4);
        offset += 4;
      }
      if (this.buffer.length < offset + length) {
        return;
      }
      const payload = Buffer.from(this.buffer.subarray(offset, offset + length));
      if (mask !== null) {
        for (let index = 0; index < payload.length; index += 1) {
          payload[index] = (payload[index] ?? 0) ^ (mask[index % 4] ?? 0);
        }
      }
      this.buffer = this.buffer.subarray(offset + length);
      this.deliver({ opcode, payload });
    }
  }


  onFrame(handler: (frame: Frame) => void): void {
    this.handlers.push(handler);
  }

  private deliver(frame: Frame): void {
    for (const handler of this.handlers) {
      handler(frame);
    }
  }
}

export async function startWsTestServer(): Promise<WsTestServer> {
  const state = {
    admittedUserId: null as string | null,
    rejectedPaths: [] as string[],
    requests: [] as unknown[],
  };

  const server: Server = createServer((_request, response) => {
    response.writeHead(426, { "content-type": "text/plain" });
    response.end("upgrade required");
  });

  server.on("upgrade", (request: IncomingMessage, socket: Duplex) => {
    const key = request.headers["sec-websocket-key"];
    const acceptValue = accept(typeof key === "string" ? key : undefined);
    if (acceptValue === null) {
      socket.destroy();
      return;
    }
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    if (url.pathname !== "/v1/brain") {
      state.rejectedPaths.push(url.pathname);
      socket.write("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n");
      socket.destroy();
      return;
    }
    const userId = url.searchParams.get("user_id");
    if (userId === null || userId === "") {
      state.rejectedPaths.push(url.pathname);
      socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
      socket.destroy();
      return;
    }
    state.admittedUserId = userId;
    socket.write(
      [
        "HTTP/1.1 101 Switching Protocols",
        "Upgrade: websocket",
        "Connection: Upgrade",
        `Sec-WebSocket-Accept: ${acceptValue}`,
        "",
        "",
      ].join("\r\n"),
    );
    const reader = new FrameReader(socket);
    reader.onFrame((frame) => {
      if (frame.opcode === 0x8) {
        socket.end(encodeFrame(0x8, Buffer.alloc(0)));
        return;
      }
      if (frame.opcode !== 0x1 && frame.opcode !== 0x2) {
        return;
      }
      const text = frame.payload.toString("utf8");
      let request: { id?: unknown; method?: unknown };
      try {
        request = JSON.parse(text) as { id?: unknown; method?: unknown };
      } catch {
        socket.write(
          encodeFrame(0x1, Buffer.from(JSON.stringify({ kind: "garbage" }), "utf8")),
        );
        return;
      }
      state.requests.push(request);
      const id = typeof request.id === "string" ? request.id : "";
      const method = typeof request.method === "string" ? request.method : "";
      if (method === "emit_event") {
        for (const event of cannedEvents(userId)) {
          socket.write(
            encodeFrame(0x1, Buffer.from(JSON.stringify({ kind: "event", payload: event }), "utf8")),
          );
        }
        socket.write(
          encodeFrame(
            0x1,
            Buffer.from(
              JSON.stringify({
                kind: "response",
                payload: { id, method, version: "v1", ok: true, result: { emitted: 2 }, error: null },
              }),
              "utf8",
            ),
          ),
        );
        return;
      }
      const result = cannedResult(method, userId);
      const ok = result !== null;
      socket.write(
        encodeFrame(
          0x1,
          Buffer.from(
            JSON.stringify({
              kind: "response",
              payload: {
                id,
                method,
                version: "v1",
                ok,
                result: ok ? result : null,
                error: ok ? null : { code: "unknown_method", message: `unknown method: ${method}` },
              },
            }),
            "utf8",
          ),
        ),
      );
    });
  });

  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      resolve();
    });
  });
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("could not bind the WebSocket test server");
  }

  return {
    url: `ws://127.0.0.1:${address.port}`,
    get admittedUserId(): string | null {
      return state.admittedUserId;
    },
    get rejectedPaths(): string[] {
      return state.rejectedPaths;
    },
    get requests(): unknown[] {
      return state.requests;
    },
    async stop(): Promise<void> {
      server.closeAllConnections();
      await new Promise<void>((resolve) => {
        server.close(() => {
          resolve();
        });
      });
    },
  };
}

function cannedEvents(userId: string): unknown[] {
  return [
    {
      id: "evt_live_1",
      type: "memory.created",
      timestamp: "2026-09-25T10:00:00Z",
      user_id: userId,
      source: { provider: "test" },
      payload: { correlation_id: "corr_live", memory_id: "mem_1" },
    },
    {
      id: "evt_live_2",
      type: "action.proposed",
      timestamp: "2026-09-25T10:00:01Z",
      user_id: userId,
      source: { provider: "test" },
      payload: { correlation_id: "corr_live" },
    },
  ];
}

function cannedResult(method: string, userId: string): unknown {
  switch (method) {
    case "ping":
      return { ok: true, service: "digital-brain", api_version: "v1" };
    case "preferences":
      return { user_id: userId, preferences: [], domains: [] };
    case "resolve_person":
      return {
        user_id: userId,
        name: "Ali Ahmadov",
        person_id: "per_ali_1a2b3c4d",
        aliases: [],
        created: true,
        ambiguous: false,
        candidates: [],
        memory_id: "mem_1",
      };
    case "people_timeline":
      return {
        user_id: userId,
        person_id: "per_ali",
        total_entries: 1,
        entries: [
          {
            person_id: "per_ali",
            memory_id: "mem_1",
            memory_type: "interaction",
            status: "active",
            statement: "Ali works at Acme",
            occurred_at: "2026-09-25T10:00:00Z",
            created_at: "2026-09-25T10:00:00Z",
            durability: "temporary",
            confidence: 0.9,
            importance: 0.5,
            provenance: { provider: "test" },
          },
        ],
        person_known: true,
        truncated: false,
        scan_truncated: false,
      };
    default:
      return null;
  }
}
