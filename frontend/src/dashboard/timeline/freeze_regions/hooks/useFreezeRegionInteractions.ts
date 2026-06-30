/**
 * Pointer + selection wiring for the freeze-region layer.
 *
 * Exposes one factory: :func:`useFreezeRegionInteractions` returns a
 * stable handlers object that the timeline canvas's pointer wiring
 * can invoke without knowing anything about the freeze-region module.
 *
 * Behaviour summary:
 *
 *   * pointer move → update hovered group (only when changed)
 *   * pointer down on a freeze → set selected + invoke ``onSelect``
 *   * keyboard "reveal next freeze" → expose ``revealNext`` /
 *     ``revealPrevious`` so the panel can drive it
 */

import { useCallback, useMemo } from "react";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";
import { hitTestFreezeRegions } from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";
import { getFreezeRegionMetrics } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";
import { recordFreezeRegionTrace } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

export interface FreezeInteractionHandlers {
  onPointerMove(xCss: number): void;
  onPointerLeave(): void;
  /** Returns the freeze (if any) that was clicked. */
  onPointerDown(xCss: number): FreezeRegionView | null;
  /** Programmatically select a freeze by id (e.g. from the warnings panel). */
  selectFreeze(groupId: string | null): void;
  /** Drive the reveal animation. */
  revealFreeze(groupId: string | null): void;
}

export interface UseFreezeRegionInteractionsOptions {
  onSelect?: (region: FreezeRegionView | null) => void;
}

export function useFreezeRegionInteractions(
  options: UseFreezeRegionInteractionsOptions = {},
): FreezeInteractionHandlers {
  const setHoveredGroup = useFreezeRegionStore((s) => s.setHoveredGroup);
  const setSelectedGroup = useFreezeRegionStore((s) => s.setSelectedGroup);
  const revealGroup = useFreezeRegionStore((s) => s.revealGroup);

  const { onSelect } = options;

  const onPointerMove = useCallback(
    (xCss: number) => {
      const entries = useFreezeRegionStore.getState().visibleEntries;
      const hit = hitTestFreezeRegions(entries, xCss);
      const previous = useFreezeRegionStore.getState().hoveredGroupId;
      const next = hit?.region.groupId ?? null;
      if (previous !== next) {
        setHoveredGroup(next);
        getFreezeRegionMetrics().recordHoverChange();
        recordFreezeRegionTrace({ kind: "hover-changed", detail: next ?? "<none>" });
      }
    },
    [setHoveredGroup],
  );

  const onPointerLeave = useCallback(() => {
    if (useFreezeRegionStore.getState().hoveredGroupId !== null) {
      setHoveredGroup(null);
      getFreezeRegionMetrics().recordHoverChange();
    }
  }, [setHoveredGroup]);

  const onPointerDown = useCallback(
    (xCss: number) => {
      const entries = useFreezeRegionStore.getState().visibleEntries;
      const hit = hitTestFreezeRegions(entries, xCss);
      const region = hit?.region ?? null;
      const previous = useFreezeRegionStore.getState().selectedGroupId;
      const next = region?.groupId ?? null;
      if (previous !== next) {
        setSelectedGroup(next);
        getFreezeRegionMetrics().recordSelectionChange();
        recordFreezeRegionTrace({ kind: "selection-changed", detail: next ?? "<none>" });
        onSelect?.(region);
      }
      return region;
    },
    [setSelectedGroup, onSelect],
  );

  const selectFreeze = useCallback(
    (groupId: string | null) => {
      const previous = useFreezeRegionStore.getState().selectedGroupId;
      if (previous === groupId) return;
      setSelectedGroup(groupId);
      getFreezeRegionMetrics().recordSelectionChange();
      recordFreezeRegionTrace({
        kind: "selection-changed",
        detail: groupId ?? "<none>",
      });
    },
    [setSelectedGroup],
  );

  const revealFreeze = useCallback(
    (groupId: string | null) => {
      revealGroup(groupId);
      getFreezeRegionMetrics().recordReveal();
      recordFreezeRegionTrace({
        kind: groupId === null ? "reveal-missed" : "reveal",
        detail: groupId ?? "<none>",
      });
    },
    [revealGroup],
  );

  return useMemo(
    () => ({
      onPointerMove,
      onPointerLeave,
      onPointerDown,
      selectFreeze,
      revealFreeze,
    }),
    [onPointerMove, onPointerLeave, onPointerDown, selectFreeze, revealFreeze],
  );
}
