/**
 * Reusable canvas textures for lifecycle-segment decorations.
 *
 * The cache pre-bakes diagonal hatches, dot patterns, and gradients
 * onto offscreen canvases so each frame stamps the cached
 * :class:`CanvasPattern` instead of running the per-pixel math
 * inline. Patterns are keyed by ``(kind, color, size, density)``.
 *
 * The cache degrades gracefully when the host environment does not
 * support ``createPattern`` (older jsdom builds, OffscreenCanvas
 * fallbacks). Callers should fall back to a flat fill when ``null`` is
 * returned.
 */

interface CacheEntry {
  pattern: CanvasPattern;
}

export class TimelineSegmentTextureCache {
  private patternsByKey = new Map<string, CacheEntry>();
  private hits = 0;
  private misses = 0;

  /** Diagonal hatch — used for waiting / sleeping segments. */
  hatch(ctx: CanvasRenderingContext2D, color: string, size = 6): CanvasPattern | null {
    return this.cachedPattern(ctx, `hatch|${size}|${color}`, (off) => {
      off.width = size;
      off.height = size;
      const offCtx = off.getContext("2d");
      if (offCtx === null) return false;
      offCtx.strokeStyle = color;
      offCtx.lineWidth = 1;
      offCtx.beginPath();
      offCtx.moveTo(0, size);
      offCtx.lineTo(size, 0);
      offCtx.stroke();
      return true;
    });
  }

  /** Light dotted texture — used for replay-focused segments. */
  dots(ctx: CanvasRenderingContext2D, color: string, size = 6): CanvasPattern | null {
    return this.cachedPattern(ctx, `dots|${size}|${color}`, (off) => {
      off.width = size;
      off.height = size;
      const offCtx = off.getContext("2d");
      if (offCtx === null) return false;
      offCtx.fillStyle = color;
      offCtx.beginPath();
      offCtx.arc(size / 2, size / 2, Math.max(0.75, size / 6), 0, Math.PI * 2);
      offCtx.fill();
      return true;
    });
  }

  clear(): void {
    this.patternsByKey.clear();
  }

  size(): number {
    return this.patternsByKey.size;
  }

  hitCount(): number {
    return this.hits;
  }

  missCount(): number {
    return this.misses;
  }

  private cachedPattern(
    ctx: CanvasRenderingContext2D,
    key: string,
    paint: (off: HTMLCanvasElement) => boolean,
  ): CanvasPattern | null {
    const cached = this.patternsByKey.get(key);
    if (cached !== undefined) {
      this.hits += 1;
      return cached.pattern;
    }
    this.misses += 1;
    if (typeof document === "undefined") return null;
    const off = document.createElement("canvas");
    if (!paint(off)) return null;
    const pattern = ctx.createPattern(off, "repeat");
    if (pattern === null) return null;
    this.patternsByKey.set(key, { pattern });
    return pattern;
  }
}
