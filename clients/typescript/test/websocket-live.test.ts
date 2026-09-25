/**
 * Live WebSocket tests: the real platform `WebSocket` against a real socket.
 *
 * The Core WebSocket adapter cannot be started here (the `websockets` package
 * is not installed and installing it is out of scope), so the server side is
 * the minimal RFC 6455 fixture in `support/ws-test-server.ts`. What these tests
 * prove is the client half: handshake, identity query, request framing,
 * response correlation, event delivery/deduplication and the close handshake.
 */

import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import {
  BrainApiError,
  WebSocketBrainClient,
  type BrainEvent,
} from "../src/index.ts";
import { startWsTestServer, type WsTestServer } from "./support/ws-test-server.ts";

let server: WsTestServer;
let client: WebSocketBrainClient;

before(async () => {
  server = await startWsTestServer();
  client = new WebSocketBrainClient({ url: server.url, userId: "usr_ali" });
});

after(async () => {
  await client?.close();
  await server?.stop();
});

test("the real WebSocket completes the handshake with the identity query", async () => {
  await client.connect();
  assert.equal(client.isConnected, true);
  assert.equal(client.readyState, 1);
  assert.equal(server.admittedUserId, "usr_ali");
});

test("a request travels over the socket and comes back typed", async () => {
  const result = await client.call("ping");
  assert.equal(result.api_version, "v1");
  assert.equal(result.service, "digital-brain");
  assert.equal(server.requests.length >= 1, true);
  const last = server.requests[server.requests.length - 1] as { method?: string };
  assert.equal(last.method, "ping");
});

test("identity is injected into ownership params on a real socket", async () => {
  const result = await client.call("preferences", {});
  assert.equal(result.user_id, "usr_ali");
  const last = server.requests[server.requests.length - 1] as { params?: Record<string, unknown> };
  assert.equal(last.params?.["user_id"], "usr_ali");
});

test("people_timeline comes back over the socket with provenance intact", async () => {
  const result = await client.call("people_timeline", { person_id: "per_ali" });
  assert.equal(result.person_known, true);
  const entry = (result.entries ?? [])[0];
  assert.ok(entry !== undefined);
  assert.equal(entry.provenance.provider, "test");
  assert.equal(entry.durability, "temporary");
});

test("resolve_person travels with the injected identity over a real socket", async () => {
  const result = await client.call("resolve_person", { name: "Ali Ahmadov" });
  assert.equal(result.user_id, "usr_ali");
  assert.equal(result.created, true);
  assert.equal(result.ambiguous, false);
  assert.equal(result.person_id, "per_ali_1a2b3c4d");
  const last = server.requests[server.requests.length - 1] as { params?: Record<string, unknown> };
  assert.equal(last.params?.["user_id"], "usr_ali", "the client identity is injected");
  assert.equal(last.params?.["name"], "Ali Ahmadov");
});

test("a conflicting identity for resolve_person is refused locally", async () => {
  const before = server.requests.length;
  await assert.rejects(
    () => client.call("resolve_person", { name: "Ali", user_id: "usr_bəkir" } as never),
    (error: unknown) => {
      assert.equal((error as { kind?: string }).kind, "identity");
      return true;
    },
  );
  assert.equal(server.requests.length, before, "nothing is sent over the wire");
});

test("events arrive before the response and are delivered once", async () => {
  const seen: BrainEvent[] = [];
  const unsubscribe = client.onEvent((event) => {
    seen.push(event);
  });
  try {
    await client.call("emit_event" as never);
    assert.deepEqual(seen.map((event) => event.id), ["evt_live_1", "evt_live_2"]);
    const correlations = new Set(seen.map((event) => client.correlationIdOf(event)));
    assert.deepEqual([...correlations], ["corr_live"]);
    assert.equal(client.stats.events.eventsDelivered, 2);
    assert.equal(client.stats.events.eventsDroppedDuplicate, 0);
  } finally {
    unsubscribe();
  }
});

test("an unknown method becomes BrainApiError over a real socket", async () => {
  await assert.rejects(
    () => client.call("nope" as never),
    (error: unknown) => {
      assert.ok(error instanceof BrainApiError);
      assert.equal(error.typedCode, "unknown_method");
      return true;
    },
  );
});

test("requests stay serialized on a real connection", async () => {
  const before = server.requests.length;
  const results = await Promise.all([
    client.call("ping"),
    client.call("preferences", {}),
    client.call("people_timeline", { person_id: "per_ali" }),
  ]);
  assert.equal(results.length, 3);
  assert.equal(server.requests.length - before, 3);
  const methods = server.requests.slice(before).map((entry) => (entry as { method: string }).method);
  assert.deepEqual(methods, ["ping", "preferences", "people_timeline"]);
});

test("a second connection is a separate identity", async () => {
  const other = new WebSocketBrainClient({ url: server.url, userId: "usr_bəkir" });
  try {
    await other.connect();
    const result = await other.call("preferences", {});
    assert.equal(result.user_id, "usr_bəkir");
  } finally {
    await other.close();
  }
});

test("close performs the closing handshake and refuses later requests", async () => {
  const local = new WebSocketBrainClient({ url: server.url, userId: "usr_ali" });
  await local.connect();
  await local.close(1000, "done");
  assert.equal(local.isConnected, false);
  assert.equal(local.readyState, 3);
  await assert.rejects(
    () => local.call("ping"),
    (error: unknown) => {
      assert.equal((error as { kind?: string }).kind, "closed");
      return true;
    },
  );
});
