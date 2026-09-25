/**
 * Live end-to-end tests against the real Core HTTP transport: the client
 * builds `ApiRequest` envelopes, `BrainApi` answers, and the canonical
 * `ApiResponse` comes back over the wire.
 */

import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import {
  BrainApiError,
  BrainContractError,
  HttpBrainClient,
  isBrainApiError,
  type NormalizedSourceEvent,
} from "../src/index.ts";
import { startBrainHttpServer, startSilentServer, type BrainHttpServer } from "./support/brain-server.ts";

let server: BrainHttpServer;
let client: HttpBrainClient;

before(async () => {
  server = await startBrainHttpServer();
  client = new HttpBrainClient({ baseUrl: server.baseUrl, userId: "usr_ali" });
});

after(async () => {
  client?.close();
  if (server !== undefined) {
    await server.stop();
  }
});

function event(id: string, userId: string, text: string, extra: Record<string, unknown> = {}): NormalizedSourceEvent {
  return {
    id,
    type: "source.whatsapp.message_received",
    timestamp: "2026-09-25T10:00:00Z",
    user_id: userId,
    source: { provider: "whatsapp", component: "test" },
    occurred_at: "2026-09-25T10:00:00Z",
    payload: { text, ...extra },
  };
}

test("health reports the static liveness payload", async () => {
  const health = await client.health();
  assert.equal(health.status, "ok");
  assert.equal(health.service, "digital-brain");
  assert.equal(health.api_version, "v1");
});

test("ping answers over HTTP", async () => {
  const result = await client.call("ping");
  assert.equal(result.api_version, "v1");
  assert.equal(result.service, "digital-brain");
});

test("describe exposes the v1 registry including people_timeline", async () => {
  const result = await client.call("describe");
  const methods = result.methods ?? [];
  assert.equal(methods.length, 16);
  assert.ok(methods.includes("people_timeline"));
  assert.ok("people_timeline" in (result.schemas ?? {}));
});

test("request ids are minted per client and echoed by the server", async () => {
  const response = await client.request("ping");
  assert.equal(response.ok, true);
  assert.match(response.id, /^brain-\d+$/);
  assert.equal(response.version, "v1");
});

test("ingest then read back the user preferences view", async () => {
  const ingested = await client.call("ingest", {
    event: event("evt_pref_1", "usr_ali", "I prefer Python and pytest"),
  });
  assert.ok(ingested.event_id.length > 0);
  assert.ok(ingested.events_emitted >= 0);

  const stored = await client.call("record_preference", {
    name: "language",
    value: "Python",
    domain: "language",
  });
  assert.equal(stored.name, "language");
  assert.equal(stored.value, "Python");
  assert.equal(stored.domain, "language");

  const preferences = await client.call("preferences");
  assert.equal(preferences.user_id, "usr_ali");
  const names = (preferences.preferences ?? []).map((entry) => entry.name);
  assert.ok(names.includes("language"));
});

test("people_timeline returns the source-traceable history", async () => {
  await client.call("ingest", {
    event: {
      ...event("evt_ali_1", "usr_ali", "Ali works at Acme as a backend engineer"),
      subject: { person_id: "per_ali_1", role: "colleague" },
    },
  });
  await client.call("ingest", {
    event: {
      ...event("evt_ali_2", "usr_ali", "Ali prefers tea, not coffee"),
      subject: { person_id: "per_ali_1", role: "colleague" },
    },
  });

  const summary = await client.call("people_summary");
  const ali = (summary.people ?? []).find((person) => person.person_id === "per_ali_1");
  assert.ok(ali !== undefined, "the ingested person should be a known person");
  assert.equal(ali.mention_count, 2);

  const timeline = await client.call("people_timeline", { person_id: "per_ali_1" });
  assert.equal(timeline.person_id, "per_ali_1");
  assert.equal(timeline.user_id, "usr_ali");
  assert.equal(timeline.person_known, true);
  assert.equal(timeline.total_entries, 2);
  assert.equal(timeline.truncated, false);
  const entries = timeline.entries ?? [];
  assert.equal(entries.length, 2);
  for (const entry of entries) {
    assert.equal(entry.person_id, "per_ali_1");
    assert.ok(entry.memory_id.length > 0);
    assert.equal(entry.provenance.provider, "whatsapp");
    assert.equal(entry.provenance.source_event_id?.startsWith("evt_ali_"), true);
    assert.equal(entry.durability, "temporary");
    assert.ok(entry.occurred_at.length > 0);
    assert.ok(entry.created_at.length > 0);
  }
});

