/**
 * Run the filter + sort pipeline against the projected event rows.
 *
 * Combines :func:`useProjectedEventRows` with the local feed state.
 * Pipeline timings feed :class:`EventFeedMetrics` so the diagnostics
 * page can detect regressions in derivation cost.
 */

import { useMemo } from "react";
import type { EventRow } from "@/dashboard/events/models/eventRow";
import type { EventFilterState, EventSortState } from "@/dashboard/events/models/filters";
import { useProjectedEventRows } from "@/dashboard/events/selectors/storeSelectors";
import { applyEventFilterAndSort } from "@/dashboard/events/utils/sortFilter";
import { getEventFeedMetrics } from "@/dashboard/events/observability";

export function useEventRows(filters: EventFilterState, sort: EventSortState): EventRow[] {
  const projected = useProjectedEventRows();
  return useMemo(() => {
    const metrics = getEventFeedMetrics();
    metrics.recordFilterEvaluation();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const result = applyEventFilterAndSort(projected, filters, sort);
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    metrics.recordPipeline(end - start);
    return result;
  }, [projected, filters, sort]);
}
