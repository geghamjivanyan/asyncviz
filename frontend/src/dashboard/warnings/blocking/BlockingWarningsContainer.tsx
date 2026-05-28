/**
 * Store-aware wrapper for :class:`BlockingWarningsPanel`.
 *
 * Owns:
 *
 *   * Snapshot hydration on mount (REST).
 *   * Websocket live-update bridge (subscribes to ``runtime_event``).
 *   * Projection memoization via the view hooks.
 *   * Selection routing into the store.
 *   * Render-duration sampling for the panel metrics collector.
 *
 * Stays out of the rendering itself — the panel is dumb and reads
 * only props. This split lets future containers (replay scrubber,
 * distributed-runtime aggregator) reuse the same view layer with a
 * different data source.
 */

import { useCallback, useEffect, useRef } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { BlockingWarningsPanel } from "@/dashboard/warnings/blocking/BlockingWarningsPanel";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import { useBlockingWarningHydration } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningHydration";
import { useBlockingWarningWebsocketBridge } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningWebsocketBridge";
import {
  useBlockingWarningFilter,
  useBlockingWarningProjections,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningViews";
import { useBlockingWarningSelection } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningSelection";
import { getBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions";

export interface BlockingWarningsContainerProps {
  className?: string;
  /** Skip auto-hydration — handy for tests that hand-feed the store. */
  disableHydration?: boolean;
  /** Skip the websocket bridge — for tests / replay-only mode. */
  disableLiveUpdates?: boolean;
  /** Custom hook for "reveal task on the timeline / inspector". */
  onRevealTask?: (taskId: string) => void;
  /** Custom hook for "reveal stack capture in inspector". */
  onRevealCapture?: (captureId: number, groupId: string) => void;
}

export function BlockingWarningsContainer({
  className,
  disableHydration = false,
  disableLiveUpdates = false,
  onRevealTask,
  onRevealCapture,
}: BlockingWarningsContainerProps) {
  useBlockingWarningHydration({ enabled: !disableHydration });
  useBlockingWarningWebsocketBridge({ enabled: !disableLiveUpdates });

  const status = useBlockingWarningStore((s) => s.status);
  const errorMessage = useBlockingWarningStore((s) => s.errorMessage);
  const statistics = useBlockingWarningStore((s) => s.statistics);
  const metrics = useBlockingWarningStore((s) => s.metrics);

  const { buckets, counts, filteredCounts } = useBlockingWarningProjections();
  const { filterMode, setFilterMode } = useBlockingWarningFilter();
  const { selectedGroupId, selectGroup } = useBlockingWarningSelection();
  const storeSelectTask = useRuntimeStore((s) => s.selectTask);
  const setFreezeSelected = useFreezeRegionStore((s) => s.setSelectedGroup);
  const revealFreeze = useFreezeRegionStore((s) => s.revealGroup);

  // Cross-link panel ↔ canvas: when a card is selected, mirror the
  // selection into the freeze-region store + nudge the renderer to
  // reveal it. Clearing the panel selection clears the reveal flag
  // too so the canvas stops flashing the previous freeze.
  const handleSelectGroup = useCallback(
    (groupId: string | null) => {
      selectGroup(groupId);
      setFreezeSelected(groupId);
      revealFreeze(groupId);
    },
    [selectGroup, setFreezeSelected, revealFreeze],
  );

  const handleSelectTask = useCallback(
    (taskId: string) => {
      storeSelectTask(taskId);
      onRevealTask?.(taskId);
      recordBlockingWarningTrace({ kind: "reveal-task", detail: taskId });
    },
    [storeSelectTask, onRevealTask],
  );

  const handleSelectCapture = useCallback(
    (captureId: number, groupId: string) => {
      onRevealCapture?.(captureId, groupId);
      recordBlockingWarningTrace({
        kind: "reveal-capture",
        detail: `${groupId}:${captureId}`,
      });
    },
    [onRevealCapture],
  );

  const renderStartRef = useRef<number>(0);
  renderStartRef.current =
    typeof performance !== "undefined" ? performance.now() : Date.now();
  useEffect(() => {
    const end =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const duration = end - renderStartRef.current;
    getBlockingWarningPanelMetrics().recordRenderDuration(duration);
    recordBlockingWarningTrace({
      kind: "panel-render",
      detail: `active=${buckets.active.length} recent=${buckets.recent.length}`,
    });
  });

  return (
    <BlockingWarningsPanel
      className={className}
      buckets={buckets}
      totalCounts={counts}
      filteredCounts={filteredCounts}
      statistics={statistics}
      metrics={metrics}
      filterMode={filterMode}
      onChangeFilterMode={setFilterMode}
      selectedGroupId={selectedGroupId}
      onSelectGroup={handleSelectGroup}
      onSelectCapture={handleSelectCapture}
      onSelectTask={handleSelectTask}
      status={{ status, errorMessage }}
    />
  );
}

