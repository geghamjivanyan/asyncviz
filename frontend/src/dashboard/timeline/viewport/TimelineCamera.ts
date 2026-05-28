/**
 * Camera state — what slice of the world is currently visible.
 *
 * The camera is *world-coordinate* state; the viewport (CSS pixels)
 * is rendered against it via the coordinate system. Keeping them
 * separate lets us swap renderers (canvas, WebGL, OffscreenCanvas)
 * without re-deriving zoom math.
 *
 * World coordinates:
 *
 *   * X axis — monotonic seconds (a stable double-precision scale).
 *   * Y axis — row index, integer-valued.
 *
 * The camera is *immutable*: every mutation produces a fresh object.
 * Reducers are pure functions so tests can drive zoom/pan without
 * mounting React.
 */

export interface TimelineCamera {
  /** Left edge of the visible window in world seconds. */
  timeStart: number;
  /** Right edge of the visible window in world seconds. */
  timeEnd: number;
  /** Index of the topmost visible row (fractional values allowed). */
  rowStart: number;
  /** Height of a single row in CSS pixels. */
  rowHeight: number;
}

export const DEFAULT_ROW_HEIGHT_PX = 18;

export const DEFAULT_CAMERA: TimelineCamera = {
  timeStart: 0,
  timeEnd: 1,
  rowStart: 0,
  rowHeight: DEFAULT_ROW_HEIGHT_PX,
};

/** Pure: bound a value within an inclusive range. */
function clamp(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/** Pure: ``true`` when two cameras have identical visible state. */
export function cameraEqual(a: TimelineCamera, b: TimelineCamera): boolean {
  return (
    a.timeStart === b.timeStart &&
    a.timeEnd === b.timeEnd &&
    a.rowStart === b.rowStart &&
    a.rowHeight === b.rowHeight
  );
}

/** Pure: visible duration in seconds (always > 0). */
export function cameraDuration(camera: TimelineCamera): number {
  return Math.max(Number.EPSILON, camera.timeEnd - camera.timeStart);
}

/** Pure: move the camera by delta seconds along the X axis. */
export function panCamera(camera: TimelineCamera, deltaSeconds: number): TimelineCamera {
  return {
    ...camera,
    timeStart: camera.timeStart + deltaSeconds,
    timeEnd: camera.timeEnd + deltaSeconds,
  };
}

/** Pure: scroll the camera by delta rows along the Y axis. */
export function scrollCamera(camera: TimelineCamera, deltaRows: number): TimelineCamera {
  return {
    ...camera,
    rowStart: camera.rowStart + deltaRows,
  };
}

/** Pure: clamp ``rowStart`` so we never scroll past the bottom row. */
export function clampRowStart(
  camera: TimelineCamera,
  visibleRows: number,
  totalRows: number,
): TimelineCamera {
  const lastValidStart = Math.max(0, totalRows - visibleRows);
  return { ...camera, rowStart: clamp(camera.rowStart, 0, lastValidStart) };
}

/**
 * Pure: zoom the camera around an anchor (in world seconds). ``factor``
 * > 1 zooms out; ``factor`` < 1 zooms in. ``minDuration`` /
 * ``maxDuration`` clamp the resulting window so a runaway wheel can't
 * produce a degenerate camera.
 */
export function zoomCameraAroundTime(
  camera: TimelineCamera,
  anchorSeconds: number,
  factor: number,
  options: { minDurationSeconds?: number; maxDurationSeconds?: number } = {},
): TimelineCamera {
  if (!Number.isFinite(factor) || factor <= 0) return camera;
  const minDuration = options.minDurationSeconds ?? 1e-6;
  const maxDuration = options.maxDurationSeconds ?? 1e9;
  const currentDuration = cameraDuration(camera);
  const nextDuration = clamp(currentDuration * factor, minDuration, maxDuration);
  // Preserve the anchor's position within the visible window.
  const t = (anchorSeconds - camera.timeStart) / currentDuration;
  const nextStart = anchorSeconds - t * nextDuration;
  const nextEnd = nextStart + nextDuration;
  return { ...camera, timeStart: nextStart, timeEnd: nextEnd };
}

/** Pure: change the row height (no pan side-effects). */
export function setRowHeight(camera: TimelineCamera, rowHeightPx: number): TimelineCamera {
  return { ...camera, rowHeight: Math.max(1, Math.floor(rowHeightPx)) };
}

/** Pure: rebuild a camera so it spans ``[timeStart, timeEnd]`` exactly. */
export function fitCameraToRange(
  camera: TimelineCamera,
  timeStart: number,
  timeEnd: number,
): TimelineCamera {
  if (timeEnd <= timeStart) return camera;
  return { ...camera, timeStart, timeEnd };
}
