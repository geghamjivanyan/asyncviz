/**
 * Replay dashboard.
 *
 * Page-level composition over the replay timeline store +
 * ``WebSocketReplayEngineBridge``. The heavy lifting lives in
 * dedicated components:
 *
 *   * ``ReplayLaneTimelinePanel`` — lane-based timeline with bright
 *     cursor, drag-select, marker tooltips
 *   * ``ReplayLaneTimelineMinimap`` — overview + draggable viewport
 *
 * This file owns the page shell, the playback / nav controls, the
 * selection state, the filtered bookmark list, and the inspector.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type JSX,
} from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { EmptyState } from "@/ui/feedback/EmptyState";
import type { Intent } from "@/ui/theme/tokens";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import { WebSocketReplayEngineBridge } from "@/dashboard/replay/hooks/WebSocketReplayEngineBridge";
import { useReplayEngineBridge } from "@/dashboard/replay/hooks/useReplayEngineBridge";
import { useReplayKeyboard } from "@/dashboard/replay/hooks/useReplayKeyboard";
import {
  useReplayBookmarks,
  useReplayMarkers,
  useReplayPlayback,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  jumpByFraction,
  seekFromFraction,
  seekToBookmark,
  seekToMarker,
  stepCursor,
} from "@/dashboard/replay/ReplayTimelineSeek";
import { REPLAY_SPEED_PRESETS } from "@/dashboard/replay/ReplayPlaybackPresets";
import {
  ReplayLaneTimelinePanel,
  type ReplayLaneTimelinePanelSelection,
} from "@/dashboard/replay/ReplayLaneTimelinePanel";
import { ReplayLaneTimelineMinimap } from "@/dashboard/replay/ReplayLaneTimelineMinimap";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayMarkerKind,
  ReplayMarkerSeverity,
  ReplayPlaybackSnapshot,
  ReplayPlaybackState,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

// ──────────────────────────────────────────────────────────────────────────
// Page
// ──────────────────────────────────────────────────────────────────────────

export function ReplayPage(): JSX.Element {
  const client = useWebSocketClient();
  const bridge = useMemo(
    () => new WebSocketReplayEngineBridge({ client }),
    [client],
  );
  useEffect(() => () => bridge.dispose(), [bridge]);
  useReplayEngineBridge({ bridge });

  const dispatch = useCallback(
    (intent: ReplayControlIntent) => {
      void bridge.dispatch(intent);
    },
    [bridge],
  );

  const playback = useReplayPlayback();
  const window = useReplayWindow();
  const markers = useReplayMarkers();
  const bookmarks = useReplayBookmarks();
  const removeBookmark = useReplayTimelineStore((s) => s.removeBookmark);

  const hasRecording =
    window.maxSequence > window.minSequence || markers.length > 0;

  // Visible window for the timeline + minimap. The lane timeline owns
  // the zoom toolbar / wheel / dblclick interactions and updates this
  // via ``handleVisibleWindowChange``; the minimap mirrors the range
  // as a draggable overlay. Default = full recording.
  const [visibleStart, setVisibleStart] = useState<number | null>(null);
  const [visibleEnd, setVisibleEnd] = useState<number | null>(null);
  const visibleRange = useMemo(() => {
    const minSeq = window.minSequence;
    const maxSeq = window.maxSequence;
    if (visibleStart === null || visibleEnd === null) {
      return { start: minSeq, end: maxSeq };
    }
    return {
      start: Math.max(minSeq, visibleStart),
      end: Math.min(maxSeq, visibleEnd),
    };
  }, [visibleStart, visibleEnd, window.minSequence, window.maxSequence]);

  const visibleWindow = useMemo<ReplaySessionWindow>(() => {
    const fullSpan = Math.max(0, window.maxSequence - window.minSequence);
    if (fullSpan <= 0) return window;
    const nsSpan = Math.max(0, window.maxMonotonicNs - window.minMonotonicNs);
    const startFrac = (visibleRange.start - window.minSequence) / fullSpan;
    const endFrac = (visibleRange.end - window.minSequence) / fullSpan;
    return {
      minSequence: visibleRange.start,
      maxSequence: visibleRange.end,
      minMonotonicNs:
        window.minMonotonicNs + Math.round(nsSpan * Math.max(0, Math.min(1, startFrac))),
      maxMonotonicNs:
        window.minMonotonicNs + Math.round(nsSpan * Math.max(0, Math.min(1, endFrac))),
    };
  }, [window, visibleRange.start, visibleRange.end]);

  const handleVisibleWindowChange = useCallback(
    (start: number, end: number) => {
      setVisibleStart(start);
      setVisibleEnd(end);
    },
    [],
  );

  // Drag-selection on the lane timeline.
  const [selection, setSelection] =
    useState<ReplayLaneTimelinePanelSelection | null>(null);
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(null);
  const [selectedBookmarkId, setSelectedBookmarkId] = useState<string | null>(
    null,
  );

  const handleSelectMarker = useCallback((marker: ReplayTimelineMarker) => {
    setSelectedMarkerId(marker.id);
    setSelectedBookmarkId(null);
  }, []);
  const handleSelectBookmark = useCallback((bookmark: ReplayBookmark) => {
    setSelectedBookmarkId(bookmark.id);
    setSelectedMarkerId(null);
  }, []);

  const selectedMarker = useMemo(
    () =>
      selectedMarkerId === null
        ? null
        : markers.find((m) => m.id === selectedMarkerId) ?? null,
    [markers, selectedMarkerId],
  );
  const selectedBookmark = useMemo(
    () =>
      selectedBookmarkId === null
        ? null
        : bookmarks.find((b) => b.id === selectedBookmarkId) ?? null,
    [bookmarks, selectedBookmarkId],
  );

  const summary = useMemo(
    () => buildSummary(playback, window, markers),
    [playback, window, markers],
  );

  // Reset zoom whenever the recording itself changes (e.g., a new
  // bundle is loaded) — leftover visibleStart/End from the previous
  // session would otherwise show as a stale narrow window.
  useEffect(() => {
    setVisibleStart(null);
    setVisibleEnd(null);
  }, [window.minSequence, window.maxSequence]);

  // Keyboard shortcuts. Disabled while focus is inside an editable
  // element (search inputs, bookmark notes) — handled inside the
  // hook so we don't have to thread refs everywhere.
  useReplayKeyboard({
    enabled: hasRecording,
    window,
    playback,
    markers,
    bookmarks,
    dispatch,
  });

  if (!hasRecording) {
    return (
      <div className="flex h-full min-h-0 w-full flex-col gap-4 px-4 py-4">
        <header className="flex items-center gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">
            Replay
          </h1>
        </header>
        <div className="flex flex-1 items-center justify-center">
          <EmptyState
            title="No replay recording loaded."
            description="Launch your runtime with asyncviz replay <recording> to attach the dashboard to a captured session. Live runtimes stream their own state here whenever the asyncviz replay launcher is active."
          />
        </div>
      </div>
    );
  }

  return (
    <div
      data-replay-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto px-4 py-4"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">
            Replay
          </h1>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            sequence #{window.minSequence} – #{window.maxSequence}
          </span>
        </div>
        <PlaybackStateBadge state={playback.state} paused={playback.paused} />
      </header>

      <Section title="Replay summary">
        <div
          className="grid gap-2"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(11rem, 1fr))" }}
        >
          <SummaryCell label="Status" value={statusLabel(playback)} />
          <SummaryCell
            label="Recording loaded"
            value="Yes"
            intent="success"
          />
          <SummaryCell
            label="Current position"
            value={`${formatCount(playback.lastSequence)} / ${formatCount(window.maxSequence)}`}
            sub={`${(summary.positionFraction * 100).toFixed(1)}%`}
          />
          <SummaryCell
            label="Total duration"
            value={formatNs(summary.totalDurationNs)}
          />
          <SummaryCell label="Playback speed" value={`${playback.speed}×`} />
          <SummaryCell
            label="Buffered events"
            value={formatCount(summary.bufferedEvents)}
          />
          <SummaryCell label="Replay mode" value={playback.state.toUpperCase()} />
        </div>
      </Section>

      <Section title="Playback">
        <Card padding="sm" className="flex flex-col gap-3">
          <PlaybackControls
            playback={playback}
            window={window}
            markers={markers}
            bookmarks={bookmarks}
            dispatch={dispatch}
          />
        </Card>
      </Section>

      <Section title="Timeline">
        <Card padding="sm" className="flex flex-col gap-3">
          <ReplayLaneTimelinePanel
            playback={playback}
            fullWindow={window}
            visibleWindow={visibleWindow}
            onVisibleWindowChange={handleVisibleWindowChange}
            markers={markers}
            bookmarks={bookmarks}
            dispatch={dispatch}
            selection={selection}
            onSelectionChange={setSelection}
            onSelectMarker={handleSelectMarker}
            onSelectBookmark={handleSelectBookmark}
            selectedMarkerId={selectedMarkerId}
            selectedBookmarkId={selectedBookmarkId}
          />
          <ReplayLaneTimelineMinimap
            playback={playback}
            window={window}
            markers={markers}
            bookmarks={bookmarks}
            visibleStartSequence={visibleRange.start}
            visibleEndSequence={visibleRange.end}
            onViewportChange={handleVisibleWindowChange}
            dispatch={dispatch}
          />
          {selection !== null && (
            <SelectionStatsBar
              selection={selection}
              markers={markers}
              window={window}
              onClear={() => setSelection(null)}
            />
          )}
        </Card>
      </Section>

      <Section title="Recording">
        <div className="flex min-h-0 flex-1 gap-2">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
            <RecordingInfoCard
              window={window}
              playback={playback}
              markers={markers}
            />
            <BookmarksCard
              bookmarks={bookmarks}
              dispatch={dispatch}
              onRemove={removeBookmark}
              onSelect={handleSelectBookmark}
              currentSequence={playback.lastSequence}
              selectedBookmarkId={selectedBookmarkId}
            />
          </div>
          <aside
            aria-label="Replay inspector"
            className="hidden h-full w-[340px] shrink-0 overflow-y-auto md:flex"
          >
            <ReplayInspector
              playback={playback}
              window={window}
              markers={markers}
              selectedMarker={selectedMarker}
              selectedBookmark={selectedBookmark}
              dispatch={dispatch}
              onClearSelection={() => {
                setSelectedMarkerId(null);
                setSelectedBookmarkId(null);
              }}
            />
          </aside>
        </div>
      </Section>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Summary
// ──────────────────────────────────────────────────────────────────────────

interface ReplaySummary {
  positionFraction: number;
  totalDurationNs: number;
  bufferedEvents: number;
  warningCount: number;
  blockingCount: number;
  snapshotCount: number;
}

function buildSummary(
  playback: ReplayPlaybackSnapshot,
  window: ReplaySessionWindow,
  markers: readonly ReplayTimelineMarker[],
): ReplaySummary {
  const span = window.maxSequence - window.minSequence;
  const positionFraction =
    span > 0
      ? Math.max(
          0,
          Math.min(
            1,
            (playback.lastSequence - window.minSequence) / span,
          ),
        )
      : 0;
  let warningCount = 0;
  let blockingCount = 0;
  let snapshotCount = 0;
  for (const m of markers) {
    if (m.kind === "warning") warningCount += 1;
    else if (m.kind === "blocking" || m.kind === "saturation") blockingCount += 1;
    else if (m.kind === "checkpoint" || m.kind === "annotation") snapshotCount += 1;
  }
  return {
    positionFraction,
    totalDurationNs: Math.max(0, window.maxMonotonicNs - window.minMonotonicNs),
    bufferedEvents: span > 0 ? span + 1 : 0,
    warningCount,
    blockingCount,
    snapshotCount,
  };
}

function statusLabel(playback: ReplayPlaybackSnapshot): string {
  if (playback.paused && playback.state !== "paused") return "Paused";
  return playback.state.charAt(0).toUpperCase() + playback.state.slice(1);
}

// ──────────────────────────────────────────────────────────────────────────
// Playback controls
// ──────────────────────────────────────────────────────────────────────────

function PlaybackControls({
  playback,
  window,
  markers,
  bookmarks,
  dispatch,
}: {
  playback: ReplayPlaybackSnapshot;
  window: ReplaySessionWindow;
  markers: readonly ReplayTimelineMarker[];
  bookmarks: readonly ReplayBookmark[];
  dispatch: (intent: ReplayControlIntent) => void;
}) {
  const isPlaying = playback.state === "playing" && !playback.paused;
  const atStart = playback.lastSequence <= window.minSequence;
  const atEnd = playback.lastSequence >= window.maxSequence;

  const prevMarker = useMemo(
    () => findAdjacentMarker(markers, playback.lastSequence, "prev"),
    [markers, playback.lastSequence],
  );
  const nextMarker = useMemo(
    () => findAdjacentMarker(markers, playback.lastSequence, "next"),
    [markers, playback.lastSequence],
  );
  const prevWarning = useMemo(
    () => findAdjacentMarker(markers, playback.lastSequence, "prev", isWarningMarker),
    [markers, playback.lastSequence],
  );
  const nextWarning = useMemo(
    () => findAdjacentMarker(markers, playback.lastSequence, "next", isWarningMarker),
    [markers, playback.lastSequence],
  );
  const prevBookmark = useMemo(
    () => findAdjacentBookmark(bookmarks, playback.lastSequence, "prev"),
    [bookmarks, playback.lastSequence],
  );
  const nextBookmark = useMemo(
    () => findAdjacentBookmark(bookmarks, playback.lastSequence, "next"),
    [bookmarks, playback.lastSequence],
  );

  return (
    <div className="flex flex-col gap-2">
      <div
        role="group"
        aria-label="Playback controls"
        className="flex flex-wrap items-center gap-2"
      >
        <ControlButton
          onClick={() => dispatch(seekFromFraction(0, window))}
          disabled={atStart}
          label="⏮"
          title="Jump to start"
        />
        <ControlButton
          onClick={() =>
            dispatch(stepCursor(playback.lastSequence, -1, window))
          }
          disabled={atStart}
          label="◀"
          title="Step backward"
        />
        <ControlButton
          onClick={() => dispatch({ type: isPlaying ? "pause" : "play" })}
          label={isPlaying ? "Pause" : "Play"}
          title={isPlaying ? "Pause" : "Play"}
          intent="accent"
        />
        <ControlButton
          onClick={() => dispatch({ type: "step-forward" })}
          disabled={atEnd}
          label="▶"
          title="Step forward"
        />
        <ControlButton
          onClick={() => dispatch({ type: "stop" })}
          disabled={playback.state === "idle"}
          label="■"
          title="Stop"
          intent="danger"
        />
        <ControlButton
          onClick={() => dispatch(seekFromFraction(1, window))}
          disabled={atEnd}
          label="⏭"
          title="Jump to end"
        />
        <ControlButton
          onClick={() =>
            dispatch(jumpByFraction(playback.lastSequence, -0.1, window))
          }
          disabled={atStart}
          label="-10%"
          title="Skip back 10%"
        />
        <ControlButton
          onClick={() =>
            dispatch(jumpByFraction(playback.lastSequence, 0.1, window))
          }
          disabled={atEnd}
          label="+10%"
          title="Skip ahead 10%"
        />
        <label className="ml-auto flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Speed
          </span>
          <select
            value={playback.speed}
            onChange={(e) =>
              dispatch({
                type: "set-speed",
                speed: Number.parseFloat(e.target.value),
              })
            }
            aria-label="Playback speed"
            className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-xs text-text outline-none hover:border-accent focus:border-accent"
          >
            {REPLAY_SPEED_PRESETS.map((preset) => (
              <option key={preset} value={preset}>
                {preset}×
              </option>
            ))}
          </select>
        </label>
      </div>

      <div
        role="group"
        aria-label="Navigation"
        className="flex flex-wrap items-center gap-2 border-t border-line/40 pt-2"
      >
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Navigate
        </span>
        <NavButton
          target={prevMarker}
          dispatch={dispatch}
          labelPrefix="◀ Marker"
          missingTitle="No earlier marker"
        />
        <NavButton
          target={nextMarker}
          dispatch={dispatch}
          labelPrefix="Marker ▶"
          missingTitle="No later marker"
        />
        <NavButton
          target={prevWarning}
          dispatch={dispatch}
          labelPrefix="◀ Warn"
          missingTitle="No earlier warning"
          intent="warning"
        />
        <NavButton
          target={nextWarning}
          dispatch={dispatch}
          labelPrefix="Warn ▶"
          missingTitle="No later warning"
          intent="warning"
        />
        <NavBookmarkButton
          bookmark={prevBookmark}
          dispatch={dispatch}
          labelPrefix="◀ Bookmark"
          missingTitle="No earlier bookmark"
        />
        <NavBookmarkButton
          bookmark={nextBookmark}
          dispatch={dispatch}
          labelPrefix="Bookmark ▶"
          missingTitle="No later bookmark"
        />
      </div>
    </div>
  );
}

function NavButton({
  target,
  dispatch,
  labelPrefix,
  missingTitle,
  intent = "default",
}: {
  target: ReplayTimelineMarker | null;
  dispatch: (intent: ReplayControlIntent) => void;
  labelPrefix: string;
  missingTitle: string;
  intent?: Intent;
}) {
  return (
    <ControlButton
      onClick={() => target !== null && dispatch(seekToMarker(target))}
      disabled={target === null}
      label={labelPrefix}
      title={target !== null ? `${labelPrefix}: ${target.label}` : missingTitle}
      intent={intent}
    />
  );
}

function NavBookmarkButton({
  bookmark,
  dispatch,
  labelPrefix,
  missingTitle,
}: {
  bookmark: ReplayBookmark | null;
  dispatch: (intent: ReplayControlIntent) => void;
  labelPrefix: string;
  missingTitle: string;
}) {
  return (
    <ControlButton
      onClick={() => bookmark !== null && dispatch(seekToBookmark(bookmark))}
      disabled={bookmark === null}
      label={labelPrefix}
      title={
        bookmark !== null ? `${labelPrefix}: ${bookmark.label}` : missingTitle
      }
    />
  );
}

function ControlButton({
  onClick,
  disabled,
  label,
  title,
  intent = "default",
}: {
  onClick: () => void;
  disabled?: boolean;
  label: string;
  title: string;
  intent?: Intent;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className={cn(
        "rounded border px-2.5 py-1 font-mono text-xs uppercase tracking-widest",
        "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line disabled:hover:text-subtle",
        intent === "accent"
          ? "border-accent bg-accent/10 text-accent hover:bg-accent/15"
          : intent === "danger"
            ? "border-line text-subtle hover:border-danger hover:text-danger"
            : intent === "warning"
              ? "border-line text-subtle hover:border-warning hover:text-warning"
              : "border-line bg-canvas text-text hover:border-accent hover:text-accent",
      )}
    >
      {label}
    </button>
  );
}

function findAdjacentMarker(
  markers: readonly ReplayTimelineMarker[],
  pivot: number,
  direction: "prev" | "next",
  predicate: (m: ReplayTimelineMarker) => boolean = () => true,
): ReplayTimelineMarker | null {
  let best: ReplayTimelineMarker | null = null;
  for (const m of markers) {
    if (!predicate(m)) continue;
    if (direction === "prev") {
      if (m.sequence < pivot && (best === null || m.sequence > best.sequence)) {
        best = m;
      }
    } else {
      if (m.sequence > pivot && (best === null || m.sequence < best.sequence)) {
        best = m;
      }
    }
  }
  return best;
}

function findAdjacentBookmark(
  bookmarks: readonly ReplayBookmark[],
  pivot: number,
  direction: "prev" | "next",
): ReplayBookmark | null {
  let best: ReplayBookmark | null = null;
  for (const b of bookmarks) {
    if (direction === "prev") {
      if (b.sequence < pivot && (best === null || b.sequence > best.sequence)) {
        best = b;
      }
    } else {
      if (b.sequence > pivot && (best === null || b.sequence < best.sequence)) {
        best = b;
      }
    }
  }
  return best;
}

function isWarningMarker(m: ReplayTimelineMarker): boolean {
  return m.kind === "warning" || m.severity === "warning" || m.severity === "critical";
}

// ──────────────────────────────────────────────────────────────────────────
// Selection stats bar
// ──────────────────────────────────────────────────────────────────────────

function SelectionStatsBar({
  selection,
  markers,
  window,
  onClear,
}: {
  selection: ReplayLaneTimelinePanelSelection;
  markers: readonly ReplayTimelineMarker[];
  window: ReplaySessionWindow;
  onClear: () => void;
}) {
  const stats = useMemo(() => {
    const start = Math.min(selection.startSequence, selection.endSequence);
    const end = Math.max(selection.startSequence, selection.endSequence);
    let warnings = 0;
    let blocking = 0;
    let snapshots = 0;
    let total = 0;
    let firstNs = Number.POSITIVE_INFINITY;
    let lastNs = Number.NEGATIVE_INFINITY;
    let prevNs: number | null = null;
    let intervalSum = 0;
    let intervalCount = 0;
    for (const m of markers) {
      if (m.sequence < start || m.sequence > end) continue;
      total += 1;
      if (m.kind === "warning") warnings += 1;
      else if (m.kind === "blocking" || m.kind === "saturation") blocking += 1;
      else if (m.kind === "checkpoint" || m.kind === "annotation") snapshots += 1;
      if (m.monotonicNs < firstNs) firstNs = m.monotonicNs;
      if (m.monotonicNs > lastNs) lastNs = m.monotonicNs;
      if (prevNs !== null) {
        intervalSum += Math.max(0, m.monotonicNs - prevNs);
        intervalCount += 1;
      }
      prevNs = m.monotonicNs;
    }
    const span = end - start;
    const fullSpan = Math.max(1, window.maxSequence - window.minSequence);
    const timeSpan = (window.maxMonotonicNs - window.minMonotonicNs) * (span / fullSpan);
    const eventCount = span + 1;
    const avgLatencyNs = intervalCount > 0 ? intervalSum / intervalCount : 0;
    return {
      start,
      end,
      total,
      warnings,
      blocking,
      snapshots,
      eventCount,
      durationNs: Math.max(0, timeSpan),
      avgLatencyNs,
    };
  }, [selection, markers, window]);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded border border-accent/40 bg-accent/5 px-3 py-2 font-mono text-xs">
      <span className="text-[10px] uppercase tracking-widest text-accent">
        Selection
      </span>
      <Stat label="Range" value={`#${stats.start} – #${stats.end}`} />
      <Stat label="Events" value={formatCount(stats.eventCount)} />
      <Stat
        label="Warnings"
        value={String(stats.warnings)}
        intent={stats.warnings > 0 ? "warning" : undefined}
      />
      <Stat
        label="Blocking"
        value={String(stats.blocking)}
        intent={stats.blocking > 0 ? "danger" : undefined}
      />
      <Stat label="Snapshots" value={String(stats.snapshots)} />
      <Stat label="Markers" value={String(stats.total)} />
      <Stat label="Duration" value={formatNs(stats.durationNs)} />
      <Stat
        label="Avg interval"
        value={stats.avgLatencyNs > 0 ? formatNs(stats.avgLatencyNs) : "—"}
      />
      <button
        type="button"
        onClick={onClear}
        className="ml-auto rounded border border-line bg-canvas px-2 py-0.5 text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
      >
        Clear
      </button>
    </div>
  );
}

function Stat({
  label,
  value,
  intent,
}: {
  label: string;
  value: string;
  intent?: Intent;
}) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : "text-text";
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-[10px] uppercase tracking-widest text-muted">
        {label}
      </span>
      <span className={cn("tabular-nums", valueColor)}>{value}</span>
    </span>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Recording info + bookmarks
// ──────────────────────────────────────────────────────────────────────────

function RecordingInfoCard({
  window,
  playback,
  markers,
}: {
  window: ReplaySessionWindow;
  playback: ReplayPlaybackSnapshot;
  markers: readonly ReplayTimelineMarker[];
}) {
  let warningCount = 0;
  let blockingCount = 0;
  let snapshotCount = 0;
  for (const m of markers) {
    if (m.kind === "warning") warningCount += 1;
    else if (m.kind === "blocking" || m.kind === "saturation") blockingCount += 1;
    else if (m.kind === "checkpoint" || m.kind === "annotation") snapshotCount += 1;
  }
  return (
    <Card padding="md" className="flex flex-col gap-3">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
        Recording information
      </span>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-xs">
        <KV label="Sequence span" value={`#${window.minSequence} – #${window.maxSequence}`} />
        <KV
          label="Duration"
          value={formatNs(Math.max(0, window.maxMonotonicNs - window.minMonotonicNs))}
        />
        <KV
          label="Event count"
          value={String(Math.max(0, window.maxSequence - window.minSequence + 1))}
        />
        <KV label="Frames dispatched" value={String(playback.framesDispatched)} />
        <KV
          label="Warnings"
          value={String(warningCount)}
          intent={warningCount > 0 ? "warning" : undefined}
        />
        <KV
          label="Blocking events"
          value={String(blockingCount)}
          intent={blockingCount > 0 ? "danger" : undefined}
        />
        <KV
          label="Snapshots"
          value={String(snapshotCount)}
          intent={snapshotCount > 0 ? "accent" : undefined}
        />
        <KV label="Total markers" value={String(markers.length)} />
      </dl>
    </Card>
  );
}

type BookmarkCategory = "all" | "warning" | "blocking" | "health" | "runtime" | "user";

const CATEGORY_OPTIONS: { key: BookmarkCategory; label: string }[] = [
  { key: "all", label: "All" },
  { key: "warning", label: "Warnings" },
  { key: "blocking", label: "Blocking" },
  { key: "health", label: "Health" },
  { key: "runtime", label: "Runtime" },
  { key: "user", label: "User" },
];

function classifyBookmark(b: ReplayBookmark): BookmarkCategory[] {
  const tags: BookmarkCategory[] = [];
  const id = b.id.toLowerCase();
  const label = b.label.toLowerCase();
  const isAuto = id.startsWith("bm-");
  if (id.includes("warning") || label.includes("warning")) tags.push("warning");
  if (id.includes("failure") || label.includes("failure") || label.includes("failed")) {
    tags.push("warning");
  }
  if (id.includes("blocking") || label.includes("block")) tags.push("blocking");
  if (id.includes("saturation") || label.includes("saturation")) tags.push("health");
  if (
    id.includes("runtime-started") ||
    id.includes("runtime-stopped") ||
    label.includes("runtime")
  ) {
    tags.push("runtime");
  }
  if (!isAuto) tags.push("user");
  if (isAuto && tags.length === 0) tags.push("runtime");
  return tags;
}

function BookmarksCard({
  bookmarks,
  dispatch,
  onRemove,
  onSelect,
  currentSequence,
  selectedBookmarkId,
}: {
  bookmarks: readonly ReplayBookmark[];
  dispatch: (intent: ReplayControlIntent) => void;
  onRemove: (id: string) => void;
  onSelect: (bookmark: ReplayBookmark) => void;
  currentSequence: number;
  selectedBookmarkId: string | null;
}) {
  const [category, setCategory] = useState<BookmarkCategory>("all");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const trimmedQuery = query.trim().toLowerCase();
    return bookmarks.filter((b) => {
      if (category !== "all") {
        const tags = classifyBookmark(b);
        if (!tags.includes(category)) return false;
      }
      if (trimmedQuery.length === 0) return true;
      const haystack = `${b.label} ${b.note ?? ""}`.toLowerCase();
      return haystack.includes(trimmedQuery);
    });
  }, [bookmarks, category, query]);

  return (
    <Card padding="md" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Bookmarks ({filtered.length} / {bookmarks.length})
        </span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search…"
          aria-label="Search bookmarks"
          className="w-40 rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[11px] text-text outline-none hover:border-accent focus:border-accent"
        />
      </div>
      <div role="group" aria-label="Bookmark filters" className="flex flex-wrap gap-1">
        {CATEGORY_OPTIONS.map((opt) => {
          const active = category === opt.key;
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => setCategory(opt.key)}
              className={cn(
                "rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest",
                active
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-line bg-canvas text-subtle hover:border-accent hover:text-accent",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {filtered.length === 0 ? (
        <p className="font-mono text-xs text-subtle">No bookmarks match.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {filtered.map((b) => (
            <BookmarkRow
              key={b.id}
              bookmark={b}
              active={b.sequence === currentSequence || b.id === selectedBookmarkId}
              onJump={() => {
                onSelect(b);
                dispatch(seekToBookmark(b));
              }}
              onSelect={() => onSelect(b)}
              onRemove={() => onRemove(b.id)}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}

function BookmarkRow({
  bookmark,
  active,
  onJump,
  onSelect,
  onRemove,
}: {
  bookmark: ReplayBookmark;
  active: boolean;
  onJump: () => void;
  onSelect: () => void;
  onRemove: () => void;
}) {
  return (
    <li
      className={cn(
        "flex items-center justify-between gap-3 rounded border px-2 py-1.5 font-mono text-xs",
        active ? "border-accent bg-accent/10" : "border-line",
      )}
      data-active={active ? "true" : undefined}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 flex-col gap-0.5 text-left"
      >
        <span className="truncate text-text" title={bookmark.label}>
          {bookmark.label}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
          seq #{bookmark.sequence} · {formatNs(bookmark.monotonicNs)}
        </span>
        {bookmark.note !== undefined && bookmark.note.length > 0 && (
          <span className="truncate text-[11px] text-muted" title={bookmark.note}>
            {bookmark.note}
          </span>
        )}
      </button>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onJump}
          title="Jump to bookmark"
          aria-label={`Jump to bookmark ${bookmark.label}`}
          className="rounded border border-line bg-canvas px-2 py-0.5 text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Jump
        </button>
        <button
          type="button"
          onClick={onRemove}
          title="Delete bookmark"
          aria-label={`Delete bookmark ${bookmark.label}`}
          className="rounded border border-line bg-canvas px-2 py-0.5 text-[10px] uppercase tracking-widest text-subtle hover:border-danger hover:text-danger"
        >
          Delete
        </button>
      </div>
    </li>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Inspector
// ──────────────────────────────────────────────────────────────────────────

const KIND_RELATED_OBJECT: Partial<Record<ReplayMarkerKind, string>> = {
  warning: "warning",
  blocking: "event loop",
  saturation: "queue / semaphore / executor",
  checkpoint: "snapshot",
  annotation: "annotation",
  bookmark: "bookmark",
};

function ReplayInspector({
  playback,
  window,
  markers,
  selectedMarker,
  selectedBookmark,
  dispatch,
  onClearSelection,
}: {
  playback: ReplayPlaybackSnapshot;
  window: ReplaySessionWindow;
  markers: readonly ReplayTimelineMarker[];
  selectedMarker: ReplayTimelineMarker | null;
  selectedBookmark: ReplayBookmark | null;
  dispatch: (intent: ReplayControlIntent) => void;
  onClearSelection: () => void;
}) {
  const span = window.maxSequence - window.minSequence;
  const fraction =
    span > 0
      ? Math.max(
          0,
          Math.min(1, (playback.lastSequence - window.minSequence) / span),
        )
      : 0;

  const nearbyMarkers = useMemo(() => {
    const out: { marker: ReplayTimelineMarker; delta: number }[] = [];
    for (const m of markers) {
      const delta = m.sequence - playback.lastSequence;
      out.push({ marker: m, delta });
    }
    out.sort((a, b) => Math.abs(a.delta) - Math.abs(b.delta));
    return out.slice(0, 5);
  }, [markers, playback.lastSequence]);

  return (
    <Card padding="md" className="flex h-full w-full flex-col gap-4">
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Replay inspector
          </span>
          <span className="truncate font-mono text-sm text-text">
            #{playback.lastSequence}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {Math.round(fraction * 100)}% through recording
          </span>
        </div>
        <PlaybackStateBadge state={playback.state} paused={playback.paused} />
      </header>

      {selectedMarker !== null && (
        <SelectedMarkerSection
          marker={selectedMarker}
          window={window}
          onJump={() => dispatch(seekToMarker(selectedMarker))}
          onClear={onClearSelection}
        />
      )}
      {selectedBookmark !== null && selectedMarker === null && (
        <SelectedBookmarkSection
          bookmark={selectedBookmark}
          window={window}
          onJump={() => dispatch(seekToBookmark(selectedBookmark))}
          onClear={onClearSelection}
        />
      )}

      <InspectorSection title="Position">
        <InspectorKV label="Sequence" value={`#${playback.lastSequence}`} />
        <InspectorKV
          label="Timestamp"
          value={formatNs(playback.lastMonotonicNs)}
        />
        <InspectorKV label="Progress" value={`${Math.round(fraction * 100)}%`} />
        <InspectorKV label="Speed" value={`${playback.speed}×`} />
      </InspectorSection>

      <InspectorSection title="Engine">
        <InspectorKV label="State" value={statusLabel(playback)} />
        <InspectorKV label="Paused" value={playback.paused ? "Yes" : "No"} />
        <InspectorKV
          label="Frames dispatched"
          value={String(playback.framesDispatched)}
        />
        {playback.errorDetail !== undefined && playback.errorDetail.length > 0 && (
          <InspectorKV
            label="Error"
            value={playback.errorDetail}
            intent="danger"
          />
        )}
      </InspectorSection>

      <InspectorSection title="Recording">
        <InspectorKV
          label="Range"
          value={`#${window.minSequence} – #${window.maxSequence}`}
        />
        <InspectorKV
          label="Total"
          value={`${Math.max(0, window.maxSequence - window.minSequence + 1)} events`}
        />
        <InspectorKV
          label="Duration"
          value={formatNs(Math.max(0, window.maxMonotonicNs - window.minMonotonicNs))}
        />
      </InspectorSection>

      {nearbyMarkers.length > 0 && (
        <InspectorSection title="Nearby markers">
          <ul className="flex flex-col gap-1 font-mono text-[11px]">
            {nearbyMarkers.map(({ marker, delta }) => (
              <li
                key={marker.id}
                className="flex items-baseline justify-between gap-2"
                title={marker.description ?? marker.label}
              >
                <span className="flex min-w-0 items-baseline gap-2">
                  <Badge intent={markerSeverityIntent(marker.severity)}>
                    {marker.kind}
                  </Badge>
                  <span className="truncate text-muted">{marker.label}</span>
                </span>
                <span className="shrink-0 tabular-nums text-subtle">
                  {delta === 0 ? "here" : delta > 0 ? `+${delta}` : String(delta)}
                </span>
              </li>
            ))}
          </ul>
        </InspectorSection>
      )}
    </Card>
  );
}

function SelectedMarkerSection({
  marker,
  window,
  onJump,
  onClear,
}: {
  marker: ReplayTimelineMarker;
  window: ReplaySessionWindow;
  onJump: () => void;
  onClear: () => void;
}) {
  const tRel = Math.max(0, marker.monotonicNs - window.minMonotonicNs);
  return (
    <section className="flex flex-col gap-2 rounded border border-accent/40 bg-accent/5 p-2">
      <header className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
          Selected marker
        </span>
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Clear
        </button>
      </header>
      <div className="flex items-baseline gap-2">
        <Badge intent={markerSeverityIntent(marker.severity)}>{marker.kind}</Badge>
        <span className="truncate font-mono text-xs text-text" title={marker.label}>
          {marker.label}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px]">
        <KV label="Type" value={marker.kind} />
        <KV label="Severity" value={marker.severity} intent={markerSeverityIntent(marker.severity)} />
        <KV label="Sequence" value={`#${marker.sequence}`} />
        <KV label="Timestamp" value={formatNs(tRel)} />
        <KV
          label="Related to"
          value={KIND_RELATED_OBJECT[marker.kind] ?? marker.kind}
        />
        <KV label="ID" value={marker.id} />
      </dl>
      {marker.description !== undefined && marker.description.length > 0 && (
        <p className="whitespace-pre-wrap break-words font-mono text-[11px] text-muted">
          {marker.description}
        </p>
      )}
      <RelatedLinks marker={marker} />
      <button
        type="button"
        onClick={onJump}
        className="self-start rounded border border-accent bg-accent/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-accent hover:bg-accent/15"
      >
        Jump to marker
      </button>
    </section>
  );
}

function SelectedBookmarkSection({
  bookmark,
  window,
  onJump,
  onClear,
}: {
  bookmark: ReplayBookmark;
  window: ReplaySessionWindow;
  onJump: () => void;
  onClear: () => void;
}) {
  const tRel = Math.max(0, bookmark.monotonicNs - window.minMonotonicNs);
  const categories = classifyBookmark(bookmark);
  return (
    <section className="flex flex-col gap-2 rounded border border-accent/40 bg-accent/5 p-2">
      <header className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
          Selected bookmark
        </span>
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Clear
        </button>
      </header>
      <div className="flex items-baseline gap-2">
        <Badge intent="accent">bookmark</Badge>
        <span className="truncate font-mono text-xs text-text" title={bookmark.label}>
          {bookmark.label}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px]">
        <KV label="Sequence" value={`#${bookmark.sequence}`} />
        <KV label="Timestamp" value={formatNs(tRel)} />
        <KV label="ID" value={bookmark.id} />
        <KV label="Categories" value={categories.join(", ")} />
      </dl>
      {bookmark.note !== undefined && bookmark.note.length > 0 && (
        <p className="whitespace-pre-wrap break-words font-mono text-[11px] text-muted">
          {bookmark.note}
        </p>
      )}
      <button
        type="button"
        onClick={onJump}
        className="self-start rounded border border-accent bg-accent/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-accent hover:bg-accent/15"
      >
        Jump to bookmark
      </button>
    </section>
  );
}

function RelatedLinks({ marker }: { marker: ReplayTimelineMarker }) {
  const links = useMemo(() => relatedLinksFor(marker), [marker]);
  if (links.length === 0) return null;
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
        Related
      </span>
      {links.map((link) => (
        <a
          key={link.href}
          href={link.href}
          className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-accent hover:border-accent"
        >
          {link.label}
        </a>
      ))}
    </div>
  );
}

function relatedLinksFor(
  marker: ReplayTimelineMarker,
): readonly { href: string; label: string }[] {
  const out: { href: string; label: string }[] = [];
  switch (marker.kind) {
    case "warning":
      out.push({ href: "#/warnings", label: "Warnings" });
      out.push({ href: "#/tasks", label: "Tasks" });
      break;
    case "blocking":
      out.push({ href: "#/blocking", label: "Blocking" });
      out.push({ href: "#/eventloop", label: "Event loop" });
      break;
    case "saturation":
      out.push({ href: "#/queues", label: "Queues" });
      out.push({ href: "#/semaphores", label: "Semaphores" });
      out.push({ href: "#/executors", label: "Executors" });
      break;
    case "checkpoint":
    case "annotation":
      out.push({ href: "#/snapshots", label: "Snapshots" });
      break;
    case "bookmark":
      break;
  }
  return out;
}

function markerSeverityIntent(severity: ReplayMarkerSeverity): Intent {
  switch (severity) {
    case "critical":
      return "danger";
    case "warning":
      return "warning";
    case "info":
    default:
      return "accent";
  }
}

// ──────────────────────────────────────────────────────────────────────────
// Shared building blocks
// ──────────────────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}

function SummaryCell({
  label,
  value,
  sub,
  intent = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  intent?: Intent;
}) {
  return (
    <Card padding="sm" intent={intent} className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="truncate font-mono text-base tabular-nums text-text">{value}</span>
      {sub !== undefined && (
        <span className="truncate font-mono text-[10px] uppercase tracking-widest text-subtle">
          {sub}
        </span>
      )}
    </Card>
  );
}

function KV({
  label,
  value,
  intent,
}: {
  label: string;
  value: string;
  intent?: Intent;
}) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "success"
          ? "text-success"
          : intent === "accent"
            ? "text-accent"
            : "text-text";
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[10px] uppercase tracking-widest text-muted">{label}</dt>
      <dd className={cn("truncate tabular-nums", valueColor)} title={value}>
        {value}
      </dd>
    </div>
  );
}

function InspectorSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-1.5 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
        {title}
      </span>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  );
}

function InspectorKV({
  label,
  value,
  intent,
}: {
  label: string;
  value: string;
  intent?: Intent;
}) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "success"
          ? "text-success"
          : intent === "accent"
            ? "text-accent"
            : "text-text";
  return (
    <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className={cn("tabular-nums", valueColor)}>{value}</span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Playback state badge
// ──────────────────────────────────────────────────────────────────────────

const STATE_INTENT: Record<ReplayPlaybackState, Intent> = {
  idle: "default",
  playing: "accent",
  paused: "warning",
  seeking: "accent",
  buffering: "warning",
  stopped: "default",
  failed: "danger",
};

function PlaybackStateBadge({
  state,
  paused,
}: {
  state: ReplayPlaybackState;
  paused: boolean;
}) {
  const intent = STATE_INTENT[state];
  const label = paused && state !== "paused" ? "PAUSED" : state.toUpperCase();
  return <Badge intent={intent}>{label}</Badge>;
}

// ──────────────────────────────────────────────────────────────────────────
// Formatting
// ──────────────────────────────────────────────────────────────────────────

function formatNs(ns: number): string {
  if (!Number.isFinite(ns) || ns <= 0) return "0s";
  const seconds = ns / 1e9;
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return `${minutes}m ${remainder.toFixed(0).padStart(2, "0")}s`;
  }
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes.toString().padStart(2, "0")}m`;
  }
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes.toString().padStart(2, "0")}m`;
}

function formatCount(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString();
}
