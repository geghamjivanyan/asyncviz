/**
 * Lane-based replay timeline.
 *
 * Markers are split into dedicated horizontal lanes — Bookmarks,
 * Warnings, Blocking, Snapshots, Health — so dense recordings stay
 * legible. Each lane buckets its markers down to one column per pixel
 * so render cost is O(width) regardless of how many events the
 * recording contains.
 *
 * Atop the lanes:
 *   * a bright, glowing playback cursor with a sequence + timestamp
 *     pill anchored to the playhead
 *   * an optional drag-selection rectangle showing event count,
 *     warnings, blocking, average inter-event latency, and duration
 *   * a hover tooltip on every marker with a one-click jump action
 *
 * Zoom is driven by an external visible-window range; the panel
 * exposes a small zoom toolbar that emits ``onVisibleWindowChange``
 * for ReplayPage to update the shared range (which the minimap
 * displays + can pan).
 */

import {
  memo,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type JSX,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { cn } from "@/lib/cn";
import { Badge } from "@/ui/primitives/Badge";
import type { Intent } from "@/ui/theme/tokens";
import { useReplayScrub } from "@/dashboard/replay/hooks/useReplayScrub";
import {
  useReplayScrubPreview,
  useReplayViewport,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  seekToBookmark,
  seekToMarker,
} from "@/dashboard/replay/ReplayTimelineSeek";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayMarkerSeverity,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

// ── lane geometry ─────────────────────────────────────────────────────────

interface LaneSpec {
  readonly key: LaneKey;
  readonly label: string;
}

type LaneKey =
  | "bookmark"
  | "warning"
  | "blocking"
  | "snapshot"
  | "health";

const LANES: readonly LaneSpec[] = [
  { key: "bookmark", label: "Bookmarks" },
  { key: "warning", label: "Warnings" },
  { key: "blocking", label: "Blocking" },
  { key: "snapshot", label: "Snapshots" },
  { key: "health", label: "Health" },
];

const LANE_HEIGHT_PX = 28;
const LANE_GAP_PX = 5;
const SCRUBBER_HEIGHT_PX = 20;
const LABEL_COL_PX = 84;
const TOTAL_LANES_HEIGHT_PX =
  LANE_HEIGHT_PX * LANES.length + LANE_GAP_PX * (LANES.length - 1);
const TOTAL_TIMELINE_HEIGHT_PX =
  TOTAL_LANES_HEIGHT_PX + LANE_GAP_PX * 2 + SCRUBBER_HEIGHT_PX;

// ── lane classification ──────────────────────────────────────────────────

function laneForMarker(marker: ReplayTimelineMarker): LaneKey | null {
  switch (marker.kind) {
    case "warning":
      return "warning";
    case "blocking":
      return "blocking";
    case "checkpoint":
    case "annotation":
      return "snapshot";
    case "saturation":
      return "health";
    case "bookmark":
      return "bookmark";
    default:
      return null;
  }
}

// ── zoom presets ─────────────────────────────────────────────────────────

interface ZoomPreset {
  readonly key: string;
  readonly label: string;
  /** Pixels per event at this zoom; ``null`` means "fit". */
  readonly pxPerEvent: number | null;
}

const ZOOM_PRESETS: readonly ZoomPreset[] = [
  { key: "fit", label: "Fit", pxPerEvent: null },
  { key: "25", label: "25%", pxPerEvent: 0.25 },
  { key: "50", label: "50%", pxPerEvent: 0.5 },
  { key: "100", label: "100%", pxPerEvent: 1 },
  { key: "200", label: "200%", pxPerEvent: 2 },
  { key: "500", label: "500%", pxPerEvent: 5 },
];

const MIN_VISIBLE_EVENTS = 4;
const WHEEL_ZOOM_STEP = 1.2;

// ── public interface ─────────────────────────────────────────────────────

export interface ReplayLaneTimelinePanelSelection {
  readonly startSequence: number;
  readonly endSequence: number;
}

export interface ReplayLaneTimelinePanelProps {
  readonly playback: ReplayPlaybackSnapshot;
  readonly fullWindow: ReplaySessionWindow;
  readonly visibleWindow: ReplaySessionWindow;
  readonly onVisibleWindowChange: (start: number, end: number) => void;
  readonly markers: readonly ReplayTimelineMarker[];
  readonly bookmarks: readonly ReplayBookmark[];
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly selection: ReplayLaneTimelinePanelSelection | null;
  readonly onSelectionChange: (
    selection: ReplayLaneTimelinePanelSelection | null,
  ) => void;
  readonly onSelectMarker: (marker: ReplayTimelineMarker) => void;
  readonly onSelectBookmark: (bookmark: ReplayBookmark) => void;
  readonly selectedMarkerId: string | null;
  readonly selectedBookmarkId: string | null;
}

// ── component ────────────────────────────────────────────────────────────

export function ReplayLaneTimelinePanel(
  props: ReplayLaneTimelinePanelProps,
): JSX.Element {
  const {
    playback,
    fullWindow,
    visibleWindow,
    onVisibleWindowChange,
    markers,
    bookmarks,
    dispatch,
    selection,
    onSelectionChange,
    onSelectMarker,
    onSelectBookmark,
    selectedMarkerId,
    selectedBookmarkId,
  } = props;

  const trackRef = useRef<HTMLDivElement | null>(null);
  const [trackWidth, setTrackWidth] = useState(0);
  const [hover, setHover] = useState<HoverTarget | null>(null);
  const [dragging, setDragging] = useState<DragState | null>(null);

  // Latest width retained on a ref so wheel/zoom handlers don't
  // re-create when the width state churns.
  const widthRef = useRef(0);
  widthRef.current = trackWidth;

  // Sync the timeline's pixel width — the bucketing memo + the cursor
  // geometry both consume it. ResizeObserver keeps it in step with
  // window resizes / sidebar toggles.
  useLayoutEffect(() => {
    const node = trackRef.current;
    if (node === null) return undefined;
    const measure = () => {
      setTrackWidth(Math.max(0, node.getBoundingClientRect().width));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const fullSpan = Math.max(0, fullWindow.maxSequence - fullWindow.minSequence);
  const visibleSpan = Math.max(
    0,
    visibleWindow.maxSequence - visibleWindow.minSequence,
  );

  // Per-lane bucketed columns over the *visible* range. Memoizes on
  // (markers, bookmarks, visibleWindow, width) so the playback ticker
  // (~2Hz) never invalidates them. With 100k events this stays fast
  // because we collapse to one column per pixel and pre-filter to the
  // visible range so deep zooms don't iterate everything.
  const laneColumns = useMemo(
    () => bucketLanes(markers, bookmarks, visibleWindow, trackWidth),
    [markers, bookmarks, visibleWindow, trackWidth],
  );

  const sequenceFromClientX = useCallback(
    (clientX: number): number => {
      const node = trackRef.current;
      if (node === null || visibleSpan <= 0) return visibleWindow.minSequence;
      const bounds = node.getBoundingClientRect();
      const fraction = Math.max(
        0,
        Math.min(1, (clientX - bounds.left) / Math.max(1, bounds.width)),
      );
      return Math.round(visibleWindow.minSequence + fraction * visibleSpan);
    },
    [visibleSpan, visibleWindow.minSequence],
  );

  // ── click-to-seek / drag-selection ────────────────────────────────────
  const handlePointerDownOnLanes = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      const clientX = event.clientX;
      const startSequence = sequenceFromClientX(clientX);
      setDragging({
        pointerId: event.pointerId,
        startClientX: clientX,
        startSequence,
        currentSequence: startSequence,
        moved: false,
      });
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [sequenceFromClientX],
  );

  const handlePointerMoveOnLanes = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (dragging === null || event.pointerId !== dragging.pointerId) return;
      const dx = event.clientX - dragging.startClientX;
      const moved = dragging.moved || Math.abs(dx) >= 4;
      if (!moved) return;
      const currentSequence = sequenceFromClientX(event.clientX);
      setDragging({ ...dragging, moved: true, currentSequence });
    },
    [dragging, sequenceFromClientX],
  );

  const handlePointerUpOnLanes = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (dragging === null || event.pointerId !== dragging.pointerId) {
        return;
      }
      const releaseSeq = sequenceFromClientX(event.clientX);
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // pointer capture may have already been released
      }
      if (dragging.moved) {
        const start = Math.min(dragging.startSequence, releaseSeq);
        const end = Math.max(dragging.startSequence, releaseSeq);
        onSelectionChange({ startSequence: start, endSequence: end });
      } else {
        // A non-drag click. If it lands on or near a marker, prefer
        // jumping to that marker (so bucket-only mode still respects
        // "Clicking any marker jumps directly"). Otherwise seek to
        // the click position.
        const nearestMarker = findNearestVisibleMarker(
          laneColumns.markersInVisibleRange,
          releaseSeq,
          visibleSpan,
        );
        if (nearestMarker !== null) {
          onSelectMarker(nearestMarker);
          dispatch(seekToMarker(nearestMarker));
        } else {
          onSelectionChange(null);
          dispatch({ type: "seek-sequence", sequence: releaseSeq });
        }
      }
      setDragging(null);
    },
    [
      dragging,
      dispatch,
      laneColumns.markersInVisibleRange,
      onSelectMarker,
      onSelectionChange,
      sequenceFromClientX,
      visibleSpan,
    ],
  );

  const handleLaneClickMarker = useCallback(
    (marker: ReplayTimelineMarker) => {
      onSelectMarker(marker);
      dispatch(seekToMarker(marker));
    },
    [dispatch, onSelectMarker],
  );

  const handleClickBookmark = useCallback(
    (bookmark: ReplayBookmark) => {
      onSelectBookmark(bookmark);
      dispatch(seekToBookmark(bookmark));
    },
    [dispatch, onSelectBookmark],
  );

  // ── zoom: presets / wheel / dblclick ─────────────────────────────────
  const fit = useCallback(() => {
    onVisibleWindowChange(fullWindow.minSequence, fullWindow.maxSequence);
  }, [fullWindow.minSequence, fullWindow.maxSequence, onVisibleWindowChange]);

  const zoomAroundSequence = useCallback(
    (newVisibleSpan: number, pivotSequence: number) => {
      const span = Math.max(
        MIN_VISIBLE_EVENTS,
        Math.min(fullSpan, Math.round(newVisibleSpan)),
      );
      if (span >= fullSpan) {
        fit();
        return;
      }
      let start = Math.round(pivotSequence - span / 2);
      let end = start + span;
      if (start < fullWindow.minSequence) {
        start = fullWindow.minSequence;
        end = start + span;
      }
      if (end > fullWindow.maxSequence) {
        end = fullWindow.maxSequence;
        start = end - span;
      }
      onVisibleWindowChange(start, end);
    },
    [
      fit,
      fullSpan,
      fullWindow.maxSequence,
      fullWindow.minSequence,
      onVisibleWindowChange,
    ],
  );

  const applyPreset = useCallback(
    (preset: ZoomPreset) => {
      if (preset.pxPerEvent === null || trackWidth <= 0) {
        fit();
        return;
      }
      const newSpan = trackWidth / preset.pxPerEvent;
      zoomAroundSequence(newSpan, playback.lastSequence);
    },
    [fit, playback.lastSequence, trackWidth, zoomAroundSequence],
  );

  const handleWheel = useCallback(
    (event: ReactWheelEvent<HTMLDivElement>) => {
      if (event.deltaY === 0) return;
      event.preventDefault();
      // delta < 0 → scroll up → zoom in (smaller visible span)
      const factor = event.deltaY < 0 ? 1 / WHEEL_ZOOM_STEP : WHEEL_ZOOM_STEP;
      const newSpan = visibleSpan * factor;
      // Zoom around the sequence under the mouse pointer so the
      // hovered position stays put on screen.
      const pivot = sequenceFromClientX(event.clientX);
      zoomAroundSequence(newSpan, pivot);
    },
    [sequenceFromClientX, visibleSpan, zoomAroundSequence],
  );

  const handleDoubleClick = useCallback(
    (event: ReactPointerEvent<HTMLDivElement> | React.MouseEvent) => {
      event.preventDefault();
      fit();
    },
    [fit],
  );

  // ── cursor + selection projections (using the *visible* range) ───────
  const cursorFraction = useMemo(() => {
    if (visibleSpan <= 0) return null;
    if (
      playback.lastSequence < visibleWindow.minSequence ||
      playback.lastSequence > visibleWindow.maxSequence
    ) {
      return null; // off-screen at current zoom
    }
    return (playback.lastSequence - visibleWindow.minSequence) / visibleSpan;
  }, [playback.lastSequence, visibleSpan, visibleWindow.maxSequence, visibleWindow.minSequence]);

  const selectionFractions = useMemo(() => {
    if (selection === null || visibleSpan <= 0) return null;
    const a = (selection.startSequence - visibleWindow.minSequence) / visibleSpan;
    const b = (selection.endSequence - visibleWindow.minSequence) / visibleSpan;
    return {
      start: Math.max(0, Math.min(1, Math.min(a, b))),
      end: Math.max(0, Math.min(1, Math.max(a, b))),
    };
  }, [selection, visibleSpan, visibleWindow.minSequence]);

  const dragFractions = useMemo(() => {
    if (dragging === null || !dragging.moved || visibleSpan <= 0) return null;
    const a = (dragging.startSequence - visibleWindow.minSequence) / visibleSpan;
    const b =
      (dragging.currentSequence - visibleWindow.minSequence) / visibleSpan;
    return {
      start: Math.max(0, Math.min(1, Math.min(a, b))),
      end: Math.max(0, Math.min(1, Math.max(a, b))),
    };
  }, [dragging, visibleSpan, visibleWindow.minSequence]);

  // The active preset, for highlighting the toolbar button.
  const activePreset = useMemo(() => {
    if (trackWidth <= 0) return "fit";
    if (visibleSpan >= fullSpan) return "fit";
    const pxPerEvent = trackWidth / Math.max(1, visibleSpan);
    let best: { key: string; diff: number } = { key: "fit", diff: Infinity };
    for (const p of ZOOM_PRESETS) {
      if (p.pxPerEvent === null) continue;
      const diff = Math.abs(pxPerEvent - p.pxPerEvent) / p.pxPerEvent;
      if (diff < best.diff) best = { key: p.key, diff };
    }
    return best.diff < 0.05 ? best.key : "";
  }, [trackWidth, visibleSpan, fullSpan]);

  return (
    <div
      className="flex flex-col gap-2"
      data-replay-lane-timeline="true"
    >
      <TimelineCursorReadout
        playback={playback}
        window={fullWindow}
        cursorFraction={
          fullSpan > 0
            ? Math.max(
                0,
                Math.min(
                  1,
                  (playback.lastSequence - fullWindow.minSequence) / fullSpan,
                ),
              )
            : 0
        }
      />

      <ZoomToolbar
        activePresetKey={activePreset}
        onSelectPreset={applyPreset}
        visibleSpan={visibleSpan}
        fullSpan={fullSpan}
      />

      <div
        className="relative grid"
        style={{ gridTemplateColumns: `${LABEL_COL_PX}px 1fr` }}
      >
        <div className="flex flex-col gap-[5px] py-1 pr-2">
          {LANES.map((lane) => (
            <div
              key={lane.key}
              className="flex items-center justify-end font-mono text-[10px] uppercase tracking-widest text-muted"
              style={{ height: LANE_HEIGHT_PX }}
            >
              {lane.label}
            </div>
          ))}
          <div
            className="flex items-center justify-end font-mono text-[10px] uppercase tracking-widest text-muted"
            style={{
              height: SCRUBBER_HEIGHT_PX,
              marginTop: LANE_GAP_PX,
            }}
          >
            Cursor
          </div>
        </div>

        <div
          ref={trackRef}
          className="relative rounded border border-line bg-elevated"
          style={{ height: TOTAL_TIMELINE_HEIGHT_PX }}
          onPointerDown={handlePointerDownOnLanes}
          onPointerMove={handlePointerMoveOnLanes}
          onPointerUp={handlePointerUpOnLanes}
          onPointerCancel={() => setDragging(null)}
          onPointerLeave={() => setHover(null)}
          onWheel={handleWheel}
          onDoubleClick={handleDoubleClick}
        >
          {LANES.map((lane, idx) => {
            const top = idx * (LANE_HEIGHT_PX + LANE_GAP_PX);
            return (
              <LaneRow
                key={lane.key}
                lane={lane}
                columns={laneColumns[lane.key]}
                width={trackWidth}
                top={top}
              />
            );
          })}

          {/* bookmark glyphs (always individually rendered — there are
              never enough bookmarks for this to be a perf problem) */}
          {laneColumns.bookmarkGlyphs.map((g) => (
            <button
              key={g.id}
              type="button"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => handleClickBookmark(g.bookmark)}
              onPointerEnter={() =>
                setHover({
                  kind: "bookmark",
                  bookmark: g.bookmark,
                  pixelX: g.pixelX,
                })
              }
              onPointerLeave={() => setHover(null)}
              className={cn(
                "absolute -translate-x-1/2 cursor-pointer transition-transform hover:scale-125",
                g.bookmark.id === selectedBookmarkId && "ring-2 ring-accent",
              )}
              style={{
                top: 0,
                left: g.pixelX,
                width: 12,
                height: LANE_HEIGHT_PX,
                background: "transparent",
                border: 0,
                padding: 0,
              }}
              aria-label={`Jump to bookmark ${g.bookmark.label}`}
            >
              <span
                className="block rotate-45 border border-accent bg-canvas"
                style={{ width: 10, height: 10, margin: "auto" }}
                aria-hidden="true"
              />
            </button>
          ))}

          {/* individual marker dots — only emitted when total marker
              count is small enough that drawing one per item stays
              fast. With 100k+ events the bucket bars in LaneRow do
              the work and bucket clicks resolve via pointerup. */}
          {laneColumns.individualMarkers.map((m) => (
            <button
              key={m.marker.id}
              type="button"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => handleLaneClickMarker(m.marker)}
              onPointerEnter={() =>
                setHover({
                  kind: "marker",
                  marker: m.marker,
                  pixelX: m.pixelX,
                })
              }
              onPointerLeave={() => setHover(null)}
              className={cn(
                "absolute -translate-x-1/2 cursor-pointer transition-transform hover:scale-125",
                m.marker.id === selectedMarkerId && "ring-2 ring-accent",
              )}
              style={{
                top: m.laneTop,
                left: m.pixelX,
                width: 10,
                height: LANE_HEIGHT_PX,
                background: "transparent",
                border: 0,
                padding: 0,
              }}
              aria-label={m.marker.label}
            >
              <span
                className={cn(
                  "block h-3 w-3 rounded-full",
                  severityClass(m.marker.severity),
                )}
                aria-hidden="true"
                style={{ margin: "auto" }}
              />
            </button>
          ))}

          {/* scrubber lane — owns the drag-to-scrub gesture */}
          <ScrubberLane
            playback={playback}
            window={visibleWindow}
            dispatch={dispatch}
            top={TOTAL_LANES_HEIGHT_PX + LANE_GAP_PX}
          />

          {/* selection overlay (committed) */}
          {selectionFractions !== null && (
            <SelectionOverlay
              startFraction={selectionFractions.start}
              endFraction={selectionFractions.end}
              variant="committed"
            />
          )}

          {/* drag-in-progress overlay */}
          {dragFractions !== null && (
            <SelectionOverlay
              startFraction={dragFractions.start}
              endFraction={dragFractions.end}
              variant="active"
            />
          )}

          {/* bright cursor — sits on top of everything */}
          {cursorFraction !== null && (
            <CursorOverlay
              fraction={cursorFraction}
              sequence={playback.lastSequence}
              monotonicNsFromOrigin={Math.max(
                0,
                playback.lastMonotonicNs - fullWindow.minMonotonicNs,
              )}
            />
          )}

          {/* hover tooltip */}
          {hover !== null && trackWidth > 0 && (
            <HoverTooltip
              hover={hover}
              visibleWindow={visibleWindow}
              fullWindow={fullWindow}
              onJump={(intent) => dispatch(intent)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── zoom toolbar ─────────────────────────────────────────────────────────

const ZoomToolbar = memo(function ZoomToolbar({
  activePresetKey,
  onSelectPreset,
  visibleSpan,
  fullSpan,
}: {
  activePresetKey: string;
  onSelectPreset: (preset: ZoomPreset) => void;
  visibleSpan: number;
  fullSpan: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">
      <span>Zoom</span>
      {ZOOM_PRESETS.map((preset) => {
        const active = activePresetKey === preset.key;
        return (
          <button
            key={preset.key}
            type="button"
            onClick={() => onSelectPreset(preset)}
            className={cn(
              "rounded border px-2 py-0.5 transition-colors",
              active
                ? "border-accent bg-accent/10 text-accent"
                : "border-line bg-canvas text-subtle hover:border-accent hover:text-accent",
            )}
            aria-pressed={active}
          >
            {preset.label}
          </button>
        );
      })}
      <span className="ml-2 text-subtle">
        {visibleSpan === fullSpan
          ? `Showing ${formatCount(fullSpan + 1)} events`
          : `Showing ${formatCount(visibleSpan + 1)} of ${formatCount(fullSpan + 1)} events`}
      </span>
    </div>
  );
});

// ── readout ──────────────────────────────────────────────────────────────

const TimelineCursorReadout = memo(function TimelineCursorReadout({
  playback,
  window,
  cursorFraction,
}: {
  playback: ReplayPlaybackSnapshot;
  window: ReplaySessionWindow;
  cursorFraction: number;
}) {
  const tRel = Math.max(0, playback.lastMonotonicNs - window.minMonotonicNs);
  const tTotal = Math.max(0, window.maxMonotonicNs - window.minMonotonicNs);
  return (
    <div className="flex items-baseline justify-between gap-3 font-mono">
      <div className="flex items-baseline gap-3">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          Cursor
        </span>
        <span className="text-sm tabular-nums text-accent">
          #{formatCount(playback.lastSequence)}
        </span>
        <span className="text-[10px] tabular-nums text-subtle">
          / #{formatCount(window.maxSequence)}
        </span>
      </div>
      <div className="flex items-baseline gap-3 text-[10px] uppercase tracking-widest text-subtle">
        <span>t = {formatNs(tRel)}</span>
        <span>/ {formatNs(tTotal)}</span>
        <span className="text-accent">{(cursorFraction * 100).toFixed(2)}%</span>
      </div>
    </div>
  );
});

// ── lane row ─────────────────────────────────────────────────────────────

interface LaneRowProps {
  readonly lane: LaneSpec;
  readonly columns: readonly LaneColumn[];
  readonly width: number;
  readonly top: number;
}

const LaneRow = memo(function LaneRow({
  lane,
  columns,
  width,
  top,
}: LaneRowProps) {
  return (
    <div
      className="absolute left-0 right-0"
      style={{ top, height: LANE_HEIGHT_PX, width: "100%" }}
    >
      <div
        className="absolute inset-0 rounded-sm bg-canvas/40"
        aria-hidden="true"
      />
      <svg
        className="relative block h-full w-full"
        width={Math.max(1, width)}
        height={LANE_HEIGHT_PX}
        viewBox={`0 0 ${Math.max(1, width)} ${LANE_HEIGHT_PX}`}
        preserveAspectRatio="none"
        aria-label={`${lane.label} lane`}
      >
        {columns.map((col) => {
          const fill = severityColor(col.severity);
          // log-scaled height — keeps moderate bursts visible without
          // saturation collapsing every cell to the same height.
          const ratio = Math.min(
            1,
            Math.log10(col.count + 1) / Math.log10(50),
          );
          const barH = Math.max(3, ratio * (LANE_HEIGHT_PX - 6));
          const y = LANE_HEIGHT_PX - barH - 2;
          return (
            <rect
              key={col.pixelX}
              x={col.pixelX}
              y={y}
              width={1}
              height={barH}
              fill={fill}
            />
          );
        })}
      </svg>
    </div>
  );
});

// ── cursor overlay ───────────────────────────────────────────────────────

const CursorOverlay = memo(function CursorOverlay({
  fraction,
  sequence,
  monotonicNsFromOrigin,
}: {
  fraction: number;
  sequence: number;
  monotonicNsFromOrigin: number;
}) {
  const style: CSSProperties = {
    left: `${(fraction * 100).toFixed(3)}%`,
    width: 2,
    boxShadow:
      "0 0 6px var(--color-accent, #60a5fa), 0 0 14px rgba(96,165,250,0.6)",
  };
  // Anchor the label on the opposite side when the cursor is near
  // the right edge, so the pill doesn't get clipped.
  const anchor = fraction > 0.85 ? "right" : "left";
  return (
    <>
      <div
        className="pointer-events-none absolute top-0 bottom-0 z-30 bg-accent"
        style={style}
        aria-hidden="true"
      />
      {/* knob at the top of the cursor line */}
      <div
        className="pointer-events-none absolute z-30"
        style={{
          left: `${(fraction * 100).toFixed(3)}%`,
          top: -5,
          transform: "translateX(-50%)",
        }}
        aria-hidden="true"
      >
        <div
          className="rounded-full border-2 border-accent bg-canvas"
          style={{
            width: 12,
            height: 12,
            boxShadow:
              "0 0 6px var(--color-accent, #60a5fa), 0 0 12px rgba(96,165,250,0.5)",
          }}
        />
      </div>
      {/* sequence + time pill */}
      <div
        className="pointer-events-none absolute z-30 flex items-baseline gap-2 rounded border border-accent bg-panel px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-accent shadow"
        style={{
          left: `${(fraction * 100).toFixed(3)}%`,
          top: -22,
          transform:
            anchor === "left" ? "translateX(8px)" : "translateX(calc(-100% - 8px))",
        }}
        aria-hidden="true"
      >
        <span>#{formatCount(sequence)}</span>
        <span className="text-subtle">{formatNs(monotonicNsFromOrigin)}</span>
      </div>
    </>
  );
});

// ── selection overlay ────────────────────────────────────────────────────

function SelectionOverlay({
  startFraction,
  endFraction,
  variant,
}: {
  startFraction: number;
  endFraction: number;
  variant: "active" | "committed";
}) {
  const left = `${(startFraction * 100).toFixed(3)}%`;
  const width = `${((endFraction - startFraction) * 100).toFixed(3)}%`;
  return (
    <div
      className={cn(
        "pointer-events-none absolute top-0 bottom-0 z-20 border-l border-r",
        variant === "active"
          ? "border-accent bg-accent/15"
          : "border-accent/70 bg-accent/10",
      )}
      style={{ left, width }}
      aria-hidden="true"
    />
  );
}

// ── scrubber lane (drag-to-scrub) ────────────────────────────────────────

function ScrubberLane({
  playback,
  window,
  dispatch,
  top,
}: {
  playback: ReplayPlaybackSnapshot;
  window: ReplaySessionWindow;
  dispatch: (intent: ReplayControlIntent) => void;
  top: number;
}) {
  const viewport = useReplayViewport();
  const preview = useReplayScrubPreview();
  const setViewport = useReplayTimelineStore((s) => s.setViewport);
  const ref = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    const node = ref.current;
    if (node === null) return undefined;
    const apply = (width: number) => {
      setViewport({
        startSequence: window.minSequence,
        endSequence: Math.max(window.minSequence, window.maxSequence),
        widthPx: width,
      });
    };
    apply(node.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) apply(entry.contentRect.width);
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, [setViewport, window.minSequence, window.maxSequence]);

  const { onPointerDown, isDragging } = useReplayScrub({
    viewport,
    window,
    dispatch,
  });

  const span = Math.max(0, window.maxSequence - window.minSequence);
  const cursorFraction =
    span > 0
      ? Math.max(
          0,
          Math.min(1, (playback.lastSequence - window.minSequence) / span),
        )
      : 0;
  const previewFraction =
    preview === null || span <= 0
      ? null
      : Math.max(0, Math.min(1, (preview.sequence - window.minSequence) / span));

  return (
    <div
      ref={ref}
      role="slider"
      tabIndex={0}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(cursorFraction * 100)}
      aria-label={`Replay scrubber at ${Math.round(cursorFraction * 100)}%`}
      data-dragging={isDragging || undefined}
      onPointerDown={(e) => {
        e.stopPropagation();
        onPointerDown(e);
      }}
      className="absolute left-0 right-0 cursor-pointer touch-none select-none rounded-sm border-t border-line/70 bg-canvas"
      style={{ top, height: SCRUBBER_HEIGHT_PX }}
    >
      <div
        className="absolute inset-y-0 left-0 rounded-l-sm bg-accent/25"
        style={{ width: `${(cursorFraction * 100).toFixed(3)}%` }}
        aria-hidden="true"
      />
      {previewFraction !== null && (
        <div
          className="absolute inset-y-0 w-px bg-accent/80"
          style={{ left: `${(previewFraction * 100).toFixed(3)}%` }}
          aria-hidden="true"
        />
      )}
    </div>
  );
}

// ── hover tooltip ────────────────────────────────────────────────────────

interface HoverTargetMarker {
  readonly kind: "marker";
  readonly marker: ReplayTimelineMarker;
  readonly pixelX: number;
}
interface HoverTargetBookmark {
  readonly kind: "bookmark";
  readonly bookmark: ReplayBookmark;
  readonly pixelX: number;
}
type HoverTarget = HoverTargetMarker | HoverTargetBookmark;

function HoverTooltip({
  hover,
  visibleWindow,
  fullWindow,
  onJump,
}: {
  hover: HoverTarget;
  visibleWindow: ReplaySessionWindow;
  fullWindow: ReplaySessionWindow;
  onJump: (intent: ReplayControlIntent) => void;
}) {
  const sequence =
    hover.kind === "marker" ? hover.marker.sequence : hover.bookmark.sequence;
  const monotonicNs =
    hover.kind === "marker"
      ? hover.marker.monotonicNs
      : hover.bookmark.monotonicNs;
  const title =
    hover.kind === "marker" ? hover.marker.label : hover.bookmark.label;
  const intent: Intent =
    hover.kind === "marker"
      ? markerSeverityIntent(hover.marker.severity)
      : "accent";
  const kindLabel = hover.kind === "marker" ? hover.marker.kind : "bookmark";
  const payloadText =
    hover.kind === "marker"
      ? hover.marker.description
      : hover.bookmark.note;

  const visibleSpan = Math.max(1, visibleWindow.maxSequence - visibleWindow.minSequence);
  const fraction = Math.max(
    0,
    Math.min(1, (sequence - visibleWindow.minSequence) / visibleSpan),
  );
  const anchorRight = fraction > 0.7;

  return (
    <div
      className="pointer-events-auto absolute z-40 flex w-max max-w-[24rem] -translate-y-full flex-col gap-1 rounded border border-line bg-panel px-2 py-1.5 font-mono text-[11px] text-text shadow-lg"
      style={{
        left: `${(fraction * 100).toFixed(3)}%`,
        top: -10,
        transform: anchorRight
          ? "translate(calc(-100% - 4px), -100%)"
          : "translate(4px, -100%)",
      }}
      role="tooltip"
    >
      <div className="flex items-baseline gap-2">
        <Badge intent={intent}>{kindLabel}</Badge>
        <span className="truncate" title={title}>
          {title}
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-3 text-[10px] uppercase tracking-widest text-subtle">
        <span>seq #{formatCount(sequence)}</span>
        <span>
          t = {formatNs(Math.max(0, monotonicNs - fullWindow.minMonotonicNs))}
        </span>
      </div>
      {payloadText !== undefined && payloadText.length > 0 && (
        <div className="flex flex-col gap-0.5">
          <span className="text-[9px] uppercase tracking-widest text-muted">
            Payload
          </span>
          <p className="whitespace-normal break-words text-muted">{payloadText}</p>
        </div>
      )}
      <button
        type="button"
        onClick={() => {
          if (hover.kind === "marker") onJump(seekToMarker(hover.marker));
          else onJump(seekToBookmark(hover.bookmark));
        }}
        className="self-start rounded border border-accent bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-accent hover:bg-accent/15"
      >
        Jump
      </button>
    </div>
  );
}

// ── bucketing ────────────────────────────────────────────────────────────

interface LaneColumn {
  readonly pixelX: number;
  readonly count: number;
  readonly severity: ReplayMarkerSeverity;
}

interface BucketedLanes {
  readonly bookmark: readonly LaneColumn[];
  readonly warning: readonly LaneColumn[];
  readonly blocking: readonly LaneColumn[];
  readonly snapshot: readonly LaneColumn[];
  readonly health: readonly LaneColumn[];
  /** Per-marker dots — only populated when the recording has few
   *  enough markers that drawing one per item stays fast. With more
   *  than ``INDIVIDUAL_MARKER_THRESHOLD`` markers total, lanes fall
   *  back to bucket bars and individualMarkers stays empty. */
  readonly individualMarkers: readonly {
    readonly marker: ReplayTimelineMarker;
    readonly pixelX: number;
    readonly laneTop: number;
  }[];
  readonly bookmarkGlyphs: readonly {
    readonly id: string;
    readonly bookmark: ReplayBookmark;
    readonly pixelX: number;
  }[];
  /** Markers that fell inside the visible range, sorted by sequence
   *  — used for bucket-mode click-to-jump (find nearest marker). */
  readonly markersInVisibleRange: readonly ReplayTimelineMarker[];
}

const INDIVIDUAL_MARKER_THRESHOLD = 400;

function bucketLanes(
  markers: readonly ReplayTimelineMarker[],
  bookmarks: readonly ReplayBookmark[],
  visibleWindow: ReplaySessionWindow,
  widthPx: number,
): BucketedLanes {
  const empty: LaneColumn[] = [];
  const result: {
    [K in LaneKey]: Map<number, { count: number; severity: ReplayMarkerSeverity }>;
  } = {
    bookmark: new Map(),
    warning: new Map(),
    blocking: new Map(),
    snapshot: new Map(),
    health: new Map(),
  };
  const bookmarkGlyphs: BucketedLanes["bookmarkGlyphs"] = [];
  const individualMarkers: BucketedLanes["individualMarkers"] = [];
  const markersInVisibleRange: ReplayTimelineMarker[] = [];

  if (widthPx <= 0) {
    return {
      bookmark: empty,
      warning: empty,
      blocking: empty,
      snapshot: empty,
      health: empty,
      individualMarkers: [],
      bookmarkGlyphs: [],
      markersInVisibleRange: [],
    };
  }

  const span = Math.max(
    0,
    visibleWindow.maxSequence - visibleWindow.minSequence,
  );

  const xOf = (sequence: number): number => {
    if (span <= 0) return 0;
    const clamped = Math.max(
      visibleWindow.minSequence,
      Math.min(visibleWindow.maxSequence, sequence),
    );
    return Math.round(
      ((clamped - visibleWindow.minSequence) / span) * widthPx,
    );
  };

  // Count visible markers to decide between per-marker dots vs.
  // bucket-only rendering. We pre-filter both for the threshold
  // decision and for downstream nearest-marker lookups.
  for (const marker of markers) {
    if (
      marker.sequence < visibleWindow.minSequence ||
      marker.sequence > visibleWindow.maxSequence
    ) {
      continue;
    }
    if (laneForMarker(marker) === null) continue;
    markersInVisibleRange.push(marker);
  }
  const useIndividualMarkers =
    markersInVisibleRange.length <= INDIVIDUAL_MARKER_THRESHOLD;

  for (const marker of markersInVisibleRange) {
    const lane = laneForMarker(marker);
    if (lane === null || lane === "bookmark") continue;
    const px = xOf(marker.sequence);
    const bucket = result[lane].get(px);
    if (bucket === undefined) {
      result[lane].set(px, { count: 1, severity: marker.severity });
    } else {
      bucket.count += 1;
      // upgrade to the strongest severity in the bucket
      if (
        bucket.severity !== "critical" &&
        (marker.severity === "critical" ||
          (marker.severity === "warning" && bucket.severity === "info"))
      ) {
        bucket.severity = marker.severity;
      }
    }
    if (useIndividualMarkers) {
      const laneIdx = LANES.findIndex((l) => l.key === lane);
      if (laneIdx >= 0) {
        (individualMarkers as Array<BucketedLanes["individualMarkers"][number]>).push({
          marker,
          pixelX: px,
          laneTop: laneIdx * (LANE_HEIGHT_PX + LANE_GAP_PX),
        });
      }
    }
  }

  for (const b of bookmarks) {
    if (
      b.sequence < visibleWindow.minSequence ||
      b.sequence > visibleWindow.maxSequence
    ) {
      continue;
    }
    const px = xOf(b.sequence);
    const bucket = result.bookmark.get(px);
    if (bucket === undefined) {
      result.bookmark.set(px, { count: 1, severity: "info" });
    } else {
      bucket.count += 1;
    }
    (bookmarkGlyphs as Array<BucketedLanes["bookmarkGlyphs"][number]>).push({
      id: b.id,
      bookmark: b,
      pixelX: px,
    });
  }

  const collect = (key: LaneKey): readonly LaneColumn[] => {
    const out: LaneColumn[] = [];
    for (const [pixelX, v] of result[key]) {
      out.push({ pixelX, count: v.count, severity: v.severity });
    }
    out.sort((a, b) => a.pixelX - b.pixelX);
    return out;
  };

  markersInVisibleRange.sort((a, b) => a.sequence - b.sequence);

  return {
    bookmark: collect("bookmark"),
    warning: collect("warning"),
    blocking: collect("blocking"),
    snapshot: collect("snapshot"),
    health: collect("health"),
    individualMarkers,
    bookmarkGlyphs,
    markersInVisibleRange,
  };
}

function findNearestVisibleMarker(
  markersInVisibleRange: readonly ReplayTimelineMarker[],
  pivot: number,
  visibleSpan: number,
): ReplayTimelineMarker | null {
  if (markersInVisibleRange.length === 0 || visibleSpan <= 0) return null;
  // Linear scan is fine here — visible markers are pre-filtered so
  // this is bounded by what's on-screen, not the total recording.
  let best: ReplayTimelineMarker | null = null;
  let bestDist = Infinity;
  for (const m of markersInVisibleRange) {
    const d = Math.abs(m.sequence - pivot);
    if (d < bestDist) {
      best = m;
      bestDist = d;
    }
  }
  // Hit-test tolerance: ~1% of the visible span, with a floor of 1
  // event so dense recordings still register clicks.
  const tolerance = Math.max(1, Math.round(visibleSpan * 0.01));
  return best !== null && bestDist <= tolerance ? best : null;
}

// ── drag state ───────────────────────────────────────────────────────────

interface DragState {
  readonly pointerId: number;
  readonly startClientX: number;
  readonly startSequence: number;
  readonly currentSequence: number;
  readonly moved: boolean;
}

// ── helpers ──────────────────────────────────────────────────────────────

function severityClass(severity: ReplayMarkerSeverity): string {
  switch (severity) {
    case "critical":
      return "bg-danger";
    case "warning":
      return "bg-warning";
    case "info":
    default:
      return "bg-accent";
  }
}

function severityColor(severity: ReplayMarkerSeverity): string {
  switch (severity) {
    case "critical":
      return "var(--color-danger, #ef4444)";
    case "warning":
      return "var(--color-warning, #f59e0b)";
    case "info":
    default:
      return "var(--color-accent, #60a5fa)";
  }
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
