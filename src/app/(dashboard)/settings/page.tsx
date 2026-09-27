import type { Metadata } from "next";
import {
  BrainCircuit,
  CheckCircle2,
  CircleOff,
  RadioTower,
} from "@/components/icons";
import { ApprovalsManager } from "@/components/approvals-manager";
import { AutomationsManager } from "@/components/automations-manager";
import { ConnectorsManager } from "@/components/connectors-manager";
import { DeveloperModeToggle } from "@/components/developer-mode-toggle";
import { PermissionsManager } from "@/components/permissions-manager";
import { SettingsManager } from "@/components/settings-manager";
import { SettingsSection } from "@/components/settings/settings-section";
import { SettingsSectionNav } from "@/components/settings/settings-section-nav";
import { FlyEngineControl } from "@/components/settings/fly-engine-control";
import { flyStatus } from "@/lib/fly-service";
import { Panel, SectionHeading } from "@/components/ui";
import { actionService } from "@/modules/actions";
import { automationService } from "@/modules/automations";
import { connectorService } from "@/modules/connectors";
import {
  DEVELOPER_MODE_SETTING_KEY,
  developerModeService,
} from "@/modules/developer-mode";
import { permissionService } from "@/modules/permissions";
import { settingsService } from "@/modules/settings";

const SETTINGS_SECTIONS = [
  { id: "general", label: "General" },
  { id: "permissions", label: "Permissions" },
  { id: "approvals", label: "Approvals" },
  { id: "automations", label: "Automations" },
  { id: "connectors", label: "Connectors" },
] as const;

export const metadata: Metadata = { title: "Settings" };

/**
 * Everything the operator can change, on one page.
 *
 * Approvals, Automations, Permissions and Connectors used to be four
 * separate routes. They are sections here instead, ordered by how much
 * they depend on each other: policy decides what may run, the approval
 * queue is what policy held back, automations are the rules, and
 * connectors are where the data arrives from.
 *
 * The old routes still resolve, so bookmarks and external links keep
 * working, but in-app links go straight to the section.
 */
