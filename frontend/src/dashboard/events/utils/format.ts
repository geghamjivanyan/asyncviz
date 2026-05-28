/**
 * Display formatting helpers — pure functions.
 */

import type { EventCategory } from "@/dashboard/events/models/eventRow";

const CATEGORY_LABEL: Record<EventCategory, string> = {
  "task.created": "created",
  "task.started": "started",
  "task.waiting": "waiting",
  "task.resumed": "resumed",
  "task.completed": "completed",
  "task.cancelled": "cancelled",
  "task.failed": "failed",
};

export function formatCategory(category: EventCategory): string {
  return CATEGORY_LABEL[category];
}

/** ``HH:MM:SS.mmm`` clock display — empty string when invalid. */
export function formatEventTime(timestampSeconds: number): string {
  if (!Number.isFinite(timestampSeconds) || timestampSeconds <= 0) return "—";
  const ms = timestampSeconds * 1000;
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return "—";
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const mm = String(date.getUTCMinutes()).padStart(2, "0");
  const ss = String(date.getUTCSeconds()).padStart(2, "0");
  const millis = String(date.getUTCMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${millis}`;
}

/** Compact duration — same scale as the task table for consistency. */
export function formatEventDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 0.001) return `${(seconds * 1_000_000).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  return `${Math.floor(seconds / 60)}m${(seconds % 60).toFixed(0)}s`;
}

/** Compress an id when it doesn't fit the column. */
export function formatTaskIdCompact(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 6)}…${id.slice(-4)}`;
}
