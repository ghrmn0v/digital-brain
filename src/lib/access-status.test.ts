import { describe, expect, it } from "vitest";
import {
  deriveAccessStatus,
  type AccessCheck,
  type AccessStatusInput,
} from "@/lib/access-status";

const healthy: AccessStatusInput = {
  database: { configured: true, reachable: true, recordCount: 312 },
  services: {
    fly: {
      reachable: true,
      service: "fly-python-behavior",
      neurons: 2414,
      flightMode: true,
      error: null,
    },
    desktopShell: { detected: true, agent: "Electron/44.4.5" },
  },
  gemini: {
    heldBy: "brain",
    brainEnvFileConfigured: true,
    productCredentialPresent: false,
  },
  brain: {
    urlConfigured: true,
    tokenConfigured: false,
    userIdConfigured: true,
    reachable: true,
    status: "ok",
    service: "core.brain",
    apiVersion: "v1",
  },
  permissions: {
    total: 6,
    enabled: 6,
    automatic: 2,
    askFirst: 3,
    off: 1,
    sources: 3,
  },
};

const find = (checks: AccessCheck[], id: string) => {
  const check = checks.find((c) => c.id === id);
  if (!check) throw new Error(`no check ${id}`);
  return check;
};

const withBrain = (patch: Partial<AccessStatusInput["brain"]>) =>
  deriveAccessStatus({ ...healthy, brain: { ...healthy.brain, ...patch } });

const withDatabase = (patch: Partial<AccessStatusInput["database"]>) =>
  deriveAccessStatus({ ...healthy, database: { ...healthy.database, ...patch } });

const withGemini = (patch: Partial<AccessStatusInput["gemini"]>) =>
  deriveAccessStatus({ ...healthy, gemini: { ...healthy.gemini, ...patch } });

const withPermissions = (patch: Partial<AccessStatusInput["permissions"]>) =>
  deriveAccessStatus({ ...healthy, permissions: { ...healthy.permissions, ...patch } });

