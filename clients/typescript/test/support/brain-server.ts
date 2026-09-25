/**
 * Starts the real Core HTTP transport (`python -m core.transport.http`) on an
 * ephemeral loopback port with an in-memory database, so the client tests
 * exercise the real server, the real `BrainApi` and the real contract.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer, type Server } from "node:http";
import { createServer as createNetServer, type Socket } from "node:net";
import { join } from "node:path";

const REPO_ROOT = join(import.meta.dirname, "..", "..", "..", "..");

function pythonExecutable(): string {
  const venv = join(REPO_ROOT, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

async function freePort(): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    const probe = createNetServer();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      if (address === null || typeof address === "string") {
        probe.close();
        reject(new Error("could not reserve a loopback port"));
        return;
      }
      const { port } = address;
      probe.close(() => {
        resolve(port);
      });
    });
  });
}

export interface BrainHttpServer {
  readonly baseUrl: string;
  stop(): Promise<void>;
}

export interface SilentServer {
  readonly baseUrl: string;
  stop(): Promise<void>;
}

const freePortValue = freePort;

async function reservePort(): Promise<number> {
  return freePortValue();
}

/** Accepts connections and never answers, to exercise client timeouts. */
export async function startSilentServer(): Promise<SilentServer> {
  const port = await reservePort();
  const server = createServer();
  const sockets = new Set<Socket>();
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      resolve();
    });
  });
  return {
    baseUrl: `http://127.0.0.1:${port}`,
    async stop(): Promise<void> {
      for (const socket of sockets) {
        socket.destroy();
      }
      await new Promise<void>((resolve) => {
        server.close(() => {
          resolve();
        });
      });
    },
  };
}

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

export async function startBrainHttpServer(): Promise<BrainHttpServer> {
  const port = await freePort();
  const child: ChildProcess = spawn(
    pythonExecutable(),
    ["-m", "core.transport.http", "--host", "127.0.0.1", "--port", String(port), "--db", ":memory:"],
    { cwd: REPO_ROOT, stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => {
    stderr += chunk.toString("utf8");
  });
  const baseUrl = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30_000;
  for (;;) {
    if (child.exitCode !== null) {
      throw new Error(`brain http server exited early (${child.exitCode}): ${stderr}`);
    }
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) {
        break;
      }
    } catch {
      /* not up yet */
    }
    if (Date.now() > deadline) {
      child.kill("SIGKILL");
      throw new Error(`brain http server did not become ready: ${stderr}`);
    }
    await sleep(100);
  }
  return {
    baseUrl,
    async stop(): Promise<void> {
      if (child.exitCode !== null) {
        return;
      }
      child.kill("SIGINT");
      const exitDeadline = Date.now() + 5_000;
      while (child.exitCode === null && Date.now() < exitDeadline) {
        await sleep(50);
      }
      if (child.exitCode === null) {
        child.kill("SIGKILL");
      }
    },
  };
}
