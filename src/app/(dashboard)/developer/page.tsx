import type { Metadata } from "next";
import Link from "next/link";
import {
  Bot,
  BrainCircuit,
  Code2,
  GitBranch,
  MonitorSmartphone,
  RadioTower,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { DeveloperInformationFeed } from "@/components/developer-information-feed";
import { DeveloperProposalsManager } from "@/components/developer-proposals-manager";
import {
  Badge,
  InlineNotice,
  PageHeader,
  Panel,
  SectionHeading,
  secondaryButtonClassName,
} from "@/components/ui";
import { developerModeService } from "@/modules/developer-mode";

export const metadata: Metadata = { title: "Developer Mode" };

export default async function DeveloperPage() {
  const [enabled, proposals, information] = await Promise.all([
    developerModeService.isEnabled(),
    developerModeService.listProposals(100),
    developerModeService.listInformation(100),
  ]);
  const repositories = [
    ...new Set(proposals.map((proposal) => proposal.repository)),
  ];

  return (
    <div className="space-y-6">
      <div className="hidden min-[900px]:block">
        <PageHeader
          eyebrow="Desktop capability"
          title="Developer Mode"
          description="Control repository-aware developer proposals while keeping all intelligence in Core Brain and every external action behind explicit permission."
          actions={
            <Badge tone={enabled ? "success" : "neutral"} dot>
              {enabled ? "Enabled" : "Off by default"}
            </Badge>
          }
        />

        {!enabled ? (
          <Panel className="p-6">
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Developer Mode is off
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                  Existing product behavior is unchanged. Shared Developer Updates
                  remain available, while the desktop workspace and proposal actions
                  stay inactive.
                </p>
              </div>
              <Link href="/settings" className={secondaryButtonClassName}>
                Open desktop settings
              </Link>
            </div>
          </Panel>
        ) : (
          <>
            <Panel>
              <SectionHeading
                title="Developer execution boundary"
                description="Preparation only — repository, Git, testing, and deployment ports have no implementation"
              />
              <div className="grid gap-px bg-slate-800 sm:grid-cols-2 xl:grid-cols-5">
                {[
                  { label: "Core Brain", detail: "Analysis and explanation", icon: BrainCircuit },
                  { label: "Product API", detail: "Validate and persist", icon: Bot },
                  { label: "Permission", detail: "Approve or reject", icon: ShieldCheck },
                  { label: "Action", detail: "Future explicit execution", icon: Code2 },
                  { label: "Fly", detail: "Existing Connectome event", icon: RadioTower },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="bg-slate-900/70 p-5">
                      <Icon aria-hidden="true" className="h-4 w-4 text-cyan-300" />
                      <p className="mt-3 text-sm font-semibold text-slate-200">
                        {item.label}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        {item.detail}
                      </p>
                    </div>
                  );
                })}
              </div>
            </Panel>

            <div className="grid gap-4 sm:grid-cols-3">
              <Panel className="p-5">
                <Code2 aria-hidden="true" className="h-4 w-4 text-cyan-300" />
                <p className="mt-3 text-sm font-semibold text-slate-200">
                  Repository context
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {repositories.length > 0
                    ? repositories.join(", ")
                    : "Waiting for Core Brain repository context"}
                </p>
              </Panel>
              <Panel className="p-5">
                <GitBranch aria-hidden="true" className="h-4 w-4 text-amber-300" />
                <p className="mt-3 text-sm font-semibold text-slate-200">Git port</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Interface prepared; no Git command or mutation is implemented.
                </p>
              </Panel>
              <Panel className="p-5">
                <Rocket aria-hidden="true" className="h-4 w-4 text-emerald-300" />
                <p className="mt-3 text-sm font-semibold text-slate-200">
                  Test and deploy ports
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Future capabilities only; no test runner or deployment adapter exists.
                </p>
              </Panel>
            </div>

            <DeveloperProposalsManager initialProposals={proposals} />
            <DeveloperInformationFeed items={information} />
          </>
        )}
      </div>

      <div className="space-y-6 min-[900px]:hidden">
        <PageHeader
          eyebrow="Platform capability"
          title="Developer Mode is desktop-only"
          description="Mobile does not run local repository analysis, Fly workflows, or developer action controls."
        />
        <InlineNotice tone="warning">
          <span className="inline-flex items-start gap-2">
            <MonitorSmartphone aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            Open Developer Updates to read the developer information generated by
            Core Brain on this device.
          </span>
        </InlineNotice>
        <Link href="/developer-information" className={secondaryButtonClassName}>
          Open shared Developer Updates
        </Link>
      </div>
    </div>
  );
}