describe("deriveAccessStatus", () => {
  it("returns every group the page renders, in order", () => {
    expect(deriveAccessStatus(healthy).groups.map((g) => g.id)).toEqual([
      "storage",
      "gemini",
      "services",
      "brain",
      "workspace",
    ]);
  });

  it("reports the Fly engine as optional, not broken, when it is down", () => {
    // The map, chat and Brain all work without Fly. Rendering an unreachable
    // optional service as a failure would train people to ignore the row.
    const check = find(
      deriveAccessStatus({
        ...healthy,
        services: {
          ...healthy.services,
          fly: { reachable: false, service: null, neurons: null, flightMode: null, error: "no response" },
        },
      }).checks,
      "fly-engine",
    );
    expect(check.state).toBe("warn");
    expect(check.value).toBe("Not running");
  });

  it("distinguishes the desktop shell from a browser without calling either broken", () => {
    const fromShell = find(deriveAccessStatus(healthy).checks, "desktop-shell");
    const fromBrowser = find(
      deriveAccessStatus({
        ...healthy,
        services: { ...healthy.services, desktopShell: { detected: false, agent: null } },
      }).checks,
      "desktop-shell",
    );
    expect(fromShell.state).toBe("ok");
    expect(fromShell.value).toBe("Electron");
    expect(fromBrowser.state).toBe("unknown");
    expect(fromBrowser.value).toBe("Browser");
  });

  it("counts every check once, with no duplicates across groups", () => {
    const status = deriveAccessStatus(healthy);
    const ids = status.checks.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(status.total).toBe(status.checks.length);
    expect(status.ok).toBe(status.checks.filter((c) => c.state === "ok").length);
  });

  it("reports a healthy Brain as ok and names what answered", () => {
    const check = find(withBrain({}).checks, "brain-transport");
    expect(check.state).toBe("ok");
    expect(check.value).toBe("ok");
    expect(check.detail).toContain("core.brain");
    expect(check.detail).toContain("v1");
  });

  it("distinguishes an unconfigured Brain from an unreachable one", () => {
    // The difference is the point of the overview: one needs a decision, the
    // other needs the service started.
    const unconfigured = find(
      withBrain({ urlConfigured: false, reachable: false }).checks,
      "brain-transport",
    );
    const unreachable = find(
      withBrain({ reachable: false, error: "ECONNREFUSED" }).checks,
      "brain-transport",
    );
    expect(unconfigured.state).toBe("unknown");
    expect(unconfigured.value).toBe("Not configured");
    expect(unreachable.state).toBe("error");
    expect(unreachable.value).toBe("Unreachable");
    expect(unreachable.detail).toContain("ECONNREFUSED");
  });

  it("treats a missing local database as an error, not an unknown", () => {
    const status = withDatabase({ configured: false, reachable: false, recordCount: null });
    expect(find(status.checks, "database-config").state).toBe("error");
    expect(find(status.checks, "database-read").state).toBe("error");
  });

  it("does not claim a record count when the read failed", () => {
    const check = find(
      withDatabase({ reachable: false, recordCount: null, error: "disk I/O" }).checks,
      "database-records",
    );
    expect(check.state).toBe("unknown");
    expect(check.value).toBe("Unknown");
  });

  it("never reports a record count it was not given", () => {
    expect(find(withDatabase({ recordCount: 0 }).checks, "database-records").value).toBe(
      "0 records",
    );
  });

  it("keeps the Gemini credential in the Brain as a non-problem", () => {
    // Product not holding the credential is the intended design, so it must not
    // be rendered as a fault the user needs to fix.
    const check = find(withGemini({ heldBy: "brain" }).checks, "gemini-holder");
    expect(check.state).toBe("unknown");
    expect(check.value).toBe("In Core Brain");
  });

  it("never puts a credential value into a detail string", () => {
    // Guards the one invariant that matters on this page.
    const status = deriveAccessStatus(healthy);
    for (const check of status.checks) {
      expect(`${check.label} ${check.detail} ${check.value ?? ""}`).not.toMatch(
        /AIza|[A-Za-z0-9_-]{32,}/,
      );
    }
  });

  it("warns when the Brain has no environment file but not when it has one", () => {
    expect(find(withGemini({ brainEnvFileConfigured: false }).checks, "gemini-env-file").state).toBe(
      "warn",
    );
    expect(find(withGemini({ brainEnvFileConfigured: true }).checks, "gemini-env-file").state).toBe(
      "ok",
    );
  });

  it("flags a workspace with no automatic policy so the user knows everything will ask", () => {
    const check = find(
      withPermissions({ automatic: 0, askFirst: 4 }).checks,
      "permission-enforced",
    );
    expect(check.state).toBe("warn");
    expect(check.detail).toContain("pause for a decision");
  });

  it("explains that no policy records still means ASK_FIRST, not open access", () => {
    const status = withPermissions({ total: 0, enabled: 0, automatic: 0, askFirst: 0, off: 0, sources: 0 });
    const check = find(status.checks, "permission-total");
    expect(check.state).toBe("warn");
    expect(check.detail).toContain("ASK_FIRST");
  });

  it("keeps the policy mix honest as counts, not percentages", () => {
    const check = find(withPermissions({ automatic: 2, askFirst: 3, off: 1 }).checks, "permission-breakdown");
    expect(check.value).toBe("2 / 3 / 1");
    expect(check.detail).toContain("Disabled records always resolve to OFF");
  });

  it("degrades monotonically: fewer working parts never means more checks passing", () => {
    const all = deriveAccessStatus(healthy).ok;
    const noBrain = withBrain({ urlConfigured: false, reachable: false }).ok;
    const noDb = withDatabase({ configured: false, reachable: false, recordCount: null }).ok;
    expect(noBrain).toBeLessThan(all);
    expect(noDb).toBeLessThan(all);
  });

  it("gives every check a non-empty label, detail and value", () => {
    for (const check of deriveAccessStatus(healthy).checks) {
      expect(check.label.length).toBeGreaterThan(0);
      expect(check.detail.length).toBeGreaterThan(0);
      expect(check.value).toBeTruthy();
    }
  });
});
