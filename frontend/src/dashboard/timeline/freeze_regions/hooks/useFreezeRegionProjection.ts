/**
 * Memoized projection of blocking-warning groups into freeze regions.
 *
 * Two slice subscriptions:
 *
 *   1. ``groupsById`` — re-projects when a group changes shape.
 *   2. ``escalation history`` — exposed via a lookup so the renderer
 *      can fetch on demand without forcing a full re-projection on
 *      every transition.
 *
 * The hook returns the sorted region list plus a lookup helper for
 * escalation history. The renderer pulls escalations lazily (only for
 * visible regions) so the work is bounded by visible-count, not total
 * count.
 */

import { useCallback, useMemo } from "react";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import type {
  BlockingEscalationEntry,
  BlockingWarningGroupModel,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { projectFreezeRegions } from "@/dashboard/timeline/freeze_regions/selectors/projectFreezeRegions";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import { getFreezeRegionMetrics } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";

export interface FreezeRegionProjection {
  regions: readonly FreezeRegionView[];
  getEscalations: (groupId: string) => readonly BlockingEscalationEntry[];
}

export function useFreezeRegionProjection(): FreezeRegionProjection {
  const groupsById = useBlockingWarningStore((s) => s.groupsById);

  const regions = useMemo(() => {
    const projected = projectFreezeRegions(groupsById);
    getFreezeRegionMetrics().recordProjection(projected.length);
    return projected;
  }, [groupsById]);

  const getEscalations = useCallback(
    (groupId: string): readonly BlockingEscalationEntry[] => {
      const group: BlockingWarningGroupModel | undefined = groupsById[groupId];
      return group?.escalation_history ?? [];
    },
    [groupsById],
  );

  return { regions, getEscalations };
}
