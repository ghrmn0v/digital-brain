"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  CalendarPlus,
  Clock3,
  MapPin,
  Plus,
  Timer,
  Trash2,
  X,
} from "lucide-react";
import type { CalendarEventDto } from "@/modules/calendar/contracts";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  addDuration,
  parseLocalDate,
  parseLocalDateTime,
  toDateInputValue,
  toTimeInputValue,
} from "@/lib/domain/calendar-time";
import {
  formatDate,
  formatDateTime,
  formatTime,
} from "@/lib/client/format";
import {
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  dangerButtonClassName,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";

const durationOptions = [
  { value: 30, label: "30 minutes" },
  { value: 60, label: "1 hour" },
  { value: 90, label: "1 hour 30 minutes" },
  { value: 120, label: "2 hours" },
  { value: 180, label: "3 hours" },
  { value: 240, label: "4 hours" },
  { value: 480, label: "8 hours" },
] as const;

function EventCard({
  event,
  disabled,
  onDelete,
}: {
  event: CalendarEventDto;
  disabled: boolean;
  onDelete: (event: CalendarEventDto) => Promise<void>;
}) {
  return (
    <article className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 gap-4">
        <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl border border-cyan-400/15 bg-cyan-400/[0.07] text-cyan-200">
          <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {new Intl.DateTimeFormat("en-US", { month: "short" }).format(
              new Date(event.startsAt),
            )}
          </span>
          <span className="text-base font-semibold leading-5">
            {new Intl.DateTimeFormat("en-US", { day: "2-digit" }).format(
              new Date(event.startsAt),
            )}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-words text-sm font-semibold text-slate-100">
              {event.title}
            </h3>
            <StatusBadge status={event.status} />
            {event.allDay ? <StatusBadge status="all day" /> : null}
          </div>
          {event.description ? (
            <p className="mt-2 line-clamp-3 max-w-3xl text-sm leading-6 text-slate-500">
              {event.description}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
              {event.allDay ? (
                <>All day · {formatDate(event.startsAt)}</>
              ) : (
                <time dateTime={event.startsAt} title={formatDateTime(event.startsAt)}>
                  {formatDateTime(event.startsAt)} – {formatTime(event.endsAt)}
                </time>
              )}
            </span>
            {event.timeZone ? (
              <span className="inline-flex items-center gap-1.5">
                <MapPin aria-hidden="true" className="h-3.5 w-3.5" />
                {event.timeZone}
              </span>
            ) : null}
            <span>Source: {event.source}</span>
          </div>
        </div>
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!window.confirm(`Delete “${event.title}”? This cannot be undone.`)) return;
          void onDelete(event);
        }}
        className={dangerButtonClassName}
        aria-label={`Delete event ${event.title}`}
      >
        <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
        Delete
      </button>
    </article>
  );
}

