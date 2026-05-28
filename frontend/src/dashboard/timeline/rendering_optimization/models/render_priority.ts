/**
 * Render priority bucket.
 *
 * Higher values run first inside a frame and survive longer under
 * degradation pressure. The render-scheduler keeps a queue per
 * priority; the frame budget consumes them in descending order so a
 * frame that runs out of time still emits the critical layers.
 */

export enum RenderPriority {
  /** Background tiles, idle decorative effects. */
  IDLE = 0,
  /** Tick labels, gridlines, secondary overlays. */
  LOW = 1,
  /** Segments, rows, primary visualization data. */
  NORMAL = 2,
  /** Selection rings, replay cursor, focused row highlights. */
  HIGH = 3,
  /** Critical safety layers that must always paint (e.g. error banners). */
  CRITICAL = 4,
}

export function isRenderPriority(value: number): value is RenderPriority {
  return value >= RenderPriority.IDLE && value <= RenderPriority.CRITICAL;
}
