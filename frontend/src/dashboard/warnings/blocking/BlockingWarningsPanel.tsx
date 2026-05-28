/**
 * Stateless presentation layer for the blocking-warnings panel.
 *
 * Composes the existing sub-components (metrics header, filter bar,
 * grouping sections, cards, replay badge, capture/task drilldowns).
 * Everything renders from props — :class:`BlockingWarningsContainer`
 * is the one that wires the store, hooks, and websocket bridge.
 *
 * Keeping the panel stateless means:
 *
 *   * The whole tree is replay-deterministic — feed the same view
 *     bundle twice and the rendered DOM is identical.
 *   * Tests can mount the panel against synthesized fixtures without
 *     constructing a websocket client or hydrating the store.
 *   * Future containers (replay scrubber, distributed-runtime
 *     aggregator) can drive the same view layer.
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/cn";
import { BlockingWarningCard } from "@/dashboard/warnings/blocking/BlockingWarningCard";
import { BlockingWarningFilters } from "@/dashboard/warnings/blocking/BlockingWarningFilters";
import { BlockingWarningGrouping } from "@/dashboard/warnings/blocking/BlockingWarningGrouping";
import { BlockingWarningMetricsHeader } from "@/dashboard/warnings/blocking/BlockingWarningMetrics";
import { BlockingWarningReplayBadge } from "@/dashboard/warnings/blocking/BlockingWarningReplay";
import {
  describeCountsAnnouncement,
} from "@/dashboard/warnings/blocking/BlockingWarningAccessibility";
import {
  DEFAULT_ACTIVE_VISIBLE_CAP,
  DEFAULT_RECENT_VISIBLE_CAP,
  clampViews,
} from "@/dashboard/warnings/blocking/BlockingWarningVirtualization";
import type {
  BlockingWarningEmitterMetricsModel,
  BlockingWarningEmitterStatisticsModel,
  BlockingWarningFilterMode,
  BlockingWarningView,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type {
  BlockingWarningBuckets,
  BlockingWarningCounts,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";

/** Status surface for the replay/connection badge + error message. */
export interface BlockingWarningsPanelStatus {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
}

export interface BlockingWarningsPanelProps {
  /** Bucketed (+ filtered) views the panel renders into the sections. */
  buckets: BlockingWarningBuckets;
  /** Pre-filter total counts (used in the metrics header). */
  totalCounts: BlockingWarningCounts;
  /** Post-filter counts (used in the screen-reader announcement). */
  filteredCounts: BlockingWarningCounts;
  /** Emitter statistics block — null until first hydration. */
  statistics: BlockingWarningEmitterStatisticsModel | null;
  /** Emitter metrics block — null until first hydration. */
  metrics: BlockingWarningEmitterMetricsModel | null;
  /** Filter mode + setter. */
  filterMode: BlockingWarningFilterMode;
  onChangeFilterMode: (mode: BlockingWarningFilterMode) => void;
  /** Selection state + setter. */
  selectedGroupId: string | null;
  onSelectGroup: (groupId: string | null) => void;
  /** Optional drilldown callbacks. */
  onSelectCapture?: (captureId: number, groupId: string) => void;
  onSelectTask?: (taskId: string) => void;
  /** Hydration/connection status for the badge. */
  status: BlockingWarningsPanelStatus;
  /** Visible-cap overrides (mostly for tests). */
  activeVisibleCap?: number;
  recentVisibleCap?: number;
  className?: string;
}