export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ section?: string }>;
}) {
  /*
   * Settings used to be one long page with an IntersectionObserver acting as a
   * scroll-spy, so every section was always in the DOM and choosing one only
   * scrolled to it. Selecting a category now renders just that category, and the
   * choice lives in the URL so a section can be linked to and survives a reload.
   */
  const requested = (await searchParams).section;
  const active = SETTINGS_SECTIONS.some((entry) => entry.id === requested)
    ? (requested as (typeof SETTINGS_SECTIONS)[number]["id"])
    : "general";

  const [
    fly,
    settings,
    developerModeEnabled,
    pendingActions,
    automations,
    permissions,
    connectorRecords,
  ] = await Promise.all([
    flyStatus(),
    settingsService.list(),
    developerModeService.isEnabled(),
    actionService.list({ status: "pending_approval" }, 1, 100),
    automationService.list({}),
    permissionService.list({}),
    connectorService.list(),
  ]);

  const sensitiveSettingPattern =
    /(?:api[-_.]?key|authorization|credential|password|secret|token)/i;
  const publicSettings = settings.filter(
    (setting) =>
      !sensitiveSettingPattern.test(setting.key) &&
      setting.key !== DEVELOPER_MODE_SETTING_KEY,
  );
  const restrictedSettingCount = settings.filter((setting) =>
    sensitiveSettingPattern.test(setting.key),
  ).length;

  const connectors = connectorRecords.map((connector) => ({
    id: connector.id,
    name: connector.name,
    type: connector.type,
    version: connector.version,
    enabled: connector.enabled,
    status: connector.status,
    lastSyncAt: connector.lastSyncAt,
    lastError: connector.lastError,
    updatedAt: connector.updatedAt,
  }));

  const coreBrainConfigured = Boolean(process.env.CORE_BRAIN_URL?.trim());
  const flyConfigured = Boolean(process.env.FLY_EVENTS_URL?.trim());

  return (
    <div className="space-y-8">
      <SettingsSectionNav />

      {active === "general" ? (
        <SettingsSection
        id="general"
        eyebrow="System configuration"
        title="General"
        description="Product settings and platform capabilities. Environment secrets and remote service URLs never reach this page."
      >
        {/* Fly is a separate local process, so the app can show its real
            status and start or stop it rather than leaving that to a terminal. */}
        <FlyEngineControl initial={fly} />
        <div className="space-y-4">
          <div className="hidden min-[900px]:block">
            <DeveloperModeToggle enabled={developerModeEnabled} />
          </div>

          <Panel>
            <SectionHeading
              title="Integration readiness"
              description="Only configuration booleans cross the server boundary"
            />
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <ReadinessCard
                name="Core Brain"
                description="Normalized events and developer intelligence"
                configured={coreBrainConfigured}
                icon={BrainCircuit}
              />
              <div className="hidden min-[900px]:block">
                <ReadinessCard
                  name="Fly events"
                  description="Normalized events via the Connectome layer"
                  configured={flyConfigured}
                  icon={RadioTower}
                />
              </div>
            </div>
          </Panel>

          {restrictedSettingCount > 0 ? (
            <div className="rounded-lg border border-[var(--warning)]/20 bg-[var(--warning)]/[0.07] px-4 py-3 text-sm text-[var(--warning)]">
              {restrictedSettingCount} potentially sensitive{" "}
              {restrictedSettingCount === 1 ? "setting is" : "settings are"}{" "}
              withheld from the browser UI.
            </div>
          ) : null}

          <SettingsManager settings={publicSettings} />
        </div>
      </SettingsSection>
      ) : null}

      {active === "permissions" ? (
      <SettingsSection
        id="permissions"
        eyebrow="Action policy"
        title="Permissions"
        description="Control each source and action with explicit automatic, ask-first, or off policies. Disabled entries always resolve to off."
      >
        <PermissionsManager permissions={permissions} />
      </SettingsSection>
      ) : null}

      {active === "approvals" ? (
      <SettingsSection
        id="approvals"
        eyebrow="Human-in-the-loop"
        title="Approvals"
        description="Automatic actions execute without interrupting you. This queue holds only ask-first proposals, with structured payloads and a durable decision reason."
      >
        <ApprovalsManager actions={pendingActions.items} />
      </SettingsSection>
      ) : null}

      {active === "automations" ? (
      <SettingsSection
        id="automations"
        eyebrow="Event workflows"
        title="Automations"
        description="Translate normalized events into registered actions with explicit JSON payloads, optional conditions, and human permission enforcement."
      >
        <AutomationsManager automations={automations} />
      </SettingsSection>
      ) : null}

      {active === "connectors" ? (
      <SettingsSection
        id="connectors"
        eyebrow="Integration registry"
        title="Connectors"
        description="Seeded connectors, connection health, and recent sync outcomes. Credentials and credential values are never shown."
      >
        <ConnectorsManager connectors={connectors} />
      </SettingsSection>
      ) : null}
    </div>
  );
}

function ReadinessCard({
  name,
  description,
  configured,
  icon: Icon,
}: {
  name: string;
  description: string;
  configured: boolean;
  icon: typeof BrainCircuit;
}) {
  const StatusIcon = configured ? CheckCircle2 : CircleOff;
  return (
    <article className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)] p-5">
      <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] text-[var(--text-primary)]">
        <Icon aria-hidden="true" className="h-5 w-5" />
      </div>
      <h3 className="mt-5 text-[0.9375rem] font-semibold text-[var(--text-primary)]">
        {name}
      </h3>
      <p className="mt-1.5 text-[0.875rem] leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
      <div className="mt-4 flex items-center gap-2 border-t border-[var(--panel-line)] pt-3 text-[0.8125rem] text-[var(--text-muted)]">
        <StatusIcon
          aria-hidden="true"
          className={
            configured
              ? "h-3.5 w-3.5 text-[var(--success)]"
              : "h-3.5 w-3.5 text-[var(--text-muted)]"
          }
        />
        URL configured: {configured ? "yes" : "no"}
      </div>
    </article>
  );
}
