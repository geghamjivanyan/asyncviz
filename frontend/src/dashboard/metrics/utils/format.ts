/**
 * Display formatting helpers — pure functions for the metrics cards.
 */

export function formatRate(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "0/s";
  if (value === 0) return "0/s";
  if (value < 0.01) return "<0.01/s";
  if (value < 10) return `${value.toFixed(2)}/s`;
  if (value < 100) return `${value.toFixed(1)}/s`;
  if (value < 1000) return `${value.toFixed(0)}/s`;
  if (value < 10_000) return `${(value / 1000).toFixed(2)}k/s`;
  return `${(value / 1000).toFixed(0)}k/s`;
}

export function formatCount(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "0";
  if (value < 1000) return String(value);
  if (value < 10_000) return `${(value / 1000).toFixed(2)}k`;
  if (value < 1_000_000) return `${(value / 1000).toFixed(0)}k`;
  return `${(value / 1_000_000).toFixed(1)}M`;
}

export function formatUptime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (minutes < 60) return `${minutes}m${secs.toString().padStart(2, "0")}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return `${hours}h${mins.toString().padStart(2, "0")}m`;
  const days = Math.floor(hours / 24);
  const hrs = hours % 24;
  return `${days}d${hrs.toString().padStart(2, "0")}h`;
}

export function formatLagMs(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m`;
}

export function formatPercent(fraction: number): string {
  if (!Number.isFinite(fraction)) return "—";
  const clamped = Math.min(1, Math.max(0, fraction));
  return `${(clamped * 100).toFixed(0)}%`;
}

export function formatSequence(value: number | null): string {
  if (value === null) return "—";
  return formatCount(value);
}