export function CalendarManager({
  events,
  total,
}: {
  events: CalendarEventDto[];
  total: number;
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [allDay, setAllDay] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endDate, setEndDate] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(90);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  let timedEndPreview: Date | null = null;
  if (!allDay && startDate && startTime) {
    try {
      timedEndPreview = addDuration(
        parseLocalDateTime(startDate, startTime),
        durationMinutes,
      );
    } catch {}
  }

  function toggleForm() {
    if (!formOpen) {
      const now = new Date();
      const next = new Date(now);
      next.setMinutes(Math.ceil(next.getMinutes() / 30) * 30, 0, 0);
      setStartDate(toDateInputValue(next));
      setStartTime(toTimeInputValue(next));
      const nextDay = new Date(next);
      nextDay.setDate(nextDay.getDate() + 1);
      setEndDate(toDateInputValue(nextDay));
    }
    setFormOpen((open) => !open);
  }

  async function createEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPendingAction("create");
    setError(null);
    setSuccess(null);

    const formData = new FormData(event.currentTarget);
    const title = String(formData.get("title") ?? "").trim();
    const description = String(formData.get("description") ?? "").trim();
    const startDate = String(formData.get("startDate") ?? "");
    const endDate = String(formData.get("endDate") ?? "");
    const startTime = String(formData.get("startTime") ?? "");

    try {
      if (!title || !startDate || (allDay && !endDate)) {
        throw new Error(
          allDay
            ? "Title, start date, and exclusive end date are required."
            : "Title, start date, and start time are required.",
        );
      }

      let startsAt: Date;
      let endsAt: Date;

      if (allDay) {
        startsAt = parseLocalDate(startDate);
        endsAt = parseLocalDate(endDate);
        if (endsAt <= startsAt) {
          endsAt = addDuration(startsAt, 24 * 60);
        }
      } else {
        if (!startTime) {
          throw new Error("Start time is required for a timed event.");
        }
        startsAt = parseLocalDateTime(startDate, startTime);
        endsAt = addDuration(startsAt, durationMinutes);
      }

      if (Number.isNaN(startsAt.getTime()) || Number.isNaN(endsAt.getTime())) {
        throw new Error("Enter a valid date and time range.");
      }
      if (endsAt <= startsAt) {
        throw new Error("The event end must be later than its start.");
      }

      await apiRequest<CalendarEventDto>("/api/calendar", {
        method: "POST",
        body: {
          title,
          description: description || null,
          startsAt: startsAt.toISOString(),
          endsAt: endsAt.toISOString(),
          allDay,
          timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
          status: "confirmed",
        },
      });

      formRef.current?.reset();
      setAllDay(false);
      setStartDate("");
      setStartTime("");
      setEndDate("");
      setDurationMinutes(90);
      setFormOpen(false);
      setSuccess("Calendar event created.");
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Calendar event could not be created."));
    } finally {
      setPendingAction(null);
    }
  }

  async function deleteEvent(event: CalendarEventDto) {
    setPendingAction(`delete:${event.id}`);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<void>(`/api/calendar/${encodeURIComponent(event.id)}`, {
        method: "DELETE",
      });
      setSuccess(`“${event.title}” deleted.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Calendar event could not be deleted."));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-5">
      <Panel>
        <SectionHeading
          title="Add an event"
          description="Choose a start time and duration; the end time is calculated reliably in this browser’s IANA time zone"
          action={
            <button
              type="button"
              onClick={toggleForm}
              aria-expanded={formOpen}
              className={formOpen ? secondaryButtonClassName : primaryButtonClassName}
            >
              {formOpen ? (
                <X aria-hidden="true" className="h-4 w-4" />
              ) : (
                <CalendarPlus aria-hidden="true" className="h-4 w-4" />
              )}
              {formOpen ? "Close" : "New event"}
            </button>
          }
        />
        {formOpen ? (
          <form
            ref={formRef}
            onSubmit={createEvent}
            className="space-y-5 p-5"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Title</span>
                <input
                  name="title"
                  type="text"
                  required
                  maxLength={200}
                  placeholder="Event title"
                  className={inputClassName}
                />
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Description <span className="text-slate-600">optional</span></span>
                <input
                  name="description"
                  type="text"
                  maxLength={10_000}
                  placeholder="Notes or location"
                  className={inputClassName}
                />
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Start date</span>
                <input
                  name="startDate"
                  type="date"
                  required
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className={inputClassName}
                />
              </label>
              {allDay ? (
                <label className="space-y-1.5 text-xs font-medium text-slate-400">
                  <span>End date (exclusive)</span>
                  <input
                    name="endDate"
                    type="date"
                    required
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                    className={inputClassName}
                  />
                </label>
              ) : (
                <>
                  <label className="space-y-1.5 text-xs font-medium text-slate-400">
                    <span>Start time</span>
                    <input
                      name="startTime"
                      type="time"
                      step={60}
                      required
                      value={startTime}
                      onChange={(event) => setStartTime(event.target.value)}
                      className={inputClassName}
                    />
                  </label>
                  <label className="space-y-1.5 text-xs font-medium text-slate-400">
                    <span>Duration</span>
                    <select
                      value={durationMinutes}
                      onChange={(event) =>
                        setDurationMinutes(Number(event.target.value))
                      }
                      className={selectClassName}
                    >
                      {durationOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1.5 text-xs font-medium text-slate-400 sm:col-span-2 lg:col-span-1">
                    <span>Calculated end time</span>
                    <div className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-3.5 text-sm text-cyan-200">
                      <Timer aria-hidden="true" className="h-4 w-4" />
                      {timedEndPreview
                        ? formatTime(timedEndPreview.toISOString())
                        : "Choose start time"}
                    </div>
                  </label>
                </>
              )}
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <label className="inline-flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={allDay}
                  onChange={(event) => setAllDay(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                />
                All-day event
              </label>
              <div className="flex flex-col items-stretch gap-2 sm:items-end">
                <p className="text-xs text-slate-500">
                  {allDay
                    ? "The end date is exclusive; the same date creates a one-day event."
                    : `Ends at ${
                        timedEndPreview
                          ? formatTime(timedEndPreview.toISOString())
                          : "the calculated time"
                      }.`}
                </p>
                <button
                  type="submit"
                  disabled={pendingAction === "create"}
                  className={primaryButtonClassName}
                >
                  {pendingAction === "create" ? (
                    <ButtonSpinner />
                  ) : (
                    <Plus aria-hidden="true" className="h-4 w-4" />
                  )}
                  Create event
                </button>
              </div>
            </div>
          </form>
        ) : null}
      </Panel>

      {error ? <ErrorBanner title="Calendar request failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Event list"
          description={
            total > events.length
              ? `Showing ${events.length} of ${total} matching events`
              : `${total} matching ${total === 1 ? "event" : "events"}`
          }
          action={
            pendingAction && pendingAction !== "create" ? (
              <span className="inline-flex items-center gap-2 text-xs text-cyan-200">
                <ButtonSpinner /> Updating
              </span>
            ) : null
          }
        />
        {events.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {events.map((event) => (
              <EventCard
                key={`${event.id}:${event.status}:${event.updatedAt}`}
                event={event}
                disabled={pendingAction !== null}
                onDelete={deleteEvent}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={CalendarPlus}
            title="No events match this view"
            description="Create a new event above or clear the filters to see the complete local calendar."
          />
        )}
      </Panel>
    </div>
  );
}
