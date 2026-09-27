import type { Metadata } from "next";
import {
  BrainCircuit,
  CheckCircle2,
  CircleOff,
  RadioTower,
  Settings2,
} from "@/components/icons";
import { DeveloperModeToggle } from "@/components/developer-mode-toggle";
import { SettingsManager } from "@/components/settings-manager";
import {
  Badge,
  PageHeader,
  Panel,
  SectionHeading,
} from "@/components/ui";
import {
  DEVELOPER_MODE_SETTING_KEY,
  developerModeService,
} from "@/modules/developer-mode";
import { settingsService } from "@/modules/settings";

export const metadata: Metadata = { title: "Settings" };

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
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] text-[var(--text-primary)]">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
        <Badge tone={configured ? "success" : "neutral"} dot>
          {configured ? "Configured" : "Not configured"}
        </Badge>
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
          className={configured ? "h-3.5 w-3.5 text-[var(--success)]" : "h-3.5 w-3.5 text-[var(--text-muted)]"}
        />
        URL configured: {configured ? "yes" : "no"}
      </div>
    </article>
  );
}

export default async function SettingsPage() {
  const [settings, developerModeEnabled] = await Promise.all([
    settingsService.list(),
    developerModeService.isEnabled(),
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
  const coreBrainConfigured = Boolean(process.env.CORE_BRAIN_URL?.trim());
  const flyConfigured = Boolean(process.env.FLY_EVENTS_URL?.trim());

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="System configuration"
        title="Settings"
        description="Manage local product settings and platform capabilities without displaying environment secrets or remote service URLs."
      />

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
        <div className="hidden items-start gap-3 border-t border-[var(--panel-line)] px-5 py-4 text-[0.8125rem] leading-6 text-[var(--text-muted)] min-[900px]:flex">
          <Settings2 aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
          API tokens are never read, returned, or rendered by this interface.
        </div>
      </Panel>

      {restrictedSettingCount > 0 ? (
        <div className="rounded-lg border border-[var(--warning)]/20 bg-[var(--warning)]/[0.07] px-4 py-3 text-sm text-[var(--warning)]">
          {restrictedSettingCount} potentially sensitive {restrictedSettingCount === 1 ? "setting is" : "settings are"} withheld from the browser UI.
        </div>
      ) : null}

      <SettingsManager settings={publicSettings} />
    </div>
  );
}
