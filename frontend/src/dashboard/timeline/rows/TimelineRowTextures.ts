/**
 * Reusable canvas textures for row decorations.
 *
 * The renderer pre-bakes diagonal patterns (e.g. "warning hatch")
 * onto a small offscreen canvas so each frame stamps the cached
 * pattern instead of re-running the per-pixel math. Patterns are
 * keyed by color so multiple textures coexist without thrash.
 *
 * The module degrades gracefully when the host environment does not
 * support ``createPattern`` (older jsdom) — the cache returns ``null``
 * and callers fall back to a flat fill.
 */

interface CacheEntry {
  pattern: CanvasPattern;
}

export class TimelineRowTextureCache {
  private patternsByKey = new Map<string, CacheEntry>();

  /** Diagonal hatch pattern. Returns ``null`` when ``createPattern`` is
   *  unavailable in the host environment. */
  hatch(ctx: CanvasRenderingContext2D, color: string, size = 6): CanvasPattern | null {
    const key = `hatch|${size}|${color}`;
    const cached = this.patternsByKey.get(key);
    if (cached !== undefined) return cached.pattern;

    if (typeof document === "undefined") return null;
    const off = document.createElement("canvas");
    off.width = size;
    off.height = size;
    const offCtx = off.getContext("2d");
    if (offCtx === null) return null;
    offCtx.strokeStyle = color;
    offCtx.lineWidth = 1;
    offCtx.beginPath();
    offCtx.moveTo(0, size);
    offCtx.lineTo(size, 0);
    offCtx.stroke();
    const pattern = ctx.createPattern(off, "repeat");
    if (pattern === null) return null;
    this.patternsByKey.set(key, { pattern });
    return pattern;
  }

  clear(): void {
    this.patternsByKey.clear();
  }

  size(): number {
    return this.patternsByKey.size;
  }
}
