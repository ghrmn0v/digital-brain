/**
 * The service plan has to be right before anything is spawned.
 *
 * Order, ports, paths and the migration step are all decided in a pure function
 * precisely so they can be asserted here, without a Node server, a Python
 * virtualenv, or a window anywhere in sight. The bugs this catches are the ones
 * that only show up on someone else's machine: migrations after the thing that
 * reads the database, a port that collides, a data directory that is the
 * install directory.
 */

import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { nodeCommand, planServices, runtimeRoot, waitForHealth } from "../src/services.mjs";

const RUNTIME = "/opt/cerebro/runtime";
const DATA = "/home/someone/.config/cerebro";

function plan(overrides = {}) {
  return planServices({
    runtime: RUNTIME,
    dataDir: DATA,
    productPort: 3000,
    brainPort: 8765,
    ...overrides,
  });
}

test("migrations run before the Product that reads the database", () => {
  const names = plan().map((s) => s.name);
  assert.equal(names[0], "migrate");
  assert.ok(
    names.indexOf("migrate") < names.indexOf("product"),
    "the schema must exist before the server that queries it",
  );
});

test("the Brain answers before the Product is waited on", () => {
  const steps = plan();
  const brain = steps.find((s) => s.name === "brain");
  const product = steps.find((s) => s.name === "product");
  assert.ok(brain && product);
  assert.ok(
    steps.indexOf(brain) < steps.indexOf(product),
    "the Product reports on the Brain, so it must come up second",
  );
  assert.match(brain.health, /8765/);
  assert.match(product.health, /3000/);
});

test("Product is told where the Brain is and where its database lives", () => {
  const product = plan().find((s) => s.name === "product");
  assert.equal(product.env.CORE_BRAIN_URL, "http://127.0.0.1:8765");
  assert.equal(product.env.DATABASE_URL, `file:${path.join(DATA, "product.db")}`);
  assert.equal(product.env.PORT, "3000");
  assert.equal(product.env.HOSTNAME, "127.0.0.1");
});

test("state is written to the per-user data directory, never into the install", () => {
  for (const step of plan()) {
    const touched = [
      step.env?.DATABASE_URL ?? "",
      (step.args ?? []).join(" "),
    ].join(" ");
    if (touched.includes(".db")) {
      assert.ok(
        touched.includes(DATA),
        `${step.name} writes outside the data directory: ${touched}`,
      );
    }
  }
});

test("the Brain runs on the bundled interpreter, and on a fallback without one", async () => {
  // The runtime assembled by scripts/build-desktop-runtime.mjs ships the venv, so
  // that is the interpreter the app must use: a system Python may not have the
  // Brain's dependencies. Built for real here rather than asserted against a
  // string, because the whole point is which path wins when both exist.
  const { mkdtemp, mkdir } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const runtime = await mkdtemp(path.join(tmpdir(), "cerebro-runtime-"));
  const venvPython = path.join(runtime, "brain", ".venv", "bin", "python");
  await mkdir(path.dirname(venvPython), { recursive: true });
  await (await import("node:fs/promises")).writeFile(venvPython, "#!/bin/sh\n");

  const brain = planServices({
    runtime,
    dataDir: DATA,
    productPort: 3000,
    brainPort: 8765,
    python: "/usr/bin/python3",
  }).find((s) => s.name === "brain");

  assert.equal(
    brain.cmd,
    venvPython,
    "the bundled interpreter must win over the system one",
  );
  assert.ok(brain.args.includes("-m"));
  assert.ok(brain.args.includes("core.transport.http"));
  assert.ok(brain.args.includes(path.join(DATA, "brain.sqlite3")));

  // With no bundled venv the plan must still name a runnable interpreter rather
  // than a path that does not exist — a launch that dies on spawn is worse than
  // one that reports a missing runtime.
  const withoutVenv = planServices({
    runtime: "/nowhere/runtime",
    dataDir: DATA,
    productPort: 3000,
    brainPort: 8765,
  }).find((s) => s.name === "brain");
  assert.match(withoutVenv.cmd, /python/);
});

test("the Brain's credentials are only passed on if the file is there", () => {
  const missing = plan({ brainEnvFile: "/nowhere/gemini.env" }).find((s) => s.name === "brain");
  assert.equal(missing.env.BRAIN_ENV_FILE, undefined);
});

test("Fly is optional and never waited on", () => {
  const steps = plan({ flyPort: 8601 });
  const fly = steps.find((s) => s.name === "fly");
  assert.ok(fly, "Fly should be planned when a port is given");
  assert.equal(fly.optional, true);
  assert.equal(fly.health, null, "an optional service must not hold up the window");
});

test("Fly is left out entirely when no port is offered", () => {
  assert.equal(plan().find((s) => s.name === "fly"), undefined);
});

test("the runtime is found inside a packaged app, and beside it in dev", () => {
  assert.equal(
    runtimeRoot({}, "/opt/app/resources"),
    path.join("/opt/app/resources", "runtime"),
  );
  assert.equal(runtimeRoot({ CEREBRO_RUNTIME_DIR: "/custom" }, "/opt/app/resources"), "/custom");
  assert.ok(path.isAbsolute(runtimeRoot({}, undefined)));
});

test("Node-based steps get a Node, never a bare second copy of the app", () => {
  // process.execPath inside Electron is the Electron binary. Asked to be a Node
  // server it silently is neither: no output, no listener. Whichever way a Node
  // is obtained, the flag or a real interpreter has to be there.
  for (const name of ["migrate", "product"]) {
    const step = plan().find((s) => s.name === name);
    const isElectron = step.cmd === process.execPath;
    assert.ok(
      !isElectron || step.env.ELECTRON_RUN_AS_NODE === "1",
      `${name} would run the Electron binary as if it were Node`,
    );
  }
  // The Brain is already a real interpreter and must not claim otherwise.
  assert.equal(plan().find((s) => s.name === "brain").env.ELECTRON_RUN_AS_NODE, undefined);
});

test("a machine without Node still gets the run-as-node fallback", () => {
  const chosen = nodeCommand();
  assert.ok(chosen.cmd, "something has to be executed");
  if (chosen.cmd === process.execPath) {
    assert.equal(chosen.env.ELECTRON_RUN_AS_NODE, "1");
  }
});

test("health polling gives up rather than hanging the launch", async () => {
  await assert.rejects(
    () =>
      waitForHealth("http://127.0.0.1:1/health", {
        timeoutMs: 120,
        intervalMs: 20,
        fetchImpl: async () => {
          throw new Error("ECONNREFUSED");
        },
      }),
    /did not become healthy/,
  );
});

test("health polling accepts the first good answer", async () => {
  let calls = 0;
  const ok = await waitForHealth("http://127.0.0.1:3000/api/health", {
    timeoutMs: 1000,
    intervalMs: 10,
    fetchImpl: async () => {
      calls += 1;
      return { ok: calls >= 2, status: calls >= 2 ? 200 : 503 };
    },
  });
  assert.equal(ok, true);
  assert.equal(calls, 2);
});
