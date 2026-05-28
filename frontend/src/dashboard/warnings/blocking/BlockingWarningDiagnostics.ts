/**
 * Diagnostics surface — re-exports the trace + metrics getters for
 * the central diagnostics page.
 *
 * Living in one barrel keeps the import surface readable + makes the
 * panel's diagnostics contract explicit.
 */

export {
  clearBlockingWarningTrace,
  getBlockingWarningTraceSnapshot,
  isBlockingWarningTraceEnabled,
  recordBlockingWarningTrace,
  setBlockingWarningTraceEnabled,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
export type {
  BlockingWarningTraceEntry,
  BlockingWarningTraceKind,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";

export {
  getBlockingWarningPanelMetrics,
  resetBlockingWarningPanelMetrics,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
export type {
  BlockingWarningPanelMetricsSnapshot,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
