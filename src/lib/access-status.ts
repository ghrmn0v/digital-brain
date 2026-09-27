/**
 * Access status for the Permissions page.
 *
 * This module is pure: it takes facts that were observed somewhere else and
 * decides what each one means. The observation happens in the page, which is the
 * only place allowed to touch the database, the environment and the Brain. That
 * split is what makes the interesting part — which state a fact implies, and
 * what a user should be told about it — testable without a database, a network
 * or an environment.
 *
 * Two rules run through all of it.
 *
 * First, no secret is ever read into a status. The Gemini credential belongs to
 * the Core Brain and is deliberately not opened by Product, so the most that can
 * honestly be reported is that it is held elsewhere. A permissions screen is
 * exactly the page someone opens while worried about access, so it must never be
 * the page that reveals one.
 *
 * Second, a missing configuration is not an error. An unconfigured Brain is a
 * normal state for a local-first tool that someone may not have started yet, so
 * it reports as "not configured" rather than "broken", and the distinction
 * between "not configured", "configured but unreachable" and "healthy" is the
 * whole point of the overview.
 */

export type AccessState = "ok" | "warn" | "error" | "unknown";

export interface AccessCheck {
  id: string;
  label: string;
  state: AccessState;
  /** A full sentence. Says what was observed, not what should be done. */
  detail: string;
  /** Short value for the right-hand column, e.g. "312 records". */
  value?: string;
}

export interface AccessGroup {
  id: string;
  title: string;
  description: string;
  checks: AccessCheck[];
}

export interface DatabaseFacts {
  configured: boolean;
  reachable: boolean;
  /** Row count from a live read, or null when the read failed. */
  recordCount: number | null;
  error?: string;
}

export interface GeminiFacts {
  /** Where the model credential lives, as far as Product can honestly tell. */
  heldBy: "brain" | "product" | "unset";
  /** True when the Brain was told where to read its environment from. */
  brainEnvFileConfigured: boolean;
  /**
   * Whether a credential is present in Product's own environment. Only ever a
   * boolean — the value is never read, and the fact is only meaningful when
   * `heldBy` is "product".
   */
  productCredentialPresent: boolean;
}

export interface BrainFacts {
  urlConfigured: boolean;
  tokenConfigured: boolean;
  userIdConfigured: boolean;
  /** Result of the live `GET /health` probe. */
  reachable: boolean;
  status?: string | null;
  service?: string | null;
  apiVersion?: string | null;
  error?: string;
}

export interface ServicesFacts {
  /** The Fly 3D behaviour engine, probed rather than assumed. */
  fly: {
    reachable: boolean;
    service: string | null;
    neurons: number | null;
    flightMode: boolean | null;
    error: string | null;
  };
  /**
   * Whether this request came from the Electron shell. Read from the user agent
   * because that is the only signal the server has: the desktop app is a client
   * of Product, not a process it launches, so there is nothing to inspect.
   */
  desktopShell: { detected: boolean; agent: string | null };
}

export interface PermissionFacts {
  total: number;
  enabled: number;
  automatic: number;
  askFirst: number;
  off: number;
  sources: number;
}

export interface AccessStatusInput {
  database: DatabaseFacts;
  services: ServicesFacts;
  gemini: GeminiFacts;
  brain: BrainFacts;
  permissions: PermissionFacts;
}

export interface AccessStatus {
  groups: AccessGroup[];
  checks: AccessCheck[];
  ok: number;
  total: number;
}

