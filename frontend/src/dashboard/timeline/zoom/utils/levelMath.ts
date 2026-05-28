/**
 * Pure math for converting between visible-duration + normalized zoom
 * level.
 *
 * The level space is logarithmic so equal-sized keyboard / wheel
 * steps feel uniform across the full range from sub-millisecond zoom
 * to hour-long traces.
 */

export interface LevelBounds {
  minDurationSeconds: number;
  maxDurationSeconds: number;
}

/** Pure: convert a duration to a normalized ``[0, 1]`` zoom level. */
export function durationToLevel(durationSeconds: number, bounds: LevelBounds): number {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return 0;
  if (bounds.maxDurationSeconds <= bounds.minDurationSeconds) return 1;
  const clamped = Math.min(
    bounds.maxDurationSeconds,
    Math.max(bounds.minDurationSeconds, durationSeconds),
  );
  const lnMin = Math.log(bounds.minDurationSeconds);
  const lnMax = Math.log(bounds.maxDurationSeconds);
  return 1 - (Math.log(clamped) - lnMin) / (lnMax - lnMin);
}

/** Pure: convert a normalized ``[0, 1]`` zoom level back to duration. */
export function levelToDuration(level: number, bounds: LevelBounds): number {
  if (!Number.isFinite(level)) return bounds.maxDurationSeconds;
  const clamped = Math.max(0, Math.min(1, level));
  if (bounds.maxDurationSeconds <= bounds.minDurationSeconds) {
    return bounds.minDurationSeconds;
  }
  const lnMin = Math.log(bounds.minDurationSeconds);
  const lnMax = Math.log(bounds.maxDurationSeconds);
  return Math.exp(lnMin + (1 - clamped) * (lnMax - lnMin));
}

/** Pure: ratio of next/current duration when applying a level delta. */
export function factorFromLevelDelta(
  currentDurationSeconds: number,
  levelDelta: number,
  bounds: LevelBounds,
): number {
  if (!Number.isFinite(levelDelta) || levelDelta === 0) return 1;
  const currentLevel = durationToLevel(currentDurationSeconds, bounds);
  const nextLevel = Math.max(0, Math.min(1, currentLevel + levelDelta));
  const nextDuration = levelToDuration(nextLevel, bounds);
  if (!Number.isFinite(nextDuration) || currentDurationSeconds <= 0) return 1;
  return nextDuration / currentDurationSeconds;
}
