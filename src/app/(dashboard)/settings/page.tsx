import type { Metadata } from "next";
import {
  BrainCircuit,
  CheckCircle2,
  CircleOff,
  RadioTower,
  Settings2,
} from "lucide-react";
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
    <article className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-700 bg-slate-800/70 text-slate-300">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
        <Badge tone={configured ? "success" : "neutral"} dot>
          {configured ? "Configured" : "Not configured"}
        </Badge>
      </div>
      <h3 className="mt-5 text-sm font-semibold text-slate-100">{name}</h3>
      <p className="mt-1.5 text-sm leading-6 text-slate-500">{description}</p>
      <div className="mt-4 flex items-center gap-2 border-t border-slate-800/70 pt-3 text-xs text-slate-500">
        <StatusIcon
          aria-hidden="true"
          className={configured ? "h-3.5 w-3.5 text-emerald-300" : "h-3.5 w-3.5 text-slate-600"}
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
        <div className="grid gap-px bg-slate-800 md:grid-cols-2">
          <ReadinessCard
            name="Core Brain"
            description="Outbound normalized-event delivery and future read adapters remain server-only."
            configured={coreBrainConfigured}
            icon={BrainCircuit}
          />
          <div className="hidden min-[900px]:block">
            <ReadinessCard
              name="Fly events"
              description="The desktop product can deliver normalized events through the existing Connectome layer."
              configured={flyConfigured}
              icon={RadioTower}
            />
          </div>
        </div>
        <div className="hidden items-start gap-3 border-t border-slate-800 px-5 py-4 text-xs leading-5 text-slate-500 min-[900px]:flex">
          <Settings2 aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-300" />
          CORE_BRAIN_API_TOKEN and FLY_API_TOKEN are never read, returned, or
          rendered by this interface.
        </div>
      </Panel>

      {restrictedSettingCount > 0 ? (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.07] px-4 py-3 text-sm text-amber-100">
          {restrictedSettingCount} potentially sensitive {restrictedSettingCount === 1 ? "setting is" : "settings are"} withheld from the browser UI.
        </div>
      ) : null}

      <SettingsManager settings={publicSettings} />
    </div>
  );
}
