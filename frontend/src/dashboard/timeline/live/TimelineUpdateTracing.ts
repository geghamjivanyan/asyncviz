/**
 * Convenience facade over the live trace ring buffer.
 *
 * Wraps every trace push in a single ``if (enabled)`` so call sites
 * don't have to. Re-exports the trace control surface so the
 * diagnostics page can import a single barrel.
 */

import {
  clearLiveTrace,
  getLiveTraceSnapshot,
  isLiveTraceEnabled,
  recordLiveTrace,
  setLiveTraceEnabled,
  type LiveTraceEntry,
  type LiveTraceKind,
} from "@/dashboard/timeline/live/diagnostics/liveTrace";

export function traceEnvelope(detail: string): void {
  recordLiveTrace({ kind: "envelope", detail });
}

export function traceInvalidate(detail: string): void {
  recordLiveTrace({ kind: "invalidate", detail });
}

export function traceFlush(detail: string): void {
  recordLiveTrace({ kind: "flush", detail });
}

export function traceReplay(detail: string): void {
  recordLiveTrace({ kind: "replay", detail });
}

export function traceActiveTick(detail: string): void {
  recordLiveTrace({ kind: "active-tick", detail });
}

export function traceModeChange(detail: string): void {
  recordLiveTrace({ kind: "mode-change", detail });
}

export function traceFrameRequest(detail: string): void {
  recordLiveTrace({ kind: "frame-request", detail });
}

export {
  clearLiveTrace,
  getLiveTraceSnapshot,
  isLiveTraceEnabled,
  recordLiveTrace,
  setLiveTraceEnabled,
};
export type { LiveTraceEntry, LiveTraceKind };
