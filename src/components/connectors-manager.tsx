"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpenText,
  CalendarDays,
  Globe2,
  LockKeyhole,
  MessageCircle,
  PlugZap,
  Send,
} from "@/components/icons";
import type { ConnectorDto } from "@/modules/connectors/contracts";
import { Switch } from "@/components/switch";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import { formatDateTime } from "@/lib/client/format";
import {
  Badge,
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  InlineNotice,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
} from "@/components/ui";

type ConnectorView = Pick<
  ConnectorDto,
  | "id"
  | "name"
  | "type"
  | "version"
  | "enabled"
  | "status"
  | "lastSyncAt"
  | "lastError"
  | "updatedAt"
>;

const connectorIcons = {
  linkedin: Send,
  calendar: CalendarDays,
  whatsapp: MessageCircle,
  telegram: Send,
  browser: Globe2,
  notes: BookOpenText,
} as const;

function ConnectorCard({
  connector,
  disabled,
  onToggle,
}: {
  connector: ConnectorView;
  disabled: boolean;
  onToggle: (connector: ConnectorView, enabled: boolean) => Promise<boolean>;
}) {
  const [enabled, setEnabled] = useState(connector.enabled);
  const [pending, setPending] = useState(false);
  const Icon = connectorIcons[connector.type as keyof typeof connectorIcons] ?? PlugZap;

  async function toggle(next: boolean) {
    setEnabled(next);
    setPending(true);
    try {
      const succeeded = await onToggle(connector, next);
      if (!succeeded) setEnabled(connector.enabled);
    } finally {
      setPending(false);
    }
  }

  return (
    <article className="relative overflow-hidden p-5">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)]/75 text-[var(--text-primary)]">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-words text-sm font-semibold text-[var(--text-primary)]">
              {connector.name}
            </h3>
            <StatusBadge status={connector.status} />
            {enabled ? <Badge tone="success">Enabled</Badge> : <Badge>Inactive</Badge>}
          </div>
          <p className="mt-1.5 font-mono text-xs text-[var(--text-muted)]">
            {connector.type} · v{connector.version}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Switch
            checked={enabled}
            disabled={disabled || pending}
            label={`${enabled ? "Disable" : "Enable"} ${connector.name}`}
            onCheckedChange={(next) => void toggle(next)}
          />
          {pending ? <ButtonSpinner /> : null}
        </div>
      </div>

      <dl className="mt-5 grid gap-4 border-t border-[var(--panel-line)]/70 pt-4 text-xs sm:grid-cols-2">
        <div>
          <dt className="font-medium text-[var(--text-muted)]">Last sync</dt>
          <dd className="mt-1.5 text-[var(--text-primary)]">
            {connector.lastSyncAt ? (
              <time dateTime={connector.lastSyncAt} title={formatDateTime(connector.lastSyncAt)}>
                {formatDateTime(connector.lastSyncAt)}
              </time>
            ) : (
              "No sync recorded"
            )}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-[var(--text-muted)]">Last error</dt>
          <dd
            className={
              connector.lastError
                ? "mt-1.5 break-words leading-5 text-[var(--danger)]"
                : "mt-1.5 text-[var(--text-secondary)]"
            }
          >
            {connector.lastError || "No connector error recorded"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

export function ConnectorsManager({ connectors }: { connectors: ConnectorView[] }) {
  const router = useRouter();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function toggleConnector(
    connector: ConnectorView,
    enabled: boolean,
  ): Promise<boolean> {
    setPendingId(connector.id);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<ConnectorDto>(
        `/api/connectors/${encodeURIComponent(connector.id)}`,
        { method: "PATCH", body: { enabled } },
      );
      setSuccess(`${connector.name} ${enabled ? "enabled" : "disabled"}.`);
      router.refresh();
      return true;
    } catch (caught) {
      setError(getErrorMessage(caught, "Connector could not be updated."));
      return false;
    } finally {
      setPendingId(null);
    }
  }

  const healthy = connectors.filter(
    (connector) => connector.status === "healthy",
  ).length;
  const enabled = connectors.filter((connector) => connector.enabled).length;

  return (
    <div className="space-y-5">
      <InlineNotice>
        Credential references and credential values are intentionally excluded
        from this interface. Configure them outside Product and expose only health
        state here.
      </InlineNotice>
      {error ? <ErrorBanner title="Connector request failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel)]/55 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Seeded</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{connectors.length}</p>
        </div>
        <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel)]/55 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Enabled</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{enabled}</p>
        </div>
        <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel)]/55 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Healthy</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{healthy}</p>
        </div>
      </div>

      <Panel>
        <SectionHeading
          title="Connector registry"
          description="Real connector records from the local database"
          action={
            <span className="inline-flex items-center gap-2 text-xs text-[var(--text-muted)]">
              <LockKeyhole aria-hidden="true" className="h-3.5 w-3.5" />
              Secrets hidden
            </span>
          }
        />
        {connectors.length > 0 ? (
          <div className="grid gap-px bg-[var(--panel-raised)] lg:grid-cols-2">
            {connectors.map((connector) => (
              <ConnectorCard
                key={`${connector.id}:${connector.enabled}:${connector.updatedAt}`}
                connector={connector}
                disabled={pendingId !== null}
                onToggle={toggleConnector}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={PlugZap}
            title="No connectors available"
            description="No connector records. Seed the registry first."
          />
        )}
      </Panel>
    </div>
  );
}
