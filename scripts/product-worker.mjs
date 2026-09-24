import "dotenv/config";

const baseUrl = (process.env.APP_URL || "http://localhost:3000").replace(/\/$/, "");
const token = process.env.SERVICE_API_TOKEN?.trim();
const intervalMs = Math.max(
  5_000,
  Number(process.env.WORKER_INTERVAL_MS || "30000"),
);

let running = false;

async function call(pathname) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    method: "POST",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(10_000),
  });

  if (!response.ok) {
    throw new Error(`${pathname} returned HTTP ${response.status}`);
  }
}

async function tick() {
  if (running) return;
  running = true;
  try {
    await Promise.allSettled([
      call("/api/internal/automations/schedules"),
      call("/api/internal/event-deliveries"),
    ]);
  } finally {
    running = false;
  }
}

process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));

await tick();
setInterval(tick, intervalMs);
