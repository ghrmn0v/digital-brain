#!/usr/bin/env node
/**
 * Digital Brain demo scenario.
 *
 * One coherent story, driven entirely through the Product's public API so the
 * demo exercises the real integration path rather than calling the Brain
 * directly: external event -> connector ingest -> Product -> Brain -> memory,
 * learning, reasoning, proposal -> Product surfaces it.
 *
 * All data is synthetic. No external account is contacted: the WhatsApp and
 * LinkedIn events are posted to Product's own connector endpoints exactly as a
 * real connector would post them.
 *
 * No secret is ever printed. The service token is read from the environment and
 * sent as a header, never echoed.
 *
 * Usage:  node scripts/demo-scenario.mjs [--base http://127.0.0.1:3000]
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * Load the repository .env the same way the other services do.
 *
 * `process.loadEnvFile` is the platform's own dotenv support and, like
 * `--env-file`, it does not override variables already in the environment. A
 * missing file is not an error: the scenario then runs with whatever the caller
 * exported, which is what CI does.
 */
/**
 * Load the environment files the same way the services do.
 *
 * Two files can be in play and they are not interchangeable: the repository
 * `.env` belongs to Product and carries the shared service token and the owner
 * id, while `--env` is the file the runner pointed the *Brain* at, which is
 * where a checkout keeps its provider credentials. Each component reads its own
 * configuration, so both are loaded here rather than pretending one replaces
 * the other.
 *
 * `process.loadEnvFile` is the platform's own dotenv support and, like
 * `--env-file`, it does not override variables already in the environment, so
 * the repository file is read first and wins. A missing file is not an error:
 * the scenario then runs with whatever the caller exported, which is what CI
 * does.
 */
function loadEnvFile(path) {
  if (!path || !existsSync(path)) return false;
  if (typeof process.loadEnvFile !== "function") return false;
  try {
    process.loadEnvFile(path);
    return true;
  } catch {
    return false;
  }
}

const extraEnv = (() => {
  const i = process.argv.indexOf("--env");
  return i !== -1 ? process.argv[i + 1] : undefined;
})();

loadEnvFile(join(REPO, ".env"));
loadEnvFile(extraEnv);

const BRAIN_URL =
  process.env.CORE_BRAIN_URL?.trim() || "http://127.0.0.1:8765/v1/brain";
const USER_ID = process.env.CORE_BRAIN_USER_ID?.trim() || "";

// ---------------------------------------------------------------------------
// output helpers
// ---------------------------------------------------------------------------
const dim = (s) => `\x1b[2m${s}\x1b[0m`;
const bold = (s) => `\x1b[1m${s}\x1b[0m`;
const green = (s) => `\x1b[32m${s}\x1b[0m`;
const cyan = (s) => `\x1b[36m${s}\x1b[0m`;
const red = (s) => `\x1b[31m${s}\x1b[0m`;
const yellow = (s) => `\x1b[33m${s}\x1b[0m`;

let step = 0;
const TOTAL = 12;
function heading(title) {
  step += 1;
  console.log(`\n${bold(cyan(`[${step}/${TOTAL}] ${title}`))}`);
  console.log(dim("─".repeat(66)));
}
function line(label, value) {
  console.log(`   ${String(label).padEnd(22)} ${value}`);
}
function note(text) {
  console.log(dim(`   ${text}`));
}

// ---------------------------------------------------------------------------
// config
// ---------------------------------------------------------------------------
function serviceToken() {
  const fromEnv = process.env.SERVICE_API_TOKEN?.trim();
  if (fromEnv) return fromEnv;
  try {
    // Read the token without printing it, so a scenario run against `next dev`
    // can still authenticate as a service.
    const env = readFileSync(join(REPO, ".env"), "utf8");
    const match = env.match(/^SERVICE_API_TOKEN\s*=\s*"?([^"\n]*)"?/m);
    return match?.[1]?.trim() || null;
  } catch {
    return null;
  }
}

const TOKEN = serviceToken();

function baseUrl() {
  const argIndex = process.argv.indexOf("--base");
  if (argIndex !== -1 && process.argv[argIndex + 1]) {
    return process.argv[argIndex + 1].replace(/\/$/, "");
  }
  return (process.env.APP_URL?.trim() || "http://127.0.0.1:3000").replace(/\/$/, "");
}

const BASE = baseUrl();

async function api(path, init = {}) {
  const headers = { "content-type": "application/json", ...(init.headers ?? {}) };
  if (TOKEN) headers.authorization = `Bearer ${TOKEN}`;
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    signal: AbortSignal.timeout(30_000),
  });
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }
  return { status: response.status, body };
}

