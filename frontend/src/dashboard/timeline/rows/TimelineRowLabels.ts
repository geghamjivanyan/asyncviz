/**
 * Row label rendering.
 *
 * The label renderer owns the typography decisions inside the label
 * column:
 *
 *   * HiDPI-safe baseline + font selection,
 *   * binary-search label truncation with an ``…`` suffix,
 *   * primary task label + secondary coroutine label,
 *   * lineage indentation via the row layout,
 *   * memoized text measurements via the shared text cache.
 *
 * The module is pure (no React) and accepts a small injection point
 * for the text cache so tests can validate cache hits without poking
 * private state.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import { rowLabelText, rowSecondaryText } from "@/dashboard/timeline/rows/TimelineRowColors";
import type { TimelineRowLayoutSnapshot } from "@/dashboard/timeline/rows/TimelineRowLayout";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import { TimelineRowTextCache, type CachedLabel } from "@/dashboard/timeline/rows/TimelineRowCaching";
import type { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";

export interface RowLabelRendererOptions {
  /** Primary label font (px-sized, system stack). */
  primaryFont?: string;
  /** Secondary coroutine font. */
  secondaryFont?: string;
  /** Vertical offset for the primary text baseline. */
  primaryBaselineOffset?: number;
  /** Vertical offset for the secondary text baseline. */
  secondaryBaselineOffset?: number;
  /** Shared text cache. */
  cache?: TimelineRowTextCache;
  /** Optional metrics sink for cache + truncation accounting. */
  metrics?: TimelineRowMetrics;
}

export interface RowLabelRenderArgs {
  ctx: CanvasRenderingContext2D;
  palette: TimelineColorPalette;
  layout: TimelineRowLayoutSnapshot;
  row: TimelineRowProjectionEntry;
  rowTopY: number;
}

const DEFAULT_PRIMARY_FONT = "12px ui-sans-serif, system-ui, -apple-system, sans-serif";
const DEFAULT_SECONDARY_FONT = "10px ui-monospace, SFMono-Regular, Menlo, monospace";

const ELLIPSIS = "…";

export class TimelineRowLabelRenderer {
  private readonly primaryFont: string;
  private readonly secondaryFont: string;
  private readonly primaryBaselineOffset: number;
  private readonly secondaryBaselineOffset: number;
  private readonly cache: TimelineRowTextCache;
  private readonly metrics?: TimelineRowMetrics;

  constructor(options: RowLabelRendererOptions = {}) {
    this.primaryFont = options.primaryFont ?? DEFAULT_PRIMARY_FONT;
    this.secondaryFont = options.secondaryFont ?? DEFAULT_SECONDARY_FONT;
    this.primaryBaselineOffset = options.primaryBaselineOffset ?? 12;
    this.secondaryBaselineOffset = options.secondaryBaselineOffset ?? 19;
    this.cache = options.cache ?? new TimelineRowTextCache();
    this.metrics = options.metrics;
  }

  /** Render the primary + secondary label inside the label column. */
  render(args: RowLabelRenderArgs): { truncated: boolean } {
    const { ctx, palette, layout, row, rowTopY } = args;
    const indent = clampIndent(row.depth, layout);
    const labelStartX = indent + 6;
    const labelEndX = layout.labelColumnWidthPx - 6;
    const maxWidth = Math.max(0, labelEndX - labelStartX);
    if (maxWidth <= 0) return { truncated: false };

    const primaryY = rowTopY + this.primaryBaselineOffset;
    const secondaryY = rowTopY + this.secondaryBaselineOffset;

    const primary = this.resolveLabel(ctx, this.primaryFont, row.label, maxWidth);
    ctx.save();
    ctx.font = this.primaryFont;
    ctx.fillStyle = rowLabelText(palette);
    ctx.textBaseline = "alphabetic";
    ctx.fillText(primary.text, labelStartX, primaryY);

    const secondaryText = secondaryLine(row);
    let truncated = primary.truncated;
    if (secondaryText !== null && layout.rowHeightPx >= 24) {
      const secondary = this.resolveLabel(ctx, this.secondaryFont, secondaryText, maxWidth);
      ctx.font = this.secondaryFont;
      ctx.fillStyle = rowSecondaryText(palette);
      ctx.fillText(secondary.text, labelStartX, secondaryY);
      truncated = truncated || secondary.truncated;
    }
    ctx.restore();

    this.metrics?.recordLabel({ truncated });
    return { truncated };
  }

  /** Lookup-or-compute a truncated label for the given font + width. */
  resolveLabel(
    ctx: CanvasRenderingContext2D,
    font: string,
    text: string,
    maxWidthPx: number,
  ): CachedLabel {
    if (text.length === 0) {
      return { text: "", widthPx: 0, truncated: false };
    }
    const cached = this.cache.get(font, maxWidthPx, text);
    if (cached !== null) {
      this.metrics?.recordTextCacheHit();
      return cached;
    }
    this.metrics?.recordTextCacheMiss();
    const measured = truncateText(ctx, font, text, maxWidthPx);
    this.cache.set(font, maxWidthPx, text, measured);
    return measured;
  }

  /** Test/debug helper — read the cache without exposing the field. */
  cacheStats(): { hits: number; misses: number; size: number } {
    return {
      hits: this.cache.hits(),
      misses: this.cache.misses(),
      size: this.cache.size(),
    };
  }

  clearCache(): void {
    this.cache.clear();
  }
}

function clampIndent(depth: number | undefined, layout: TimelineRowLayoutSnapshot): number {
  if (!depth || depth <= 0) return 0;
  return Math.min(layout.maxIndentPx, depth * layout.indentPerDepthPx);
}

function secondaryLine(row: TimelineRowProjectionEntry): string | null {
  if (!row.coroutineName) return null;
  if (row.coroutineName === row.label) return null;
  if (row.childCount > 0) return `${row.coroutineName}  ·  ${row.childCount} child`;
  return row.coroutineName;
}

/** Pure: binary-search truncation; ``ctx.font`` is set before measuring
 *  so the cache key remains consistent. */
export function truncateText(
  ctx: CanvasRenderingContext2D,
  font: string,
  text: string,
  maxWidthPx: number,
): CachedLabel {
  if (maxWidthPx <= 0) return { text: "", widthPx: 0, truncated: text.length > 0 };
  ctx.save();
  ctx.font = font;
  try {
    const fullWidth = ctx.measureText(text).width;
    if (fullWidth <= maxWidthPx) {
      return { text, widthPx: fullWidth, truncated: false };
    }
    const ellipsisWidth = ctx.measureText(ELLIPSIS).width;
    let lo = 0;
    let hi = text.length;
    let best = "";
    let bestWidth = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const candidate = text.slice(0, mid);
      const widthPx = ctx.measureText(candidate).width + ellipsisWidth;
      if (widthPx <= maxWidthPx) {
        best = candidate;
        bestWidth = widthPx;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (best.length === 0) {
      return { text: ELLIPSIS, widthPx: ellipsisWidth, truncated: true };
    }
    return { text: `${best}${ELLIPSIS}`, widthPx: bestWidth, truncated: true };
  } finally {
    ctx.restore();
  }
}
