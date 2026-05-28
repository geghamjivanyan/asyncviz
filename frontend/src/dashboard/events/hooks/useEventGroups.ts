/**
 * Group event rows for the current grouping mode.
 *
 * Returns a stable :type:`EventGroup[]`. Identity changes only when
 * the inputs change.
 */

import { useMemo } from "react";
import type { EventRow } from "@/dashboard/events/models/eventRow";
import type { EventGroupingState } from "@/dashboard/events/models/filters";
import { groupEventRows, type EventGroup } from "@/dashboard/events/utils/grouping";
import { getEventFeedMetrics } from "@/dashboard/events/observability";

export function useEventGroups(
  rows: readonly EventRow[],
  grouping: EventGroupingState,
): EventGroup[] {
  return useMemo(() => {
    getEventFeedMetrics().recordGroupRebuild();
    return groupEventRows(rows, grouping.mode);
  }, [rows, grouping.mode]);
}
