/**
 * In-memory WebSocket double. It records what the client sent and lets a test
 * push frames back, so the client's protocol logic (identity, serialization,
 * correlation, deduplication) is testable without a server.
 */

export interface SentMessage {
  readonly url: string;
  readonly data: string;
}

export class FakeSocket {
  static instances: FakeSocket[] = [];

  readyState = 0;
  binaryType = "blob";
  readonly sent: SentMessage[] = [];
  readonly urls: string[] = [];
  readonly url: string;
  closed: { code?: number; reason?: string } | null = null;
  sendError: Error | null = null;
  private listeners = new Map<string, ((event: unknown) => void)[]>();

  constructor(url: string) {
    this.url = url;
    this.urls.push(url);
    FakeSocket.instances.push(this);
  }

  static reset(): void {
    FakeSocket.instances = [];
  }

  static get last(): FakeSocket {
    const socket = FakeSocket.instances[FakeSocket.instances.length - 1];
    if (socket === undefined) {
      throw new Error("no FakeSocket was created");
    }
    return socket;
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    const existing = this.listeners.get(type) ?? [];
    existing.push(listener);
    this.listeners.set(type, existing);
  }

  send(data: string): void {
    if (this.sendError !== null) {
      throw this.sendError;
    }
    this.sent.push({ url: this.url, data });
  }

  close(code?: number, reason?: string): void {
    this.closed = { code, reason };
    if (this.readyState === 3) {
      return;
    }
    this.readyState = 3;
    this.emit("close", { code: code ?? 1000, reason: reason ?? "" });
  }

  open(): void {
    this.readyState = 1;
    this.emit("open", {});
  }

  /** Delivers a raw text frame, exactly as a server would. */
  pushRaw(text: string): void {
    this.emit("message", { data: text });
  }

  /** Delivers a binary frame, as the Core adapter also accepts. */
  emitBinary(data: ArrayBuffer): void {
    this.emit("message", { data });
  }

  /** Delivers a response frame for a request the client already sent. */
  reply(
    requestId: string,
    method: string,
    result: unknown,
    options: { readonly ok?: boolean; readonly error?: unknown } = {},
  ): void {
    const ok = options.ok ?? true;
    this.pushRaw(
      JSON.stringify({
        kind: "response",
        payload: {
          id: requestId,
          method,
          version: "v1",
          ok,
          result: ok ? result : null,
          error: ok ? null : (options.error ?? { code: "internal_error", message: "boom" }),
        },
      }),
    );
  }

  /** Delivers an event frame. */
  event(id: string, type: string, userId: string, payload: unknown = {}): void {
    this.pushRaw(
      JSON.stringify({
        kind: "event",
        payload: {
          id,
          type,
          timestamp: "2026-09-25T10:00:00Z",
          user_id: userId,
          source: { provider: "test" },
          payload,
        },
      }),
    );
  }

  get lastRequestId(): string {
    const last = this.sent[this.sent.length - 1];
    if (last === undefined) {
      throw new Error("no request was sent");
    }
    return (JSON.parse(last.data) as { id: string }).id;
  }

  requestAt(index: number): { id: string; method: string; params?: Record<string, unknown> } {
    const entry = this.sent[index];
    if (entry === undefined) {
      throw new Error(`no request at index ${index}`);
    }
    return JSON.parse(entry.data) as {
      id: string;
      method: string;
      params?: Record<string, unknown>;
    };
  }

  private emit(type: string, event: unknown): void {
    for (const listener of [...(this.listeners.get(type) ?? [])]) {
      listener(event);
    }
  }
}

/** Factory usable as `options.socketFactory`, with optional auto-open. */
export function fakeSocketFactory(options: { readonly autoOpen?: boolean } = {}): (url: string) => FakeSocket {
  const autoOpen = options.autoOpen ?? false;
  return (url: string): FakeSocket => {
    const socket = new FakeSocket(url);
    if (autoOpen) {
      setImmediate(() => {
        socket.open();
      });
    }
    return socket;
  };
}

/** Lets queued microtasks (client promise chains) run. */
export async function flush(times = 4): Promise<void> {
  for (let index = 0; index < times; index += 1) {
    await new Promise<void>((resolve) => {
      setImmediate(resolve);
    });
  }
}