test("people_timeline honours the limit and reports a known-but-empty person", async () => {
  const limited = await client.call("people_timeline", { person_id: "per_ali_1", limit: 1 });
  assert.equal((limited.entries ?? []).length, 1);
  assert.equal(limited.truncated, true);
  assert.equal(limited.total_entries, 2);

  const unknown = await client.call("people_timeline", { person_id: "per_does_not_exist" });
  assert.equal(unknown.person_known, false);
  assert.equal(unknown.total_entries, 0);
  assert.equal((unknown.entries ?? []).length, 0);
});

test("user isolation holds across two clients", async () => {
  const other = new HttpBrainClient({ baseUrl: server.baseUrl, userId: "usr_bəkir" });
  try {
    await other.call("record_preference", { name: "language", value: "Go" });
    const otherPreferences = await other.call("preferences");
    const otherValues = (otherPreferences.preferences ?? []).map((entry) => entry.value);
    assert.deepEqual(otherValues, ["Go"]);

    const aliPreferences = await client.call("preferences");
    const aliValues = (aliPreferences.preferences ?? []).map((entry) => entry.value);
    assert.ok(!aliValues.includes("Go"), "usr_ali must not see usr_bəkir's preference");
  } finally {
    other.close();
  }
});

test("an explicit conflicting user_id is rejected locally", async () => {
  await assert.rejects(
    () => client.call("preferences", { user_id: "usr_bəkir" }),
    (error: unknown) => {
      assert.ok(error instanceof BrainContractError);
      assert.equal(error.kind, "contract");
      return true;
    },
  );
});

test("a typed Brain failure becomes BrainApiError with the canonical code", async () => {
  await assert.rejects(
    () =>
      client.call("ingest", {
        event: { ...event("evt_bad_type", "usr_ali", "x"), type: "not-a-source-event" },
      }),
    (error: unknown) => {
      assert.ok(isBrainApiError(error));
      assert.ok(error instanceof BrainApiError);
      assert.equal(error.typedCode, "validation_error");
      assert.equal(error.error.code, "validation_error");
      return true;
    },
  );
});

test("an unknown method surfaces unknown_method", async () => {
  await assert.rejects(
    () => client.call("not_a_method" as never),
    (error: unknown) => {
      assert.ok(error instanceof BrainApiError);
      assert.equal(error.typedCode, "unknown_method");
      return true;
    },
  );
});

test("request() returns a failed envelope instead of throwing", async () => {
  const response = await client.request("not_a_method" as never);
  assert.equal(response.ok, false);
  assert.equal(response.error?.code, "unknown_method");
  assert.equal(response.result ?? null, null);
});

test("a non-Brain endpoint is a transport error, not a silent failure", async () => {
  const wrong = new HttpBrainClient({ baseUrl: `${server.baseUrl}/nope` });
  try {
    await assert.rejects(
      () => wrong.call("ping"),
      (error: unknown) => {
        assert.equal((error as { kind?: string }).kind, "transport");
        return true;
      },
    );
  } finally {
    wrong.close();
  }
});

test("a server that never answers surfaces a timeout", async () => {
  const silent = await startSilentServer();
  const stalled = new HttpBrainClient({
    baseUrl: silent.baseUrl,
    userId: "usr_ali",
    requestTimeoutMs: 150,
  });
  try {
    await assert.rejects(
      () => stalled.call("ping"),
      (error: unknown) => {
        assert.equal((error as { kind?: string }).kind, "transport");
        assert.equal((error as { code?: string }).code, "timeout");
        return true;
      },
    );
  } finally {
    stalled.close();
    await silent.stop();
  }
});

test("a refused connection is a transport error, not a timeout", async () => {
  const refused = new HttpBrainClient({
    baseUrl: "http://127.0.0.1:9",
    userId: "usr_ali",
    requestTimeoutMs: 5_000,
  });
  try {
    await assert.rejects(
      () => refused.call("ping"),
      (error: unknown) => {
        assert.equal((error as { kind?: string }).kind, "transport");
        assert.equal((error as { code?: string }).code, "network_error");
        return true;
      },
    );
  } finally {
    refused.close();
  }
});

test("a request timeout is not reported for a fast response", async () => {
  const fast = new HttpBrainClient({ baseUrl: server.baseUrl, requestTimeoutMs: 10_000 });
  try {
    const result = await fast.call("ping");
    assert.equal(result.api_version, "v1");
  } finally {
    fast.close();
  }
});

test("understand returns the deterministic fallback summary", async () => {
  const result = await client.call("understand", { corpus: "refactor the parser module" });
  assert.ok(result.intent.length > 0);
  assert.ok(result.summary.length > 0);
  assert.ok(result.confidence >= 0 && result.confidence <= 1);
});

test("HTTP client advertises that it has no event stream", () => {
  assert.equal(client.supportsEvents, false);
});
