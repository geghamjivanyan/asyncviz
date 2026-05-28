/**
 * Small fixture builders for the virtualization tests.
 */

import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

export interface FakeRow {
  rowIndex: number;
  taskId: string;
}

export interface FakeSegment {
  segmentId: string;
  rowIndex: number;
  taskId: string;
  startSeconds: number;
  endSeconds: number;
  isActive: boolean;
}

export function makeFakeRows(count: number): FakeRow[] {
  const rows: FakeRow[] = [];
  for (let i = 0; i < count; i += 1) {
    rows.push({ rowIndex: i, taskId: `t${i}` });
  }
  return rows;
}

export function makeFakeSegments(args: {
  rowCount: number;
  segmentsPerRow: number;
  startSeconds?: number;
  segmentSeconds?: number;
}): FakeSegment[] {
  const segments: FakeSegment[] = [];
  const start = args.startSeconds ?? 0;
  const each = args.segmentSeconds ?? 1;
  for (let row = 0; row < args.rowCount; row += 1) {
    for (let i = 0; i < args.segmentsPerRow; i += 1) {
      const s = start + i * each;
      segments.push({
        segmentId: `r${row}-s${i}`,
        rowIndex: row,
        taskId: `t${row}`,
        startSeconds: s,
        endSeconds: s + each * 0.8,
        isActive: false,
      });
    }
  }
  return segments;
}

export function buildCoords(args: {
  rowStart?: number;
  rowHeight?: number;
  cssWidth?: number;
  cssHeight?: number;
  timeStart?: number;
  timeEnd?: number;
  devicePixelRatio?: number;
}): TimelineCoordinateSystem {
  return new TimelineCoordinateSystem(
    {
      timeStart: args.timeStart ?? 0,
      timeEnd: args.timeEnd ?? 10,
      rowStart: args.rowStart ?? 0,
      rowHeight: args.rowHeight ?? 20,
    },
    {
      cssWidth: args.cssWidth ?? 600,
      cssHeight: args.cssHeight ?? 200,
      devicePixelRatio: args.devicePixelRatio ?? 1,
    },
  );
}
