import type { Metadata } from "next";
import { PermissionsManager } from "@/components/permissions-manager";
import { PermissionsStatus } from "@/components/permissions-status";
import { PageHeader } from "@/components/ui";
import { deriveAccessStatus } from "@/lib/access-status";
import { permissionService } from "@/modules/permissions";
import { taskService } from "@/modules/tasks";

export const metadata: Metadata = { title: "Permissions" };

/** Health probes must never hold the page open; a slow Brain is a fact, not a hang. */
const HEALTH_TIMEOUT_MS = 2_500;

async function probeDatabase() {
  const configured = Boolean(process.env.DATABASE_URL?.trim());
  if (!configured) {
    return { configured: false, reachable: false, recordCount: null };
  }
  // The connection string is deliberately never read or echoed: for some drivers
  // it carries a password. A single row-counting read proves both reachability
  // and that the schema is actually queryable.
  try {
    const probe = await taskService.list({}, 1, 1);
    return {
      configured: true,
      reachable: true,
      recordCount: probe.pagination.total,
    };
  } catch (error) {
    return {
      configured: true,
      reachable: false,
      recordCount: null,
      error: error instanceof Error ? error.message : "unknown error",
    };
  }
}

async function probeBrain() {
  const url = process.env.CORE_BRAIN_URL?.trim();
  const base = {
    urlConfigured: Boolean(url),
    tokenConfigured: Boolean(process.env.CORE_BRAIN_API_TOKEN?.trim()),
    userIdConfigured: Boolean(process.env.CORE_BRAIN_USER_ID?.trim()),
  };
  if (!url) return { ...base, reachable: false };

  // CORE_BRAIN_URL is the address of the `POST /v1/brain` method endpoint, not
  // the server root, so `/health` has to be resolved against its origin.
  // Appending to the configured value instead asks for `/v1/brain/health`, which
  // answers 404 and makes a perfectly healthy Brain look broken.
  let healthUrl: string;
  try {
    healthUrl = new URL("/health", url).toString();
  } catch {
    return { ...base, reachable: false, error: "CORE_BRAIN_URL is not a valid URL" };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch(healthUrl, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      return { ...base, reachable: false, error: `HTTP ${response.status}` };
    }
    const payload = (await response.json()) as {
      status?: string;
      service?: string;
      api_version?: string;
    };
    return {
      ...base,
      reachable: true,
      status: payload.status ?? null,
      service: payload.service ?? null,
      apiVersion: payload.api_version ?? null,
    };
  } catch (error) {
    const aborted = error instanceof Error && error.name === "AbortError";
    return {
      ...base,
      reachable: false,
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

export default async function PermissionsPage() {
  const [permissions, database, brain] = await Promise.all([
    permissionService.list({}),
    probeDatabase(),
    probeBrain(),
  ]);

  const sources = new Set(permissions.map((permission) => permission.source));
  const enabled = permissions.filter((permission) => permission.enabled);

  const status = deriveAccessStatus({
    database,
    gemini: {
      // Presence only, never the value. The credential belongs to the Brain and
      // this page deliberately does not open its environment file to find out
      // more than "it was told where to read from".
      heldBy: process.env.GEMINI_API_KEY?.trim() ? "product" : "brain",
      brainEnvFileConfigured: Boolean(process.env.BRAIN_ENV_FILE?.trim()),
      productCredentialPresent: Boolean(process.env.GEMINI_API_KEY?.trim()),
    },
    brain,
    permissions: {
      total: permissions.length,
      enabled: enabled.length,
      automatic: enabled.filter((p) => p.level === "AUTOMATIC").length,
      askFirst: enabled.filter((p) => p.level === "ASK_FIRST").length,
      off: enabled.filter((p) => p.level === "OFF").length,
      sources: sources.size,
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Action policy"
        title="Permissions"
        description="Control each source and action with explicit automatic, ask-first, or off policies. Disabled entries always resolve to OFF."
      />
      <PermissionsStatus status={status} />
      <PermissionsManager permissions={permissions} />
    </div>
  );
}
