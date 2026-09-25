/**
 * WebSocket client protocol tests against an in-memory socket double.
 *
 * These cover exactly the rules the Core WebSocket adapter documents: identity
 * admission, one outstanding response, id correlation, event deduplication and
 * per-user filtering, plus the local failure modes.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  BrainApiError,
  BrainClientError,
  BrainContractError,
  WebSocketBrainClient,
  buildSocketUrl,
  type BrainEvent,
} from "../src/index.ts";
import { FakeSocket, fakeSocketFactory, flush } from "./support/fake-socket.ts";

test("the connection URL carries the identity query exactly once", () => {
  assert.equal(
    buildSocketUrl("ws://127.0.0.1:8766", "usr_ali"),
    "ws://127.0.0.1:8766/v1/brain?user_id=usr_ali",
  );
  assert.equal(
    buildSocketUrl("http://127.0.0.1:8766/", "usr_ali"),
    "ws://127.0.0.1:8766/v1/brain?user_id=usr_ali",
  );
  assert.equal(
    buildSocketUrl("wss://brain.example.test/v1/brain", "usr a/b"),
    "wss://brain.example.test/v1/brain?user_id=usr%20a%2Fb",
  );
});

test("identities the server would reject are rejected locally", () => {
  for (const bad of ["", " usr", "usr ", "usr\nali", "x".repeat(513), "usr\uD800ali"]) {
    assert.throws(
      () => new WebSocketBrainClient({ url: "ws://127.0.0.1:8766", userId: bad }),
      (error: unknown) => {
        assert.ok(error instanceof BrainContractError);
        assert.equal(error.kind, "identity");
        return true;
      },
      `expected "${bad}" to be rejected`,
    );
  }
});

test("connect opens once and is shared by concurrent callers", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory(),
  });
  const connecting = client.connect();
  await flush(1);
  assert.equal(FakeSocket.instances.length, 1);
  FakeSocket.last.open();
  const [first, second] = await Promise.all([connecting, client.connect()]);
  assert.equal(first, client);
  assert.equal(second, client);
  assert.equal(client.isConnected, true);
  assert.equal(client.readyState, 1);
  assert.equal(FakeSocket.instances.length, 1);
  await client.close();
});

test("a request is answered by the matching response frame", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory(),
  });
  const pending = client.call("ping");
  await flush(1);
  FakeSocket.last.open();
  await flush(1);
  const sent = FakeSocket.last.requestAt(0);
  assert.equal(sent.method, "ping");
  assert.equal(sent.id, "brain-1");
  FakeSocket.last.reply(sent.id, "ping", { ok: true, service: "digital-brain", api_version: "v1" });
  const result = await pending;
  assert.equal(result.service, "digital-brain");
  await client.close();
});

test("requests are serialized: the next send waits for the previous response", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory(),
  });
  const connecting = client.connect();
  await flush(1);
  FakeSocket.last.open();
  const first = client.call("ping");
  const second = client.call("preferences", {});
  await flush(2);
  assert.equal(FakeSocket.last.sent.length, 1, "only one request may be outstanding");
  FakeSocket.last.reply("brain-1", "ping", { ok: true });
  await first;
  await flush(2);
  assert.equal(FakeSocket.last.sent.length, 2, "the queued request is sent after the response");
  const queued = FakeSocket.last.requestAt(1);
  assert.equal(queued.method, "preferences");
  assert.equal(queued.params?.["user_id"], "usr_ali");
  FakeSocket.last.reply(queued.id, "preferences", { user_id: "usr_ali", preferences: [] });
  const preferences = await second;
  assert.equal(preferences.user_id, "usr_ali");
  await client.close();
});

test("the identity is injected into ownership params", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory(),
  });
  const connecting = client.connect();
  await flush(1);
  FakeSocket.last.open();
  const pending = client.call("people_timeline", { person_id: "per_ali" });
  await flush(2);
  const sent = FakeSocket.last.requestAt(0);
  assert.deepEqual(sent.params, { person_id: "per_ali", user_id: "usr_ali" });
  FakeSocket.last.reply(sent.id, "people_timeline", { user_id: "usr_ali", person_id: "per_ali", total_entries: 0 });
  await pending;
  await client.close();
});

test("a params.user_id that conflicts with the connection identity is refused locally", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  await assert.rejects(
    () => client.call("preferences", { user_id: "usr_bəkir" }),
    (error: unknown) => {
      assert.ok(error instanceof BrainContractError);
      assert.equal(error.kind, "identity");
      return true;
    },
  );
  assert.equal(FakeSocket.last.sent.length, 0, "nothing may be sent for a rejected request");
  await client.close();
});

test("a failed response becomes BrainApiError with the canonical code", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const failing = client.call("people_timeline", { person_id: "" });
  await flush(1);
  const sent = FakeSocket.last.requestAt(0);
  FakeSocket.last.reply(sent.id, "people_timeline", null, {
    ok: false,
    error: { code: "validation_error", message: "person_id is required", source: "BrainApi" },
  });
  await assert.rejects(failing, (error: unknown) => {
    assert.ok(error instanceof BrainApiError);
    assert.equal(error.typedCode, "validation_error");
    return true;
  });
  await client.close();
});

test("request() returns a failed envelope without throwing", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const pending = client.request("people_timeline", { person_id: "" });
  await flush(1);
  const sent = FakeSocket.last.requestAt(0);
  FakeSocket.last.reply(sent.id, "people_timeline", null, {
    ok: false,
    error: { code: "validation_error", message: "person_id is required" },
  });
  const response = await pending;
  assert.equal(response.ok, false);
  assert.equal(response.error?.code, "validation_error");
  await client.close();
});

test("events reach handlers once, in order, deduplicated by id", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const seen: BrainEvent[] = [];
  const unsubscribe = client.onEvent((event) => {
    seen.push(event);
  });
  FakeSocket.last.event("evt_1", "memory.created", "usr_ali", { memory_id: "mem_1" });
  FakeSocket.last.event("evt_2", "memory.updated", "usr_ali", { memory_id: "mem_2" });
  FakeSocket.last.event("evt_1", "memory.created", "usr_ali", { memory_id: "mem_1" });
  assert.deepEqual(seen.map((event) => event.id), ["evt_1", "evt_2"]);
  assert.equal(client.stats.events.eventsDroppedDuplicate, 1);
  assert.equal(client.stats.events.eventsDelivered, 2);

  unsubscribe();
  FakeSocket.last.event("evt_3", "memory.created", "usr_ali");
  assert.equal(seen.length, 2, "an unsubscribed handler stops receiving events");
  await client.close();
});

test("events for another user are dropped before any handler", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const seen: string[] = [];
  client.onEvent((event) => {
    seen.push(event.id);
  });
  FakeSocket.last.event("evt_foreign", "memory.created", "usr_bəkir");
  FakeSocket.last.event("evt_mine", "memory.created", "usr_ali");
  assert.deepEqual(seen, ["evt_mine"]);
  assert.equal(client.stats.events.eventsDroppedForeignUser, 1);
  await client.close();
});

test("the correlation id helper groups related events", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const groups = new Map<string, string[]>();
  client.onEvent((event) => {
    const key = client.correlationIdOf(event) ?? "none";
    groups.set(key, [...(groups.get(key) ?? []), event.id]);
  });
  FakeSocket.last.event("evt_a", "memory.created", "usr_ali", { correlation_id: "corr_1" });
  FakeSocket.last.event("evt_b", "action.proposed", "usr_ali", { correlation_id: "corr_1" });
  FakeSocket.last.event("evt_c", "decision.created", "usr_ali", {});
  assert.deepEqual(groups.get("corr_1"), ["evt_a", "evt_b"]);
  assert.deepEqual(groups.get("none"), ["evt_c"]);
  await client.close();
});

test("events emitted before a response still arrive first", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const order: string[] = [];
  client.onEvent((event) => {
    order.push(event.type);
  });
  const pending = client.call("ingest", {
    event: {
      id: "evt_1",
      type: "source.whatsapp.message_received",
      timestamp: "2026-09-25T10:00:00Z",
      user_id: "usr_ali",
      source: { provider: "whatsapp" },
      occurred_at: "2026-09-25T10:00:00Z",
      payload: { text: "hi" },
    },
  });
  await flush(1);
  const sent = FakeSocket.last.requestAt(0);
  FakeSocket.last.event("evt_m1", "memory.created", "usr_ali", { correlation_id: "corr_1" });
  FakeSocket.last.reply(sent.id, "ingest", { outcome: "accepted", event_id: "evt_1", user_id: "usr_ali", events_emitted: 1 });
  order.push("response");
  await pending;
  assert.deepEqual(order, ["memory.created", "response"]);
  await client.close();
});

test("malformed and non-frame payloads are ignored, not thrown", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const seen: string[] = [];
  client.onEvent((event) => {
    seen.push(event.id);
  });
  FakeSocket.last.pushRaw("not json at all");
  FakeSocket.last.pushRaw("[]");
  FakeSocket.last.pushRaw(JSON.stringify({ kind: "unknown", payload: {} }));
  FakeSocket.last.pushRaw(JSON.stringify({ kind: "event", payload: { id: "no_user" } }));
  FakeSocket.last.event("evt_ok", "memory.created", "usr_ali");
  assert.deepEqual(seen, ["evt_ok"]);
  assert.equal(client.stats.events.framesIgnored, 4);
  assert.equal(client.stats.events.eventsReceived, 1);
  await client.close();
});

test("a binary frame is decoded", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const seen: string[] = [];
  client.onEvent((event) => {
    seen.push(event.id);
  });
  const frame = JSON.stringify({
    kind: "event",
    payload: {
      id: "evt_bin",
      type: "memory.created",
      timestamp: "2026-09-25T10:00:00Z",
      user_id: "usr_ali",
      source: { provider: "test" },
      payload: {},
    },
  });
  FakeSocket.last.emitBinary(new TextEncoder().encode(frame).buffer);
  assert.deepEqual(seen, ["evt_bin"]);
  await client.close();
});

test("a request timeout rejects with a transport error", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    requestTimeoutMs: 30,
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  await assert.rejects(
    () => client.call("ping"),
    (error: unknown) => {
      assert.ok(error instanceof BrainClientError);
      assert.equal(error.kind, "transport");
      assert.equal(error.code, "timeout");
      return true;
    },
  );
  await client.close();
});

test("closing the socket rejects everything still in flight", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  const pending = client.call("ping");
  await flush(1);
  FakeSocket.last.close(1006, "gone");
  await assert.rejects(pending, (error: unknown) => {
    assert.ok(error instanceof BrainClientError);
    assert.equal(error.kind, "closed");
    return true;
  });
  assert.equal(client.isConnected, false);
  await client.close();
  await assert.rejects(
    () => client.call("ping"),
    (error: unknown) => {
      assert.equal((error as BrainClientError).kind, "closed");
      return true;
    },
  );
});

test("a send failure rejects the request and keeps the queue alive", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: fakeSocketFactory({ autoOpen: true }),
  });
  await client.connect();
  FakeSocket.last.sendError = new Error("socket is gone");
  await assert.rejects(
    () => client.call("ping"),
    (error: unknown) => {
      assert.equal((error as BrainClientError).code, "send_failed");
      return true;
    },
  );
  FakeSocket.last.sendError = null;
  const recovered = client.call("ping");
  await flush(1);
  const sent = FakeSocket.last.requestAt(0);
  FakeSocket.last.reply(sent.id, "ping", { ok: true });
  assert.equal((await recovered).ok, true);
  await client.close();
});

test("connect failure surfaces a transport error and no pending request", async () => {
  FakeSocket.reset();
  const client = new WebSocketBrainClient({
    url: "ws://127.0.0.1:8766",
    userId: "usr_ali",
    socketFactory: () => {
      throw new Error("ECONNREFUSED");
    },
  });
  await assert.rejects(
    () => client.call("ping"),
    (error: unknown) => {
      assert.equal((error as BrainClientError).kind, "transport");
      assert.equal((error as BrainClientError).code, "connect_failed");
      return true;
    },
  );
  assert.equal(client.stats.pendingRequests, 0);
});
