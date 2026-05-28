/**
 * Display formatting helpers — pure functions.
 */

export function formatLagMs(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m`;
}

export function formatDurationMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1) return `${ms.toFixed(2)}ms`;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatPercent(fraction: number): string {
  if (!Number.isFinite(fraction)) return "—";
  const clamped = Math.min(1, Math.max(0, fraction));
  return `${(clamped * 100).toFixed(0)}%`;
}

export function formatSequence(value: number | null): string {
  if (value === null) return "—";
  if (value < 1000) return String(value);
  if (value < 1_000_000) return `${(value / 1000).toFixed(1)}k`;
  return `${(value / 1_000_000).toFixed(1)}M`;
}

export function formatWallTime(wallMs: number): string {
  if (!Number.isFinite(wallMs) || wallMs <= 0) return "—";
  const date = new Date(wallMs);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toISOString().slice(11, 19);
}
