import { execFileSync, spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const databasePath = path.join(root, "smoke.db");
const port = process.env.SMOKE_TEST_PORT || "3111";
const baseUrl = `http://localhost:${port}`;

if (existsSync(databasePath)) rmSync(databasePath, { force: true });

const env = {
  ...process.env,
  DATABASE_URL: "file:./smoke.db",
};
const runNode = (args, options = {}) =>
  execFileSync(process.execPath, args, {
    cwd: root,
    env,
    stdio: "pipe",
    ...options,
  });

runNode(["node_modules/prisma/build/index.js", "migrate", "deploy"]);
runNode(["node_modules/tsx/dist/cli.mjs", "prisma/seed.ts"]);

const server = spawn(
  process.execPath,
  ["node_modules/next/dist/bin/next", "dev", "-p", port],
  {
    cwd: root,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  },
);

let serverLogs = "";
server.stdout.on("data", (chunk) => {
  serverLogs += chunk.toString();
});
server.stderr.on("data", (chunk) => {
  serverLogs += chunk.toString();
});

const delay = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

async function request(pathname, init = {}) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init.headers || {}),
    },
    signal: AbortSignal.timeout(15_000),
  });
  const text = await response.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  return { status: response.status, body, headers: response.headers };
}

try {
  let ready = false;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      if ((await request("/api/health")).status === 200) {
        ready = true;
        break;
      }
    } catch {}
    await delay(250);
  }
  if (!ready) throw new Error(`Server did not become ready.\n${serverLogs}`);

  const taskCreate = await request("/api/tasks", {
    method: "POST",
    headers: { "idempotency-key": "smoke-task-1" },
    body: JSON.stringify({ title: "Smoke task", priority: "high" }),
  });
  const taskReplay = await request("/api/tasks", {
    method: "POST",
    headers: { "idempotency-key": "smoke-task-1" },
    body: JSON.stringify({ title: "Smoke task", priority: "high" }),
  });
  const taskDone = await request(`/api/tasks/${taskCreate.body.data.id}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "done" }),
  });
  const invalidCalendar = await request("/api/calendar", {
    method: "POST",
    body: JSON.stringify({
      title: "Invalid event",
      startsAt: "2026-10-01T12:00:00.000Z",
      endsAt: "2026-10-01T11:00:00.000Z",
    }),
  });
  const action = await request("/api/actions", {
    method: "POST",
    body: JSON.stringify({
      source: "core_brain",
      action: "tasks.create_task",
      payload: { title: "Approval task" },
    }),
  });
  const approval = await request(
    `/api/actions/${action.body.data.actionId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ reason: "Smoke approval" }),
    },
  );
  const linkedinFirst = await request("/api/connectors/linkedin/jobs/ingest", {
    method: "POST",
    body: JSON.stringify({
      jobs: [
        { externalId: "smoke-job-1", title: "Engineer", company: "Acme" },
      ],
    }),
  });
  const linkedinReplay = await request("/api/connectors/linkedin/jobs/ingest", {
    method: "POST",
    body: JSON.stringify({
      jobs: [
        { externalId: "smoke-job-1", title: "Engineer", company: "Acme" },
      ],
    }),
  });

  const summary = {
    taskCreate: taskCreate.status,
    taskReplay: taskReplay.status,
    idempotencyReplayed:
      taskReplay.headers.get("idempotency-replayed") === "true",
    sameTask: taskCreate.body.data.id === taskReplay.body.data.id,
    taskDone: taskDone.body.data.status,
    invalidCalendar: invalidCalendar.status,
    action: action.body.data.status,
    approval: approval.body.data.status,
    linkedInFirst: linkedinFirst.status,
    linkedInReplay: linkedinReplay.status,
    duplicateEvent: linkedinReplay.body.data.items[0].duplicateEvent,
  };

  const passed =
    summary.taskCreate === 201 &&
    summary.taskReplay === 201 &&
    summary.idempotencyReplayed &&
    summary.sameTask &&
    summary.taskDone === "done" &&
    summary.invalidCalendar === 400 &&
    summary.action === "pending_approval" &&
    summary.approval === "completed" &&
    summary.linkedInFirst === 200 &&
    summary.linkedInReplay === 200 &&
    summary.duplicateEvent;

  console.log(JSON.stringify(summary, null, 2));
  if (!passed) throw new Error(`Smoke assertions failed.\n${serverLogs}`);
} finally {
  server.kill();
  await delay(250);
  if (existsSync(databasePath)) rmSync(databasePath, { force: true });
}
