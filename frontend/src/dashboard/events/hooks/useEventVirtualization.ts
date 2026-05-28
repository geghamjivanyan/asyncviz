/**
 * Foundation for event-feed virtualization.
 *
 * Today the hook returns every row; the contract is stable so swapping
 * in real windowing (IntersectionObserver / scroll position) is a
 * one-file change. Stable row heights are a prerequisite — the
 * default constant pins that.
 */

import { useMemo } from "react";
import type { EventRow } from "@/dashboard/events/models/eventRow";

export const EVENT_ROW_HEIGHT_PX = 36;

export interface EventVirtualizationWindow {
  startIndex: number;
  endIndex: number;
  rowHeight: number;
  totalRows: number;
  visibleRows: EventRow[];
}

export function useEventVirtualization(rows: readonly EventRow[]): EventVirtualizationWindow {
  return useMemo(
    () => ({
      startIndex: 0,
      endIndex: rows.length,
      rowHeight: EVENT_ROW_HEIGHT_PX,
      totalRows: rows.length,
      visibleRows: rows.slice(),
    }),
    [rows],
  );
}
