/**
 * Draw-call batcher.
 *
 * Per-segment ``ctx.fillRect`` calls compose poorly: each call mutates
 * state. The batcher groups draw calls by fill style so a hot
 * timeline (thousands of segments, four or five distinct fills)
 * issues exactly one ``ctx.fillStyle = …`` set + one tight loop per
 * style.
 *
 * The batcher itself is *deferred*: callers ``enqueueRect`` and call
 * ``flush(ctx)`` once at the end of the layer. State management
 * stays in the batcher, not in every layer.
 */

export type DrawOpKind = "rect" | "stroke-rect" | "line";

export interface RectDrawOp {
  readonly kind: "rect";
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface StrokeRectDrawOp {
  readonly kind: "stroke-rect";
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
  readonly lineWidth: number;
}

export interface LineDrawOp {
  readonly kind: "line";
  readonly x0: number;
  readonly y0: number;
  readonly x1: number;
  readonly y1: number;
  readonly lineWidth: number;
}

export type DrawOp = RectDrawOp | StrokeRectDrawOp | LineDrawOp;

export interface BatcherStats {
  readonly opsEnqueued: number;
  readonly opsFlushed: number;
  readonly batchesFlushed: number;
  readonly styleSwitches: number;
  readonly droppedOnOverflow: number;
}

interface StyleBucket {
  style: string;
  ops: DrawOp[];
}

export class TimelineDrawBatcher {
  private readonly buckets = new Map<string, StyleBucket>();
  private opsEnqueued = 0;
  private opsFlushed = 0;
  private batchesFlushed = 0;
  private styleSwitches = 0;
  private droppedOnOverflow = 0;
  private bufferedOps = 0;

  constructor(private readonly capacity: number) {
    if (capacity <= 0) {
      throw new RangeError(`draw-batch capacity must be > 0 (got ${capacity})`);
    }
  }

  enqueueRect(style: string, op: RectDrawOp): void {
    if (op.width <= 0 || op.height <= 0) return;
    this.enqueue(style, op);
  }

  enqueueStrokeRect(style: string, op: StrokeRectDrawOp): void {
    if (op.width <= 0 || op.height <= 0) return;
    this.enqueue(style, op);
  }

  enqueueLine(style: string, op: LineDrawOp): void {
    this.enqueue(style, op);
  }

  /** Pump every queued op to the supplied 2D context grouped by style.
   *  The batcher is reset after the flush. */
  flush(ctx: CanvasRenderingContext2D): void {
    if (this.bufferedOps === 0) return;
    let firstStyle = true;
    for (const [style, bucket] of this.buckets) {
      if (bucket.ops.length === 0) continue;
      ctx.fillStyle = style;
      ctx.strokeStyle = style;
      if (!firstStyle) this.styleSwitches += 1;
      firstStyle = false;
      for (const op of bucket.ops) {
        switch (op.kind) {
          case "rect":
            ctx.fillRect(op.x, op.y, op.width, op.height);
            break;
          case "stroke-rect":
            ctx.lineWidth = op.lineWidth;
            ctx.strokeRect(op.x, op.y, op.width, op.height);
            break;
          case "line":
            ctx.lineWidth = op.lineWidth;
            ctx.beginPath();
            ctx.moveTo(op.x0, op.y0);
            ctx.lineTo(op.x1, op.y1);
            ctx.stroke();
            break;
        }
        this.opsFlushed += 1;
      }
      bucket.ops.length = 0;
    }
    this.batchesFlushed += 1;
    this.bufferedOps = 0;
  }

  reset(): void {
    for (const bucket of this.buckets.values()) bucket.ops.length = 0;
    this.bufferedOps = 0;
  }

  stats(): BatcherStats {
    return {
      opsEnqueued: this.opsEnqueued,
      opsFlushed: this.opsFlushed,
      batchesFlushed: this.batchesFlushed,
      styleSwitches: this.styleSwitches,
      droppedOnOverflow: this.droppedOnOverflow,
    };
  }

  resetStats(): void {
    this.opsEnqueued = 0;
    this.opsFlushed = 0;
    this.batchesFlushed = 0;
    this.styleSwitches = 0;
    this.droppedOnOverflow = 0;
  }

  /** Number of ops currently buffered (across all styles). */
  bufferedOpCount(): number {
    return this.bufferedOps;
  }

  private enqueue(style: string, op: DrawOp): void {
    this.opsEnqueued += 1;
    if (this.bufferedOps >= this.capacity) {
      this.droppedOnOverflow += 1;
      return;
    }
    let bucket = this.buckets.get(style);
    if (bucket === undefined) {
      bucket = { style, ops: [] };
      this.buckets.set(style, bucket);
    }
    bucket.ops.push(op);
    this.bufferedOps += 1;
  }
}
