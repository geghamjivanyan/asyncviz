/**
 * Lightweight debug tracer for the runtime store.
 *
 * Disabled by default. When enabled (``setStoreTraceEnabled(true)`` —
 * future diagnostics-page toggle), every action records a structured
 * event into a bounded ring buffer. The diagnostics page reads the
 * ring; nothing writes to ``console.log``.
 */

import type { DiagnosticsTrace } from "@/state/runtime/models";

const CAPACITY = 256;

let enabled = false;
const ring: DiagnosticsTrace[] = [];

export function setStoreTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isStoreTraceEnabled(): boolean {
  return enabled;
}

export function recordTrace(event: Omit<DiagnosticsTrace, "at">): void {
  if (!enabled) return;
  ring.push({ ...event, at: performance.now() });
  while (ring.length > CAPACITY) ring.shift();
}

export function getTraceSnapshot(): readonly DiagnosticsTrace[] {
  return [...ring];
}

export function clearTrace(): void {
  ring.length = 0;
}
