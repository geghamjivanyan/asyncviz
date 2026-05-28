/**
 * Display formatting helpers — pure functions, no DOM, no state.
 *
 * These are shared between the cell components and the test suite.
 */

/** Render a duration in seconds as a human-readable string. */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  if (seconds < 0) return "—";
  if (seconds < 0.001) return `${(seconds * 1_000_000).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m${remainder.toFixed(0)}s`;
}

/** Render an epoch (wall seconds) as a short clock string. */
export function formatStartTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return "—";
  const ms = seconds * 1000;
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return "—";
  // HH:MM:SS — short enough to fit a narrow column.
  return date.toISOString().slice(11, 19);
}

/** Render an id with a single mid-ellipsis to keep it scannable. */
export function formatTaskIdShort(id: string | null): string {
  if (id === null || id === "") return "—";
  if (id.length <= 12) return id;
  return `${id.slice(0, 6)}…${id.slice(-4)}`;
}

/** Render a warning count as a short label. */
export function formatWarningCount(count: number): string {
  if (count === 0) return "—";
  return count > 99 ? "99+" : String(count);
}
