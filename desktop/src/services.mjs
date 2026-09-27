/**
 * Supervision for the services the packaged app has to bring with it.
 *
 * The Electron window loads `http://localhost:3000`. During development
 * something else is already serving that port, so the shell never had to start
 * anything. Installed, there is nothing else: the app ships Product, the Brain
 * and Fly inside its own resources and is the only thing that can start them.
 *
 * That changes the shell's job from "open a window" to "open a window, once the
 * app behind it is answering" — and to shut those services down again on the way
 * out, because a Node server and a Python server left running after the window
 * closes are two processes nobody asked for.
 *
 * The order matters and is not negotiable. Migrations create the database the
 * Product will read, so they run first; the Brain must answer before the Product
 * is asked about its health, because the Product reports on the Brain and would
 * otherwise come up looking broken.
 *
 * `planServices` is a pure function so all of that can be tested without
 * spawning anything.
 */

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** Where the runtime lives: inside the packaged app, or beside it in dev. */
export function runtimeRoot(env = process.env, resourcesPath = process.resourcesPath) {
  if (env.CEREBRO_RUNTIME_DIR) return env.CEREBRO_RUNTIME_DIR;
  if (resourcesPath) return path.join(resourcesPath, "runtime");
  return path.resolve(here, "..", "runtime");
}


/**
 * How to run a Node script from inside Electron.
 *
 * `process.execPath` here is the Electron binary, so it has to be told to behave
 * as Node. That is enough for the Product server, but not for the Prisma CLI:
 * the CLI loads the sqlite driver adapter, which is a native module built for
 * the system Node's ABI, and under Electron's bundled Node it aborts before it
 * prints anything. So a real Node is used when the machine has one, and the
 * run-as-node flag is the fallback rather than the first choice.
 */
export function nodeCommand() {
  const probe = spawnSync("node", ["--version"], { stdio: "ignore" });
  if (probe.status === 0) return { cmd: "node", env: {} };
  return { cmd: process.execPath, env: { ELECTRON_RUN_AS_NODE: "1" } };
}

/**
 * Describe what has to run, in order, without running it.
 *
 * @param {object} options
 * @param {string} options.runtime where the runtime was assembled
 * @param {string} options.dataDir writable per-user directory for databases
 * @param {number} options.productPort
 * @param {number} options.brainPort
 * @param {number} [options.flyPort]
 * @param {string} [options.brainEnvFile] the Brain's own credentials file
 * @param {string} [options.python] interpreter to prefer for the Brain
 */
