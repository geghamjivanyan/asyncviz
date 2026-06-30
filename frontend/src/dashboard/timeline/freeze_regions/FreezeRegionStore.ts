/**
 * Zustand store for freeze-region UI state.
 *
 * Owns:
 *
 *   * the currently hovered + selected freeze group id (overlay
 *     decoration uses these),
 *   * the most recent geometric snapshot (sourced from
 *     :class:`FreezeRegionRenderer.lastFrameGeometry` on each frame),
 *   * the reduced-motion preference (drives the pulse animation).
 *
 * The renderer subscribes implicitly via the
 * :func:`useFreezeRegionLayer` hook; pointer handlers in
 * :class:`TimelineCanvas` poke ``setHoveredGroup`` /
 * ``setSelectedGroup`` to keep state in sync.
 */

import { create } from "zustand";
import type { FreezeHitTestEntry } from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";

export interface FreezeRegionStoreState {
  hoveredGroupId: string | null;
  selectedGroupId: string | null;
  /** Render-frame snapshot of currently visible regions + geometry. */
  visibleEntries: readonly FreezeHitTestEntry[];
  /** Number of regions clipped by the visible-cap virtualizer. */
  hiddenCount: number;
  /** Last reveal target — used by the layer to flash the focused freeze. */
  revealedGroupId: string | null;
  reducedMotion: boolean;

  setHoveredGroup(groupId: string | null): void;
  setSelectedGroup(groupId: string | null): void;
  setVisibleEntries(entries: readonly FreezeHitTestEntry[], hidden: number): void;
  revealGroup(groupId: string | null): void;
  setReducedMotion(value: boolean): void;
  reset(): void;
}

const INITIAL_STATE: Omit<
  FreezeRegionStoreState,
  | "setHoveredGroup"
  | "setSelectedGroup"
  | "setVisibleEntries"
  | "revealGroup"
  | "setReducedMotion"
  | "reset"
> = {
  hoveredGroupId: null,
  selectedGroupId: null,
  visibleEntries: [],
  hiddenCount: 0,
  revealedGroupId: null,
  reducedMotion: false,
};

export const useFreezeRegionStore = create<FreezeRegionStoreState>((set) => ({
  ...INITIAL_STATE,
  setHoveredGroup: (groupId) =>
    set((prev) => (prev.hoveredGroupId === groupId ? {} : { hoveredGroupId: groupId })),
  setSelectedGroup: (groupId) =>
    set((prev) => (prev.selectedGroupId === groupId ? {} : { selectedGroupId: groupId })),
  setVisibleEntries: (entries, hidden) => set({ visibleEntries: entries, hiddenCount: hidden }),
  revealGroup: (groupId) => set({ revealedGroupId: groupId }),
  setReducedMotion: (value) =>
    set((prev) => (prev.reducedMotion === value ? {} : { reducedMotion: value })),
  reset: () => set({ ...INITIAL_STATE }),
}));
