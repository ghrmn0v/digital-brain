import "server-only";

import { execSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * The Fly 3D behaviour engine (the Python connectome service).
 *
 * Fly is a separate local process from Product, so Product cannot infer whether
 * it is running from its own configuration — only by asking it. The status probe
 * is therefore a real health request rather than a config check, because "the
 * URL is set" and "the service is up" are different claims and only the second
 * one is useful to a reader of a status page.
 *
 * The control half (start/stop) exists because Fly has no supervisor: it is a
 * process someone started by hand, and without a control the only way to change
 * its state is a terminal. It is deliberately narrow:
 *
 *   - loopback only, never a remote address;
 *   - a fixed argv, so nothing a caller supplies reaches a shell;
 *   - the Brain's own environment file, so Fly starts with the same credentials
 *     as the service it usually talks to;
 *   - no credential is read, logged or returned.
 */

export const FLY_PORT = 8601;
export const FLY_ORIGIN = `http://127.0.0.1:${FLY_PORT}`;

const HEALTH_TIMEOUT_MS = 2_500;
const BOOT_TIMEOUT_MS = 20_000;

export interface FlyStatus {
  reachable: boolean;
  origin: string;
  service: string | null;
  graph: string | null;
  neurons: number | null;
  flightMode: boolean | null;
  error: string | null;
  pid: number | null;
}

function repoRoot(): string {
  // lib/ -> src/ -> repo root
  return path.resolve(process.cwd());
}

function venvPython(): string | null {
  // The venv lives in the primary checkout; fall back to whatever python3 is on
  // PATH so this still works on a machine laid out differently.
  const candidates = [
    "/home/user/AllProjects/digital-brain/.venv/bin/python",
    path.join(repoRoot(), ".venv/bin/python"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}

/** Best-effort: which process holds the port, if any. */
function pidOnPort(): number | null {
  try {
    const out = execSync(
      `ss -ltnp 2>/dev/null | grep ":${FLY_PORT} " || true`,
      { encoding: "utf8" },
    );
    const match = out.match(/pid=(\d+)/);
    return match ? Number(match[1]) : null;
  } catch {
    return null;
  }
}

export async function flyStatus(): Promise<FlyStatus> {
  const base: FlyStatus = {
    reachable: false,
    origin: FLY_ORIGIN,
    service: null,
    graph: null,
    neurons: null,
    flightMode: null,
    error: null,
    pid: pidOnPort(),
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch(`${FLY_ORIGIN}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      return { ...base, error: `HTTP ${response.status}` };
    }
    const payload = (await response.json()) as {
      service?: string;
      graph?: string;
      neurons?: number;
      flight_mode?: boolean;
    };
    return {
      ...base,
      reachable: true,
      service: payload.service ?? null,
      graph: payload.graph ?? null,
      neurons: typeof payload.neurons === "number" ? payload.neurons : null,
      flightMode: typeof payload.flight_mode === "boolean" ? payload.flight_mode : null,
    };
  } catch (error) {
    const aborted = error instanceof Error && error.name === "AbortError";
    return {
      ...base,
      error: aborted
        ? `no answer within ${HEALTH_TIMEOUT_MS / 1000}s`
        : error instanceof Error
          ? error.message
          : "no response",
    };
  } finally {
    clearTimeout(timer);
  }
}

export type FlyAction = "start" | "stop";

export type FlyControlResult =
  | { ok: true; action: FlyAction; status: FlyStatus; note?: string }
  | { ok: false; action: FlyAction; reason: string; status: FlyStatus };

/**
 * Start or stop Fly.
 *
 * Stop signals the process holding the port; start spawns the documented command
 * detached, then waits for the health endpoint so the caller gets the real
 * outcome rather than "spawn returned".
 */
export async function flyControl(action: FlyAction): Promise<FlyControlResult> {
  const current = await flyStatus();

  if (action === "stop") {
    const pid = current.pid;
    if (!pid) {
      return { ok: false, action, reason: "Fly is not running.", status: current };
    }
    try {
      process.kill(pid, "SIGTERM");
    } catch (error) {
      return {
        ok: false,
        action,
        reason: `Could not signal pid ${pid}: ${
          error instanceof Error ? error.message : "unknown error"
        }`,
        status: current,
      };
    }
    // Give it a moment to release the port before reporting.
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 150));
      if (!(await flyStatus()).reachable) {
        return {
          ok: true,
          action,
          status: await flyStatus(),
          note: `Stopped pid ${pid}.`,
        };
      }
    }
    return { ok: false, action, reason: "Fly did not stop.", status: await flyStatus() };
  }

  if (current.reachable) {
    return { ok: true, action, status: current, note: "Fly is already running." };
  }

  const python = venvPython();
  if (!python) {
    return { ok: false, action, reason: "No Python interpreter found for Fly.", status: current };
  }
  const connectomeDir = path.join(repoRoot(), "connectome");
  if (!fs.existsSync(path.join(connectomeDir, "connectome", "server.py"))) {
    return { ok: false, action, reason: "The Fly connectome package is not present.", status: current };
  }

  // Fixed argv. The env file is the Brain's, so Fly inherits the same provider
  // configuration instead of needing its own copy of any credential.
  const envFile = process.env.BRAIN_ENV_FILE?.trim();
  const child = spawn(
    python,
    ["-m", "connectome.server", "--port", String(FLY_PORT)],
    {
      cwd: connectomeDir,
      detached: true,
      stdio: "ignore",
      env: { ...process.env, ...(envFile ? { BRAIN_ENV_FILE: envFile } : {}) },
    },
  );
  child.unref();

  const deadline = Date.now() + BOOT_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const next = await flyStatus();
    if (next.reachable) {
      return { ok: true, action, status: next, note: `Started on ${FLY_ORIGIN}.` };
    }
  }
  return {
    ok: false,
    action,
    reason: "Fly did not become healthy in time. Check the server log.",
    status: await flyStatus(),
  };
}
