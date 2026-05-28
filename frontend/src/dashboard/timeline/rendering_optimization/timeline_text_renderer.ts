/**
 * Text measurement + draw cache.
 *
 * Browser ``CanvasRenderingContext2D.measureText`` is *expensive* —
 * worst-case it lays out the glyph run. We cache by ``font + text``
 * tuples so identical labels (very common: tick labels repeat hundreds
 * of times per frame) measure exactly once.
 *
 * The cache is bounded; eviction is purely LRU. There is no need to
 * version-bump on dataset changes — measurements depend only on font
 * + text, both of which are inputs.
 */

import {
  BoundedLruMap,
  type BoundedLruStats,
} from "@/dashboard/timeline/rendering_optimization/utils/bounded_lru";

export interface TextMetricsEntry {
  /** Approximated CSS-px width. */
  readonly width: number;
  /** Approximated CSS-px ascent. */
  readonly actualAscent: number;
  /** Approximated CSS-px descent. */
  readonly actualDescent: number;
}

/**
 * Subset of the browser ``TextMetrics`` interface we actually need.
 * Declared inline so the module doesn't depend on lib.dom in code
 * paths that run in workers later.
 */
export interface MeasurableTextMetrics {
  readonly width: number;
  readonly actualBoundingBoxAscent?: number;
  readonly actualBoundingBoxDescent?: number;
}

export interface TextMeasurer {
  measure(font: string, text: string): MeasurableTextMetrics;
}

/** Adapter around a real ``CanvasRenderingContext2D``. */
export function canvasTextMeasurer(ctx: CanvasRenderingContext2D): TextMeasurer {
  return {
    measure(font: string, text: string): MeasurableTextMetrics {
      const previous = ctx.font;
      ctx.font = font;
      const metrics = ctx.measureText(text);
      ctx.font = previous;
      return metrics;
    },
  };
}

export interface TextRendererStats extends BoundedLruStats {
  /** Total measure() calls, including cache hits. */
  readonly measureRequests: number;
  /** measureText invocations that escaped the cache. */
  readonly measureMisses: number;
}

export class TimelineTextRenderer {
  private readonly cache: BoundedLruMap<string, TextMetricsEntry>;
  private measureRequests = 0;
  private measureMisses = 0;

  constructor(capacity: number) {
    this.cache = new BoundedLruMap(capacity);
  }

  /** Look up a cached entry, or measure + cache it. */
  measure(measurer: TextMeasurer, font: string, text: string): TextMetricsEntry {
    this.measureRequests += 1;
    const key = `${font}::${text}`;
    const cached = this.cache.get(key);
    if (cached !== undefined) return cached;
    const raw = measurer.measure(font, text);
    const entry: TextMetricsEntry = {
      width: Number.isFinite(raw.width) ? raw.width : 0,
      actualAscent: raw.actualBoundingBoxAscent ?? 0,
      actualDescent: raw.actualBoundingBoxDescent ?? 0,
    };
    this.cache.set(key, entry);
    this.measureMisses += 1;
    return entry;
  }

  has(font: string, text: string): boolean {
    return this.cache.has(`${font}::${text}`);
  }

  stats(): TextRendererStats {
    return {
      ...this.cache.stats(),
      measureRequests: this.measureRequests,
      measureMisses: this.measureMisses,
    };
  }

  clear(): void {
    this.cache.clear();
    this.measureRequests = 0;
    this.measureMisses = 0;
  }
}