const plural = (count: number, one: string, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;

function databaseChecks(input: AccessStatusInput): AccessCheck[] {
  const { database } = input;
  const state: AccessState = !database.configured
    ? "error"
    : database.reachable
      ? "ok"
      : "error";

  return [
    {
      id: "database-config",
      label: "Local storage configured",
      state: database.configured ? "ok" : "error",
      detail: database.configured
        ? "A local SQLite database is configured for this workspace."
        : "DATABASE_URL is not set, so this workspace has nowhere to store records.",
      value: database.configured ? "Configured" : "Missing",
    },
    {
      id: "database-read",
      label: "Local storage readable",
      state,
      detail: database.reachable
        ? "A live read against the local database succeeded."
        : database.configured
          ? `The database is configured but a read failed: ${database.error ?? "unknown error"}.`
          : "No read was attempted because storage is not configured.",
      value: database.reachable
        ? "Readable"
        : database.configured
          ? "Unreadable"
          : "Not checked",
    },
    {
      id: "database-records",
      label: "Records present",
      state: database.recordCount === null ? "unknown" : "ok",
      detail:
        database.recordCount === null
          ? "The record count is unknown because the read did not complete."
          : "The same local database holds every record this workspace shows.",
      value:
        database.recordCount === null
          ? "Unknown"
          : plural(database.recordCount, "record"),
    },
  ];
}

function geminiChecks(input: AccessStatusInput): AccessCheck[] {
  const { gemini } = input;
  return [
    {
      id: "gemini-holder",
      label: "Model credential",
      // Not an error: the credential living in the Brain is the intended
      // design, so this reports as informational rather than as a problem.
      state: gemini.heldBy === "product" ? "ok" : "unknown",
      detail:
        gemini.heldBy === "product"
          ? "A model credential is present in this application's environment."
          : gemini.heldBy === "brain"
            ? "The model credential is held by the Core Brain. Product never reads or displays it."
            : "No model credential is configured in this application or in the Core Brain.",
      value:
        gemini.heldBy === "product"
          ? "In Product"
          : gemini.heldBy === "brain"
            ? "In Core Brain"
            : "Unset",
    },
    {
      id: "gemini-env-file",
      label: "Brain environment source",
      state: gemini.brainEnvFileConfigured ? "ok" : "warn",
      detail: gemini.brainEnvFileConfigured
        ? "The Core Brain was pointed at an environment file, so its model settings resolve without shell state."
        : "The Core Brain was not pointed at an environment file, so it depends on the shell it was started from.",
      value: gemini.brainEnvFileConfigured ? "Configured" : "Not set",
    },
  ];
}

function brainChecks(input: AccessStatusInput): AccessCheck[] {
  const { brain } = input;
  const state: AccessState = !brain.urlConfigured
    ? "unknown"
    : brain.reachable
      ? "ok"
      : "error";

  return [
    {
      id: "brain-transport",
      label: "Brain API transport",
      state,
      detail: !brain.urlConfigured
        ? "CORE_BRAIN_URL is not set, so this workspace has no Brain to talk to."
        : brain.reachable
          ? `The Brain answered its health probe${brain.service ? ` as ${brain.service}` : ""}${brain.apiVersion ? ` on API ${brain.apiVersion}` : ""}.`
          : `The Brain is configured but did not answer its health probe: ${brain.error ?? "no response"}.`,
      value: !brain.urlConfigured
        ? "Not configured"
        : brain.reachable
          ? (brain.status ?? "Reachable")
          : "Unreachable",
    },
    {
      id: "brain-identity",
      label: "Brain identity",
      state: brain.userIdConfigured ? "ok" : "warn",
      detail: brain.userIdConfigured
        ? "A user id is configured, so Brain records are attributed to this workspace."
        : "No user id is configured, so the Brain falls back to a shared local identity.",
      value: brain.userIdConfigured ? "Configured" : "Default",
    },
    {
      id: "brain-token",
      label: "Brain transport token",
      // Presence only. The value is never read.
      state: brain.tokenConfigured ? "ok" : "unknown",
      detail: brain.tokenConfigured
        ? "A transport token is configured for the Brain connection."
        : "No transport token is configured. A loopback Brain does not require one, so this is expected by default.",
      value: brain.tokenConfigured ? "Configured" : "None",
    },
  ];
}

function servicesChecks(input: AccessStatusInput): AccessCheck[] {
  const { fly, desktopShell } = input.services;
  return [
    {
      id: "fly-engine",
      label: "Fly 3D engine",
      state: fly.reachable ? "ok" : "warn",
      detail: fly.reachable
        ? `The Fly behaviour engine answered its health probe${
            fly.neurons ? ` with ${fly.neurons.toLocaleString("en-US")} neurons` : ""
          }${fly.flightMode ? " and flight mode on" : ""}.`
        : `The Fly engine did not answer on port 8601${
            fly.error ? `: ${fly.error}` : ""
          }. The map and chat do not need it; the 3D view does.`,
      value: fly.reachable ? (fly.service ?? "Running") : "Not running",
    },
    {
      id: "desktop-shell",
      label: "Desktop shell",
      state: desktopShell.detected ? "ok" : "unknown",
      detail: desktopShell.detected
        ? "This request came from the Electron desktop shell, which is loading the same interface in a native window."
        : "This request came from a browser. The desktop shell is optional and serves the same routes.",
      value: desktopShell.detected ? "Electron" : "Browser",
    },
  ];
}

function permissionChecks(input: AccessStatusInput): AccessCheck[] {
  const { permissions } = input;
  const enforced = permissions.automatic + permissions.askFirst;

  return [
    {
      id: "permission-total",
      label: "Policy records",
      state: permissions.total > 0 ? "ok" : "warn",
      detail:
        permissions.total > 0
          ? `${plural(permissions.total, "policy")} across ${plural(permissions.sources, "source")} define what this workspace may do.`
          : "No policy records exist. Unconfigured actions fall back to ASK_FIRST by design, so nothing is silently allowed.",
      value: String(permissions.total),
    },
    {
      id: "permission-breakdown",
      label: "Policy mix",
      state: "ok",
      detail: `${permissions.automatic} automatic, ${permissions.askFirst} ask first, ${permissions.off} off. Disabled records always resolve to OFF regardless of their stored level.`,
      value: `${permissions.automatic} / ${permissions.askFirst} / ${permissions.off}`,
    },
    {
      id: "permission-enforced",
      label: "Acted on without asking",
      state: permissions.automatic === 0 && permissions.total > 0 ? "warn" : "ok",
      detail:
        permissions.automatic === 0
          ? "No action is automatic, so every request will pause for a decision."
          : `${permissions.automatic} ${permissions.automatic === 1 ? "action runs" : "actions run"} without asking, and ${permissions.askFirst} will pause for one.`,
      value: String(enforced),
    },
  ];
}

export function deriveAccessStatus(input: AccessStatusInput): AccessStatus {
  const groups: AccessGroup[] = [
    {
      id: "storage",
      title: "Local storage",
      description: "Where this workspace keeps its records",
      checks: databaseChecks(input),
    },
    {
      id: "gemini",
      title: "Gemini environment",
      description: "Who holds the model credential, without revealing it",
      checks: geminiChecks(input),
    },
    {
      id: "services",
      title: "Local services",
      description: "The optional processes this workspace can talk to",
      checks: servicesChecks(input),
    },
    {
      id: "brain",
      title: "Brain API transport",
      description: "Live reachability of the Core Brain",
      checks: brainChecks(input),
    },
    {
      id: "workspace",
      title: "Workspace permissions",
      description: "What this workspace is allowed to do without you",
      checks: permissionChecks(input),
    },
  ];

  const checks = groups.flatMap((group) => group.checks);
  return {
    groups,
    checks,
    ok: checks.filter((check) => check.state === "ok").length,
    total: checks.length,
  };
}