export function planServices({
  runtime,
  dataDir,
  productPort,
  brainPort,
  flyPort,
  brainEnvFile,
  python,
}) {
  const node = nodeCommand();
  const product = path.join(runtime, "product");
  const brain = path.join(runtime, "brain");
  const venvPython = path.join(brain, ".venv", "bin", "python");

  const steps = [
    {
      // Not a service: a one-shot that has to finish before anything reads the
      // database. Skipped when the CLI is absent rather than failing the launch,
      // because a missing CLI means an incomplete runtime build, and the Product
      // will say so itself when the schema is not ready.
      name: "migrate",
      kind: "once",
      skip: !existsSync(path.join(product, "node_modules", "prisma", "build", "index.js")),
      cmd: node.cmd,
      args: [
        path.join(product, "node_modules", "prisma", "build", "index.js"),
        "migrate",
        "deploy",
      ],
      cwd: product,
      // `process.execPath` inside Electron is the Electron binary, not Node.
      // Without this flag it is asked to run a server, and what it does instead
      // is start a second copy of the app: no output, no listener, no clue.
      // ELECTRON_RUN_AS_NODE is what turns the same binary back into Node.
      env: {
        ...node.env,
        DATABASE_URL: `file:${path.join(dataDir, "product.db")}`,
      },
      health: null,
    },
    {
      name: "brain",
      kind: "service",
      cmd: existsSync(venvPython) ? venvPython : python || "python3",
      args: [
        "-m",
        "core.transport.http",
        "--host",
        "127.0.0.1",
        "--port",
        String(brainPort),
        "--db",
        path.join(dataDir, "brain.sqlite3"),
      ],
      cwd: brain,
      env: {
        ...(brainEnvFile && existsSync(brainEnvFile) ? { BRAIN_ENV_FILE: brainEnvFile } : {}),
      },
      health: `http://127.0.0.1:${brainPort}/health`,
    },
    {
      name: "product",
      kind: "service",
      cmd: node.cmd,
      args: [path.join(product, "server.js")],
      cwd: product,
      env: {
        ...node.env,
        NODE_ENV: "production",
        PORT: String(productPort),
        HOSTNAME: "127.0.0.1",
        DATABASE_URL: `file:${path.join(dataDir, "product.db")}`,
        CORE_BRAIN_URL: `http://127.0.0.1:${brainPort}`,
        CORE_BRAIN_USER_ID: "usr_local",
      },
      health: `http://127.0.0.1:${productPort}/api/health`,
    },
  ];

  if (flyPort) {
    steps.push({
      name: "fly",
      kind: "service",
      optional: true,
      cmd: existsSync(venvPython) ? venvPython : python || "python3",
      args: ["connectome.server"],
      cwd: path.join(runtime, "fly"),
      env: {},
      // Fly has no /health contract in the runtime copy, so it is started last
      // and never waited on: the window must not hang because an optional
      // visualisation is slow to bind.
      health: null,
    });
  }

  return steps;
}

/** Poll a URL until it answers or the deadline passes. */
export async function waitForHealth(url, { timeoutMs = 60_000, intervalMs = 250, fetchImpl = fetch } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "no response";
  while (Date.now() < deadline) {
    try {
      const response = await fetchImpl(url, { signal: AbortSignal.timeout(2000) });
      if (response.ok) return true;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error?.message ?? String(error);
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`${url} did not become healthy in ${timeoutMs}ms (${lastError})`);
}

/**
 * Run the plan, in order, waiting for each service before the next.
 *
 * @returns {Promise<{started: object[], stop: () => Promise<void>}>}
 */
export async function startServices(steps, { log = () => {}, timeoutMs = 90_000 } = {}) {
  const started = [];

  for (const step of steps) {
    if (step.skip) {
      log(`skipping ${step.name}: not present in this runtime`);
      continue;
    }
    log(`starting ${step.name}`);
    const child = spawn(step.cmd, step.args, {
      cwd: step.cwd,
      env: { ...process.env, ...step.env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    const output = [];
    const capture = (buffer) => {
      const text = buffer.toString();
      output.push(text);
      if (output.length > 40) output.shift();
    };
    child.stdout?.on("data", capture);
    child.stderr?.on("data", capture);
    child.on("error", (error) => log(`${step.name} failed to start: ${error.message}`));

    if (step.kind === "once") {
      const code = await new Promise((resolve) => child.on("exit", resolve));
      if (code !== 0) {
        const detail = output.join("").trim().split("\n").slice(-4).join(" / ");
        // A failed migration is not fatal to the launch: the Product starts
        // anyway and reports an unready schema honestly, which is a clearer
        // failure than refusing to open at all.
        log(`${step.name} exited ${code}${detail ? `: ${detail}` : ""}`);
      }
      continue;
    }

    started.push({ name: step.name, child, output });
    if (step.health && !step.optional) {
      await waitForHealth(step.health, { timeoutMs });
      log(`${step.name} is healthy`);
    }
  }

  const stop = async () => {
    for (const { child } of started.reverse()) {
      if (child.exitCode !== null || child.killed) continue;
      child.kill("SIGTERM");
    }
    // Give them a moment to close their listeners before insisting.
    await new Promise((r) => setTimeout(r, 400));
    for (const { child } of started) {
      if (child.exitCode === null && !child.killed) child.kill("SIGKILL");
    }
  };

  return { started, stop };
}
