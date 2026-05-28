/**
 * Lightweight in-process trace ring for the replay timeline.
 *
 * Off by default — flipping :func:`setReplayTimelineTraceEnabled`
 * starts collecting. The ring is 256 entries; older entries fall
 * off the back. The diagnostics page surfaces the tail.
 */

export type ReplayTimelineTraceKind =
  | "scrub-start"
  | "scrub-update"
  | "scrub-end"
  | "seek-requested"
  | "seek-completed"
  | "marker-focus"
  | "bookmark-focus"
  | "bookmark-added"
  | "bookmark-removed"
  | "keyboard"
  | "playback-state-change"
  | "viewport-change"
  | "engine-sync";

export interface ReplayTimelineTraceEntry {
  readonly timestampMs: number;
  readonly kind: ReplayTimelineTraceKind;
  readonly detail: string;
}

const CAPACITY = 256;
let entries: ReplayTimelineTraceEntry[] = [];
let enabled = false;

export function setReplayTimelineTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) entries = [];
}

export function isReplayTimelineTraceEnabled(): boolean {
  return enabled;
}

export function recordReplayTimelineTrace(
  kind: ReplayTimelineTraceKind,
  detail: string = "",
): void {
  if (!enabled) return;
  entries.push({
    timestampMs: Date.now(),
    kind,
    detail,
  });
  if (entries.length > CAPACITY) {
    entries.splice(0, entries.length - CAPACITY);
  }
}

export function getReplayTimelineTrace(): readonly ReplayTimelineTraceEntry[] {
  return entries.slice();
}

export function clearReplayTimelineTrace(): void {
  entries = [];
}