function BlockingWarningsPanelImpl({
  buckets,
  totalCounts,
  filteredCounts,
  statistics,
  metrics,
  filterMode,
  onChangeFilterMode,
  selectedGroupId,
  onSelectGroup,
  onSelectCapture,
  onSelectTask,
  status,
  activeVisibleCap = DEFAULT_ACTIVE_VISIBLE_CAP,
  recentVisibleCap = DEFAULT_RECENT_VISIBLE_CAP,
  className,
}: BlockingWarningsPanelProps) {
  const activeClamped = useMemo(
    () => clampViews(buckets.active, activeVisibleCap),
    [buckets.active, activeVisibleCap],
  );
  const recentClamped = useMemo(
    () => clampViews(buckets.recent, recentVisibleCap),
    [buckets.recent, recentVisibleCap],
  );

  const filtered = filterMode !== "all";
  const announcement = useMemo(
    () =>
      describeCountsAnnouncement(
        filteredCounts.active,
        filteredCounts.recovered,
        filtered,
      ),
    [filteredCounts.active, filteredCounts.recovered, filtered],
  );

  const emptyOverall =
    buckets.active.length === 0 && buckets.recent.length === 0;

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col gap-3 overflow-hidden p-4 text-sm text-text",
        className,
      )}
      aria-label="Blocking warnings panel"
      data-testid="blocking-warnings-panel"
      data-status={status.status}
    >
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Blocking Warnings
        </h1>
        <BlockingWarningReplayBadge
          status={status.status}
          errorMessage={status.errorMessage}
        />
        <span
          className="sr-only"
          role="status"
          aria-live="polite"
          data-testid="blocking-warnings-announcement"
        >
          {announcement}
        </span>
      </header>

      <BlockingWarningMetricsHeader
        counts={totalCounts}
        statistics={statistics}
        metrics={metrics}
      />

      <BlockingWarningFilters
        mode={filterMode}
        onChange={onChangeFilterMode}
      />

      {status.status === "error" && status.errorMessage !== null && (
        <p
          className="rounded border border-danger bg-danger/10 px-3 py-2 font-mono text-xs text-danger"
          role="alert"
          data-testid="blocking-warnings-error"
        >
          Failed to load blocking warnings: {status.errorMessage}
        </p>
      )}

      <div
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto pr-1"
        data-testid="blocking-warnings-scroll"
      >
        {emptyOverall && status.status !== "loading" ? (
          <p
            className="rounded border border-dashed border-line bg-elevated px-3 py-6 text-center text-xs text-subtle"
            data-testid="blocking-warnings-empty"
          >
            {filtered
              ? "No blocking warnings match the current filter."
              : "No blocking warnings recorded yet."}
          </p>
        ) : (
          <>
            <BlockingWarningGrouping
              id="blocking-warnings-active"
              title="Active"
              count={buckets.active.length}
              emptyLabel="No active blocking warnings."
            >
              <CardList
                views={activeClamped.visible}
                hidden={activeClamped.hidden}
                selectedGroupId={selectedGroupId}
                onSelect={onSelectGroup}
                onSelectCapture={onSelectCapture}
                onSelectTask={onSelectTask}
              />
            </BlockingWarningGrouping>
            <BlockingWarningGrouping
              id="blocking-warnings-recent"
              title="Recent"
              count={buckets.recent.length}
              emptyLabel="No recent blocking warnings."
            >
              <CardList
                views={recentClamped.visible}
                hidden={recentClamped.hidden}
                selectedGroupId={selectedGroupId}
                onSelect={onSelectGroup}
                onSelectCapture={onSelectCapture}
                onSelectTask={onSelectTask}
              />
            </BlockingWarningGrouping>
          </>
        )}
      </div>
    </section>
  );
}

interface CardListProps {
  views: readonly BlockingWarningView[];
  hidden: number;
  selectedGroupId: string | null;
  onSelect: (groupId: string | null) => void;
  onSelectCapture?: (captureId: number, groupId: string) => void;
  onSelectTask?: (taskId: string) => void;
}

const CardListImpl = ({
  views,
  hidden,
  selectedGroupId,
  onSelect,
  onSelectCapture,
  onSelectTask,
}: CardListProps) => (
  <ul className="flex flex-col gap-2" data-testid="blocking-warnings-card-list">
    {views.map((view) => (
      <li key={view.groupId}>
        <BlockingWarningCard
          view={view}
          selected={selectedGroupId === view.groupId}
          onSelect={onSelect}
          onSelectCapture={onSelectCapture}
          onSelectTask={onSelectTask}
        />
      </li>
    ))}
    {hidden > 0 && (
      <li
        className="text-subtle text-xs font-mono italic"
        data-testid="blocking-warnings-truncated"
      >
        + {hidden} more hidden (truncated to keep render budget)
      </li>
    )}
  </ul>
);

const CardList = memo(CardListImpl);

export const BlockingWarningsPanel = memo(BlockingWarningsPanelImpl);
