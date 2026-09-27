import type { Metadata } from "next";
import Link from "next/link";
import { CircleOff } from "@/components/icons";
import { BrainChat, BrainTools } from "@/components/brain-chat";
import { InlineNotice, PageHeader, Panel, SectionHeading } from "@/components/ui";
import { brainService } from "@/modules/brain";
import { SUPPORTED_SOURCE_EVENTS } from "@/modules/brain/contracts";

export const metadata: Metadata = { title: "Brain" };
export const dynamic = "force-dynamic";

export default async function BrainPage() {
  const status = await brainService.status();
  const capabilities = status.capabilities;

  return (
    <div className="space-y-12">
      <PageHeader
        eyebrow="Core Brain"
        title="Brain"
        description="Everything below is produced by Core Brain. Product sends the request and renders the answer — it holds no intelligence of its own."
      />

      {/* Status strip: one calm row, sentence case, values as badges. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Service" value={status.service ?? "Unavailable"} />
        <Stat label="API version" value={status.apiVersion ?? "—"} />
        <Stat
          label="Methods"
          value={String(status.methodCount || capabilities.length)}
        />
        <Stat label="Provider" value={status.provider ?? "Not reported"} />
      </div>

      {status.reachable ? null : (
        <InlineNotice tone="warning">
          <span className="inline-flex items-start gap-2">
            <CircleOff aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Core Brain is not reachable
              {status.error ? (
                <span className="block text-sm opacity-80">{status.error}</span>
              ) : null}
              . Start it with{" "}
              <code className="rounded bg-[var(--panel-raised)] px-1 py-0.5 text-xs">
                python -m core.transport.http --port 8765
              </code>{" "}
              and set <code className="rounded bg-[var(--panel-raised)] px-1 py-0.5 text-xs">CORE_BRAIN_URL</code>.
            </span>
          </span>
        </InlineNotice>
      )}

      {/* Primary action. One thing to do on this page. */}
      <BrainChat status={status} />

      {/* Secondary tools, deliberately quieter. */}
      <BrainTools status={status} />

      {/* Results / what the Brain can do. */}
      <Panel>
        <SectionHeading
          title="Capabilities"
          description={`${status.methodCount || capabilities.length} methods on the Core Brain API v1`}
        />
        <div className="px-6 py-6">
          <dl className="grid gap-x-10 gap-y-7 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <div key={capability.method}>
                <dt className="flex items-center gap-2">
                  <code className="text-[0.9375rem] font-medium text-[var(--accent)]">
                    {capability.method}
                  </code>
                  {capability.interactive ? (
                    <span className="rounded-full border border-[var(--panel-line)]/80 bg-[var(--panel-raised)] px-2 py-0.5 text-[0.75rem] text-[var(--text-secondary)]">
                      Interactive
                    </span>
                  ) : null}
                </dt>
                <dd className="mt-1.5 text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
                  {capability.summary}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </Panel>

      <Panel>
        <SectionHeading
          title="Event types the Brain understands"
          description="Only these map a source event into memory"
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--panel-line)]/70">
                <th className="px-6 py-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]">
                  Event type
                </th>
                <th className="px-6 py-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]">
                  Source
                </th>
                <th className="px-6 py-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]">
                  Memory type
                </th>
                <th className="px-6 py-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]">
                  Required field
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--panel-line)]/60">
              {SUPPORTED_SOURCE_EVENTS.map((rule) => (
                <tr key={rule.type}>
                  <td className="px-6 py-4">
                    <code className="text-[0.875rem] text-[var(--accent)]">{rule.type}</code>
                  </td>
                  <td className="px-6 py-4 text-[0.9375rem] text-[var(--text-secondary)]">
                    {rule.provider}
                  </td>
                  <td className="px-6 py-4 text-[0.9375rem] text-[var(--text-secondary)]">
                    {rule.memoryType}
                  </td>
                  <td className="px-6 py-4">
                    <code className="text-[0.875rem] text-[var(--text-secondary)]">
                      {rule.required}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <p className="pb-4 text-[0.9375rem] text-[var(--text-muted)]">
        Connection details live in{" "}
        <Link href="/settings" className="text-[var(--accent)]">
          Settings
        </Link>
        .
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--panel-line)]/80 bg-[var(--panel)]/40 px-5 py-5">
      <p className="text-[0.8125rem] text-[var(--text-secondary)]">{label}</p>
      <p className="mt-2 inline-flex rounded-full border border-[var(--accent)]/20 bg-[var(--accent)]/10 px-3 py-1 text-[0.9375rem] font-medium text-[var(--accent)]">
        {value}
      </p>
    </div>
  );
}