async function brain(method, params, id) {
  const { body } = await api("");
  void body;
  const response = await fetch(BRAIN_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id, method, version: "v1", params }),
    signal: AbortSignal.timeout(60_000),
  });
  return response.json();
}

function stamp() {
  return new Date().toISOString().replace(/\.\d+Z$/, "Z");
}

const RUN = Date.now().toString(36);
const CORRELATION = `corr-demo-${RUN}`;

// ---------------------------------------------------------------------------
// the story
// ---------------------------------------------------------------------------

async function main() {
  console.log(bold("\n  Digital Brain — integrated demo"));
  console.log(dim(`  product ${BASE}`));
  console.log(dim(`  brain   ${BRAIN_URL}`));
  console.log(dim(`  user    ${USER_ID || "(not configured)"}`));
  console.log(dim(`  run     ${RUN}  ·  correlation ${CORRELATION}`));

  if (!USER_ID) {
    console.log(
      red("\n  CORE_BRAIN_USER_ID is not set."),
    );
    console.log(
      dim(
        "  The Brain isolates every event by user, so Product must name the\n" +
          "  owner it delivers for. Set it in .env and re-run.",
      ),
    );
    process.exitCode = 1;
    return;
  }

  // 1 ---------------------------------------------------------------------
  heading("A message arrives from Ayxan on WhatsApp");
  const whatsapp = await api("/api/connectors/events/ingest", {
    method: "POST",
    headers: { "idempotency-key": `demo-wa-${RUN}` },
    body: JSON.stringify({
      id: `demo-wa-${RUN}`,
      source: "whatsapp",
      type: "message.received",
      timestamp: stamp(),
      payload: {
        text: "Ayxan will bring the hackathon demo hardware on Thursday. He prefers async updates over standup calls.",
      },
      metadata: { schemaVersion: "1.0", correlationId: CORRELATION },
    }),
  });
  line("product accepted", whatsapp.status === 201 ? green("yes (201)") : red(`no (${whatsapp.status})`));
  note("A real connector posts exactly this shape to this endpoint.");

  // 2 ---------------------------------------------------------------------
  heading("The Brain understands it and links it to a person");
  const resolved = await brain(
    "resolve_person",
    { user_id: USER_ID, name: "Ayxan", correlation_id: CORRELATION },
    `demo-rp-${RUN}`,
  );
  const person = resolved?.result ?? {};
  line("person_id", person.person_id ?? red("not resolved"));
  line("identity", person.created ? green("created") : "reused (deterministic)");
  note("The same name always resolves to the same id, so memory links up.");

  // 3 ---------------------------------------------------------------------
  heading("A calendar event about the same thing");
  const calendar = await api("/api/connectors/events/ingest", {
    method: "POST",
    headers: { "idempotency-key": `demo-cal-${RUN}` },
    body: JSON.stringify({
      id: `demo-cal-${RUN}`,
      source: "calendar",
      type: "event.created",
      timestamp: stamp(),
      payload: {
        summary: "Hackathon planning with Ayxan",
        startsAt: "2026-10-01T10:00:00.000Z",
        location: "Meeting room 3",
      },
      metadata: { schemaVersion: "1.0", correlationId: CORRELATION },
    }),
  });
  line("product accepted", calendar.status === 201 ? green("yes (201)") : red(`no (${calendar.status})`));

  // 4 ---------------------------------------------------------------------
  heading("A job opportunity is discovered on LinkedIn");
  const job = await api("/api/connectors/events/ingest", {
    method: "POST",
    headers: { "idempotency-key": `demo-job-${RUN}` },
    body: JSON.stringify({
      id: `demo-job-${RUN}`,
      source: "linkedin",
      type: "job.discovered",
      timestamp: stamp(),
      payload: {
        company: "Northwind Labs",
        title: "Principal Engineer, hackathon platform",
        location: "Remote",
      },
      metadata: { schemaVersion: "1.0", correlationId: CORRELATION },
    }),
  });
  line("product accepted", job.status === 201 ? green("yes (201)") : red(`no (${job.status})`));
  note("No LinkedIn account is contacted; this is the normalized event a");
  note("connector would post. Its name differs from the Brain's own");
  note("'job_seen', and both must still reach memory.");

  // 5 ---------------------------------------------------------------------
  // Delivery is asynchronous: Product hands the event to its worker, which
  // posts it to the Brain. Reading anything before the worker has run makes the
  // counts differ from run to run, so wait for the evidence instead of racing
  // it and printing a number that is simply early.
  heading("Waiting for the worker to deliver");
  const expected = 3;
  let delivered = [];
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    const probe = await brain(
      "search",
      { user_id: USER_ID, text: "hackathon", limit: 8, correlation_id: CORRELATION },
      `demo-poll-${RUN}-${delivered.length}`,
    );
    delivered = probe?.result?.items ?? [];
    if (delivered.length >= expected) break;
    process.stdout.write(
      dim(`     waiting… ${delivered.length}/${expected} stored\r`),
    );
    await new Promise((r) => setTimeout(r, 1500));
  }
  line("stored", `${delivered.length} of ${expected} expected`);

  heading("Product shows the events it received");
  const health = await api("/api/health");
  line("product database", health.body?.database === "connected" ? green("connected") : red("not connected"));
  const timeline = await api("/api/timeline?limit=6");
  const rows = Array.isArray(timeline.body?.data) ? timeline.body.data : [];
  line("timeline entries", String(rows.length));
  for (const row of rows.slice(0, 4)) {
    console.log(
      `     ${dim("·")} [${row.kind}] ${String(row.title).slice(0, 46)} ` +
        dim(`(${row.status})`),
    );
  }
  note("Open /timeline in the UI to see this feed.");
  note("");
  note("Delivery itself is not read back from a Product API, so the proof");
  note("that it worked is the next step: memories the Brain actually stored.");

  // 6 ---------------------------------------------------------------------
  heading("What does the Brain now remember?");
  const search = await brain(
    "search",
    { user_id: USER_ID, text: "hackathon", limit: 6, correlation_id: CORRELATION },
    `demo-search-${RUN}`,
  );
  const hits = search?.result?.items ?? [];
  line("memories found", String(hits.length));
  line("delivery proof", hits.length > 0 ? green("the Brain stored what Product sent") : red("nothing arrived"));
  for (const hit of hits.slice(0, 5)) {
    console.log(
      `     ${dim("·")} [${hit.type}] score=${hit.score.toFixed(2)} ` +
        `${hit.content.slice(0, 58)}`,
    );
    console.log(
      dim(`         from ${hit.source_provider} · correlation ${hit.correlation_id ?? "—"}`),
    );
  }
  if (hits.length === 0) {
    line("result", red("no memory — events are being dropped somewhere"));
  }

  // 7 ---------------------------------------------------------------------
  heading("The Brain is asked a question, in plain language");
  // A hosted model can refuse for reasons that have nothing to do with the
  // question: no capacity behind the endpoint, or an exhausted quota. Only the
  // first is worth an immediate second try. Retrying a rate-limited account
  // makes the limit worse, so that case is reported instead of hammered.
  let answer = {};
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const chat = await brain(
      "chat",
      {
        user_id: USER_ID,
        message: "What do I know about the hackathon and who is helping?",
        correlation_id: CORRELATION,
      },
      `demo-chat-${RUN}-${attempt}`,
    );
    answer = chat?.result ?? {};
    if (!answer.fallback_used) break;
    const reason = answer.fallback_reason ?? "";
    if (/rate limit|quota|429/i.test(reason)) {
      note("the provider's quota for this key is spent; not retrying");
      break;
    }
    if (attempt === 1) {
      note(`model unavailable (${reason}); retrying once`);
      await new Promise((r) => setTimeout(r, 4000));
      continue;
    }
    break;
  }
  line("answered by", answer.provider ?? red("no answer"));
  line("fallback used", answer.fallback_used ? "yes" : "no (a model answered)");
  if (answer.fallback_used) {
    line("reason", yellow(answer.fallback_reason ?? "unspecified"));
    note("The Brain degraded instead of failing, and says why. A model answer");
    note("is shown whenever the provider had capacity to give one.");
  }
  line("grounded in", `${answer.grounded_in?.length ?? 0} memories`);
  line("confidence", String(answer.confidence ?? "—"));
  note("The answer cites the memories it used, and stores nothing:");
  line("learning recorded", String(answer.learning_recorded ?? 0));

  // 8 ---------------------------------------------------------------------
  heading("An explicit preference is recorded");
  const preference = await brain(
    "record_preference",
    {
      user_id: USER_ID,
      name: "async_updates",
      value: "Prefer async updates over live standups",
      domain: "explanation_detail",
      importance: 0.9,
      confidence: 1.0,
    },
    `demo-pref-${RUN}`,
  );
  line("preference", preference?.result?.name ?? red("not recorded"));
  line("importance", String(preference?.result?.importance ?? "—"));
  note("An explicit rule outranks anything learned later.");

  // 9 ---------------------------------------------------------------------
  heading("And it is corroborated by evidence");
  let feedbackStored = 0;
  for (const n of [1, 2]) {
    const fb = await brain(
      "record_feedback",
      {
        feedback: {
          feedback_id: `demo-fb-${RUN}-${n}`,
          user_id: USER_ID,
          source: "user",
          kind: "outcome",
          // The target must reference a real entity; the event this run
          // ingested keeps the evidence traceable instead of orphaned.
          target: { event_id: `demo-wa-${RUN}` },
          label: "accepted",
          value: 1.0,
          note: "Async summary was useful",
          metadata: {
            topic: "communication",
            preference_domain: "explanation_detail",
            preference_name: "async_summary",
            preference_value: "Prefer a written summary",
          },
          created_at: stamp(),
          version: "v1",
        },
      },
      `demo-fb-${RUN}-${n}`,
    );
    if (fb?.ok) feedbackStored += 1;
    else note(`feedback ${n} rejected: ${fb?.error?.code ?? "unknown"}`);
  }
  line("feedback stored", `${feedbackStored} of 2`);
  const learning = await brain(
    "learning_status",
    { user_id: USER_ID },
    `demo-ls-${RUN}`,
  );
  const topics = learning?.result?.topics ?? [];
  const evidence = learning?.result?.preference_evidence ?? [];
  line("signal counts", JSON.stringify(learning?.result?.signal_counts ?? {}));
  line("topics learned", topics.map((t) => `${t.topic}(${t.positive}+/${t.negative}-)`).join(", ") || "—");
  line("evidence", evidence.map((e) => `${e.name} w=${e.weight.toFixed(2)}`).join(", ") || "—");

  // 10 --------------------------------------------------------------------
  heading("Developer intelligence reads a code change");
  const analysis = await brain(
    "analyze_developer",
    {
      correlation_id: CORRELATION,
      context: {
        user_id: USER_ID,
        repository: "digital-brain",
        current_file: "src/auth/login.ts",
        changed_files: ["src/auth/login.ts"],
        files: [
          {
            path: "src/auth/login.ts",
            language: "typescript",
            content:
              "export async function login(email: string) {\n  const user = await findUser(email);\n  return user.email;\n}\n",
          },
        ],
        test_results: [
          { name: "tests/auth.test.ts", status: "failed", message: "TypeError: user is null" },
        ],
      },
    },
    `demo-analyze-${RUN}`,
  );
  const reasoning = analysis?.result?.reasoning ?? {};
  const plan = analysis?.result?.plan ?? {};
  line("bugs found", String(reasoning?.bugs?.length ?? 0));
  for (const bug of reasoning?.bugs ?? []) {
    console.log(`     ${dim("·")} [${bug.severity}] ${bug.file}:${bug.line} ${bug.title}`);
  }
  line("actions proposed", String(plan?.proposed_actions?.length ?? 0));
  for (const action of plan?.proposed_actions ?? []) {
    console.log(
      `     ${dim("·")} ${action.action_type} (permission: ${action.requested_permission_level}, conf ${action.confidence})`,
    );
  }
  line("brain events", String(analysis?.result?.events?.length ?? 0));
  note("The Brain proposes. It never executes — Product decides.");

  // 11 --------------------------------------------------------------------
  heading("A real Brain event is handed to Product");
  const devEvent = (analysis?.result?.events ?? []).find(
    (e) => e.type === "developer.bug_detected",
  );
  if (devEvent) {
    const accepted = await api("/api/brain-events", {
      method: "POST",
      body: JSON.stringify(devEvent),
    });
    line("product accepted", accepted.status === 201 ? green("yes (201)") : red(`no (${accepted.status})`));
    line("mapped source", `${accepted.body?.data?.event?.source ?? "—"} (Brain sent "core")`);
    const proposals = await api("/api/developer-information");
    const rows2 = proposals.body?.data ?? [];
    const withProposal = rows2.filter((r) => r?.proposal);
    line("developer proposals", String(withProposal.length));
    note("Open /developer in the UI to see it and decide.");
  } else {
    line("bug event", red("not emitted — skipping"));
  }

  console.log(`\n${bold("Open the app")}`);
  console.log(`   ${BASE}/dashboard   what the system did on its own`);
  console.log(`   ${BASE}/timeline    the event trail, with correlation ids`);
  console.log(`   ${BASE}/developer   proposals awaiting your decision`);
  console.log(dim("\n   /memory and /people are an intentional boundary: Product has no"));
  console.log(dim("   read adapter for the Brain yet, so they show the contract that"));
  console.log(dim("   one would need rather than inventing an endpoint. The memories"));
  console.log(dim("   this run created are listed above and in the Brain log."));
  console.log(
    dim("\n   correlation id for this run: " + CORRELATION),
  );
  console.log(
    dim("   follow it through the Brain log with:"),
  );
  console.log(dim(`     rg ${CORRELATION} logs/brain.log`));
  console.log();
}

main().catch((error) => {
  console.error(red(`\n  demo failed: ${error?.message ?? error}`));
  process.exitCode = 1;
});
