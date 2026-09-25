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
  assert.equal(methods.length, 17);
  assert.ok(methods.includes("people_timeline"));
  assert.ok(methods.includes("resolve_person"));
  assert.ok("people_timeline" in (result.schemas ?? {}));
  assert.ok("resolve_person" in (result.schemas ?? {}));
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

test("a name-only subject is resolved by Core into a named person", async () => {
  await client.call("ingest", {
    event: {
      ...event("evt_named_1", "usr_ali", "see you tomorrow"),
      subject: { person_name: "Ali Ahmadov" },
    },
  });
  const summary = await client.call("people_summary");
  const ali = (summary.people ?? []).find((person) => person.name === "Ali Ahmadov");
  assert.ok(ali !== undefined, "the resolved person should carry the connector's name");
  assert.equal(ali.mention_count, 1);

  await client.call("ingest", {
    event: {
      ...event("evt_named_2", "usr_ali", "call me back"),
      subject: { person_name: "  ali   ahmadov " },
    },
  });
  const after = await client.call("people_summary");
  const sameAli = (after.people ?? []).filter((person) => person.name === "Ali Ahmadov");
  assert.equal(sameAli.length, 1, "the same name must converge on one person");
  assert.equal(sameAli[0]?.mention_count, 2);
});

test("resolve_person creates a person once and reuses it afterwards", async () => {
  const first = await client.call("resolve_person", { name: "Bəkir Əhmədov" });
  assert.equal(first.user_id, "usr_ali");
  assert.equal(first.created, true);
  assert.equal(first.ambiguous, false);
  assert.ok((first.person_id ?? "").startsWith("per_"));
  assert.ok((first.memory_id ?? "").length > 0);

  const again = await client.call("resolve_person", { name: "  bəkir   ƏHMƏDOV " });
  assert.equal(again.person_id, first.person_id);
  assert.equal(again.created, false);
  assert.equal(again.memory_id ?? null, null);
});

test("resolve_person accepts aliases and resolves through them", async () => {
  const created = await client.call("resolve_person", {
    name: "Nigar Rahimova",
    aliases: ["Nigar", "Niqa"],
  });
  assert.deepEqual(created.aliases, ["Nigar", "Niqa"]);
  const byAlias = await client.call("resolve_person", { name: "Niqa" });
  assert.equal(byAlias.person_id, created.person_id);
  assert.equal(byAlias.created, false);
});

test("resolve_person reports an ambiguous name without inventing an id", async () => {
  await client.call("resolve_person", { name: "Murad" });
  // A second, connector-owned person that also answers to "Murad".
  const shadow = await client.call("ingest", {
    event: {
      ...event("evt_shadow", "usr_ali", "another murad"),
      subject: { person_id: "per_connector_murad", person_name: "Murad" },
    },
  });
  assert.ok(shadow.event_id.length > 0);

  const ambiguous = await client.call("resolve_person", { name: "Murad" });
  assert.equal(ambiguous.ambiguous, true);
  assert.equal(ambiguous.person_id ?? null, null);
  assert.equal(ambiguous.created, false);
  assert.ok((ambiguous.candidates ?? []).includes("per_connector_murad"));
  assert.ok((ambiguous.candidates ?? []).length >= 2);
});

test("resolve_person keeps users isolated", async () => {
  const other = new HttpBrainClient({ baseUrl: server.baseUrl, userId: "usr_bəkir" });
  try {
    const mine = await client.call("resolve_person", { name: "Sevinc" });
    const theirs = await other.call("resolve_person", { name: "Sevinc" });
    assert.notEqual(mine.person_id, theirs.person_id);
    const summary = await client.call("people_summary");
    const ids = (summary.people ?? []).map((person) => person.person_id);
    assert.ok(ids.includes(mine.person_id ?? ""));
    assert.ok(!ids.includes(theirs.person_id ?? ""));
  } finally {
    other.close();
  }
});

test("resolve_person rejects an invalid name with the canonical code", async () => {
  await assert.rejects(
    () => client.call("resolve_person", { name: "   " }),
    (error: unknown) => {
      assert.ok(error instanceof BrainApiError);
      assert.equal(error.typedCode, "validation_error");
      return true;
    },
  );
});

test("the injected identity reaches resolve_person", async () => {
  const injected = new HttpBrainClient({ baseUrl: server.baseUrl, userId: "usr_nigar" });
  try {
    const resolution = await injected.call("resolve_person", { name: "Tural" });
    assert.equal(resolution.user_id, "usr_nigar");
    const summary = await injected.call("people_summary");
    assert.equal(summary.user_id, "usr_nigar");
    assert.equal(summary.people?.[0]?.name, "Tural");
  } finally {
    injected.close();
  }
});

test("HTTP client advertises that it has no event stream", () => {
  assert.equal(client.supportsEvents, false);
});
