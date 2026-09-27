import { Braces } from "@/components/icons";
import { cn } from "@/components/ui";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function formatPrimitive(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  return String(value);
}

function primitiveClassName(value: unknown): string {
  if (value === null) return "text-[var(--text-muted)]";
  if (typeof value === "boolean") return "text-[var(--warning)]";
  if (typeof value === "number") return "text-[var(--accent)]";
  return "text-[var(--success)]";
}

function JsonNode({
  label,
  value,
  depth = 0,
}: {
  label: string;
  value: unknown;
  depth?: number;
}) {
  if (Array.isArray(value)) {
    return (
      <div className={cn(depth > 0 && "ml-3 border-l border-[var(--panel-line)] pl-3")}>
        <p className="text-xs font-semibold text-[var(--text-primary)]">
          {label}
          <span className="ml-1 font-normal text-[var(--text-muted)]">[{value.length}]</span>
        </p>
        <div className="mt-1.5 space-y-1.5">
          {value.length > 0 ? (
            value.map((item, index) => (
              <JsonNode
                key={`${label}-${index}`}
                label={`${index}`}
                value={item}
                depth={depth + 1}
              />
            ))
          ) : (
            <p className="text-xs text-[var(--text-muted)]">Empty array</p>
          )}
        </div>
      </div>
    );
  }

  if (isRecord(value)) {
    const entries = Object.entries(value);
    return (
      <div className={cn(depth > 0 && "ml-3 border-l border-[var(--panel-line)] pl-3")}>
        <p className="text-xs font-semibold text-[var(--text-primary)]">{label}</p>
        {entries.length > 0 ? (
          <div className="mt-1.5 space-y-1.5">
            {entries.map(([key, item]) => (
              <JsonNode key={key} label={key} value={item} depth={depth + 1} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">Empty object</p>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn( "grid min-w-0 gap-1 py-0.5 sm:grid-cols-[minmax(7rem,0.35fr)_1fr] sm:gap-3",
        depth > 0 && "ml-3 border-l border-[var(--panel-line)] pl-3",
      )}
    >
      <span className="break-words text-xs font-semibold text-[var(--text-secondary)]">{label}</span>
      <span
        className={cn( "min-w-0 break-words font-mono text-xs leading-5", primitiveClassName(value),
        )}
      >
        {formatPrimitive(value) || <span className="text-[var(--text-muted)]">Empty string</span>}
      </span>
    </div>
  );
}

export function JsonViewer({
  value,
  label = "Payload",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--background)] p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
        <Braces aria-hidden="true" className="h-3.5 w-3.5 text-[var(--accent)]" />
        {label}
      </div>
      {isRecord(value) ? (
        <div>
          {Object.entries(value).length > 0 ? (
            Object.entries(value).map(([key, item]) => (
              <JsonNode key={key} label={key} value={item} />
            ))
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No payload fields</p>
          )}
        </div>
      ) : (
        <JsonNode label={label} value={value} />
      )}
    </div>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-64 overflow-auto rounded-lg border border-[var(--panel-line)] bg-[var(--background)] p-4 font-mono text-xs leading-5 text-[var(--text-primary)]">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
