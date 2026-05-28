/**
 * Project the store's wire-shape state into render-ready view models.
 *
 * Memoization is dimensional:
 *
 *   * ``groupsById`` is referentially stable until a reducer rebuilds
 *     it. The projection cache keys off ``(group_id, last_seen_ns,
 *     state)`` so live updates only re-project the affected group.
 *   * Filtered + bucketed lists are derived from the projection list;
 *     ``useMemo`` recomputes only when the filter or the projection
 *     reference changes.
 */

import { useMemo } from "react";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import {
  applyFilter,
  bucketViews,
  compareViews,
  projectGroup,
  summarize,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import type {
  BlockingWarningBuckets,
  BlockingWarningCounts,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import type {
  BlockingWarningFilter,
  BlockingWarningFilterMode,
  BlockingWarningView,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

export interface BlockingWarningProjections {
  views: readonly BlockingWarningView[];
  filtered: readonly BlockingWarningView[];
  buckets: BlockingWarningBuckets;
  counts: BlockingWarningCounts;
  filteredCounts: BlockingWarningCounts;
}

/**
 * Build the projection bundle. Reads only the slices required so a
 * selection change doesn't invalidate the projection.
 */
export function useBlockingWarningProjections(): BlockingWarningProjections {
  const groupsById = useBlockingWarningStore((s) => s.groupsById);
  const filter = useBlockingWarningStore((s) => s.filter);

  const views = useMemo(() => {
    const out: BlockingWarningView[] = [];
    for (const id in groupsById) {
      out.push(projectGroup(groupsById[id]));
    }
    out.sort(compareViews);
    return out;
  }, [groupsById]);

  const filtered = useMemo(() => applyFilter(views, filter), [views, filter]);
  const buckets = useMemo(() => bucketViews(filtered), [filtered]);
  const counts = useMemo(() => summarize(views), [views]);
  const filteredCounts = useMemo(() => summarize(filtered), [filtered]);

  return { views, filtered, buckets, counts, filteredCounts };
}

/** Lookup hook — returns the view for the currently selected group, or null. */
export function useSelectedBlockingWarning(): BlockingWarningView | null {
  const selectedGroupId = useBlockingWarningStore((s) => s.selectedGroupId);
  const groupsById = useBlockingWarningStore((s) => s.groupsById);
  return useMemo(() => {
    if (selectedGroupId === null) return null;
    const group = groupsById[selectedGroupId];
    return group === undefined ? null : projectGroup(group);
  }, [selectedGroupId, groupsById]);
}

/** Filter accessor — convenience for the filter bar. */
export function useBlockingWarningFilter(): {
  filter: BlockingWarningFilter;
  setFilterMode: (mode: BlockingWarningFilterMode) => void;
  filterMode: BlockingWarningFilterMode;
} {
  const filter = useBlockingWarningStore((s) => s.filter);
  const filterMode = useBlockingWarningStore((s) => s.filterMode);
  const setFilterMode = useBlockingWarningStore((s) => s.setFilterMode);
  return { filter, setFilterMode, filterMode };
}
