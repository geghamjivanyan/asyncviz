/**
 * Lifecycle binding that mounts a :class:`FreezeRegionRenderer` on the
 * canvas timeline.
 *
 * Steps performed:
 *
 *   1. Construct exactly one renderer per renderer instance.
 *   2. Wire it to a :type:`FreezeRegionSource` backed by the projection
 *      hook + freeze-region store.
 *   3. Push the visible-entries snapshot back into the store so
 *      pointer handlers can hit-test in O(visible).
 *   4. Invalidate the renderer when the projection or selection
 *      changes — otherwise active-only changes never repaint.
 *   5. Tear everything down cleanly on unmount.
 */

import { useEffect, useMemo, useRef } from "react";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { FreezeRegionRenderer } from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";
import type { FreezeRegionSource } from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";
import { useFreezeRegionProjection } from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionProjection";
import { recordFreezeRegionTrace } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";

export interface UseFreezeRegionLayerOptions {
  /** When ``false``, skip the mount entirely. */
  enabled?: boolean;
  /** Override the default 128-region visible cap. */
  visibleCap?: number;
}

export function useFreezeRegionLayer(
  renderer: TimelineRenderer | null,
  options: UseFreezeRegionLayerOptions = {},
): void {
  const { enabled = true, visibleCap } = options;
  const { regions, getEscalations } = useFreezeRegionProjection();
  const selectedGroupId = useFreezeRegionStore((s) => s.selectedGroupId);
  const hoveredGroupId = useFreezeRegionStore((s) => s.hoveredGroupId);
  const revealedGroupId = useFreezeRegionStore((s) => s.revealedGroupId);
  const reducedMotion = useFreezeRegionStore((s) => s.reducedMotion);
  const setVisibleEntries = useFreezeRegionStore((s) => s.setVisibleEntries);

  // Stable refs so the source closures read the freshest values
  // without forcing the renderer to rebind every render.
  const sourceRef = useRef({
    regions,
    getEscalations,
    selectedGroupId,
    hoveredGroupId,
    revealedGroupId,
    reducedMotion,
    visibleCap,
  });
  sourceRef.current = {
    regions,
    getEscalations,
    selectedGroupId,
    hoveredGroupId,
    revealedGroupId,
    reducedMotion,
    visibleCap,
  };

  const source = useMemo<FreezeRegionSource>(
    () => ({
      getRegions: () => sourceRef.current.regions,
      getEscalations: (groupId) => sourceRef.current.getEscalations(groupId),
      getSelectedGroupId: () => sourceRef.current.selectedGroupId,
      getHoveredGroupId: () => sourceRef.current.hoveredGroupId,
      getRevealedGroupId: () => sourceRef.current.revealedGroupId,
      isReducedMotion: () => sourceRef.current.reducedMotion,
      getVisibleCap: () => sourceRef.current.visibleCap ?? 0,
    }),
    [],
  );

  useEffect(() => {
    if (!enabled || renderer === null) return undefined;
    const layer = new FreezeRegionRenderer({
      onVisibleEntries: (entries, hidden) => {
        setVisibleEntries(entries, hidden);
      },
    });
    layer.setSource(source);
    renderer.addLayer(layer);
    recordFreezeRegionTrace({ kind: "layer-attached", detail: layer.id });
    return () => {
      renderer.removeLayer(layer.id);
      layer.setSource(null);
      setVisibleEntries([], 0);
      recordFreezeRegionTrace({ kind: "layer-detached", detail: layer.id });
    };
  }, [enabled, renderer, source, setVisibleEntries]);

  // Force a repaint whenever projection or decoration state changes —
  // the renderer's other invalidation triggers (viewport, camera,
  // data) don't fire for these.
  useEffect(() => {
    renderer?.invalidate("overlay");
  }, [renderer, regions, selectedGroupId, hoveredGroupId, revealedGroupId]);
}
