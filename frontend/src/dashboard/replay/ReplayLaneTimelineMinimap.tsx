/**
 * Overview minimap that sits beneath the lane timeline.
 *
 * Shows the entire recording bucketed into per-pixel columns + an
 * overlay rectangle for the currently-visible window. Clicking moves
 * the cursor; dragging the viewport rectangle pans the visible
 * window (the parent receives the new visible range via
 * ``onViewportChange``).
 */

import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { cn } from "@/lib/cn";
import { bucketMarkers } from "@/dashboard/replay/ReplayTimelineProjection";
import { seekFromFraction } from "@/dashboard/replay/ReplayTimelineSeek";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayMarkerSeverity,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const SEVERITY_COLOR: Record<ReplayMarkerSeverity, string> = {
  info: "var(--color-accent, #60a5fa)",
  warning: "var(--color-warning, #f59e0b)",
  critical: "var(--color-danger, #ef4444)",
};

export interface ReplayLaneTimelineMinimapProps {
  readonly playback: ReplayPlaybackSnapshot;
  readonly window: ReplaySessionWindow;
  readonly markers: readonly ReplayTimelineMarker[];
  readonly bookmarks: readonly ReplayBookmark[];
  readonly visibleStartSequence: number;
  readonly visibleEndSequence: number;
  readonly onViewportChange: (start: number, end: number) => void;
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly heightPx?: number;
}

export const ReplayLaneTimelineMinimap = memo(function ReplayLaneTimelineMinimap({
  playback,
  window,
  markers,
  bookmarks,
  visibleStartSequence,
  visibleEndSequence,
  onViewportChange,
  dispatch,
  heightPx = 36,
}: ReplayLaneTimelineMinimapProps): JSX.Element {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [dragging, setDragging] = useState<DragState | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (node === null) return undefined;
    const apply = () => setWidth(node.getBoundingClientRect().width);
    apply();
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(apply);
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const span = Math.max(0, window.maxSequence - window.minSequence);

  const buckets = useMemo(() => {
    if (width <= 0 || span <= 0) return [];
    return bucketMarkers(markers, window, Math.max(1, Math.floor(width)));
  }, [markers, window, width, span]);

  const cursorFraction =
    span > 0 ? Math.max(0, Math.min(1, (playback.lastSequence - window.minSequence) / span)) : 0;
  const visibleStartFraction =
    span > 0 ? Math.max(0, Math.min(1, (visibleStartSequence - window.minSequence) / span)) : 0;
  const visibleEndFraction =
    span > 0 ? Math.max(0, Math.min(1, (visibleEndSequence - window.minSequence) / span)) : 1;
  const visibleWidthFraction = Math.max(0.01, visibleEndFraction - visibleStartFraction);

  const sequenceFromClientX = useCallback(
    (clientX: number): number => {
      const node = ref.current;
      if (node === null || span <= 0) return window.minSequence;
      const bounds = node.getBoundingClientRect();
      const fraction = Math.max(
        0,
        Math.min(1, (clientX - bounds.left) / Math.max(1, bounds.width)),
      );
      return Math.round(window.minSequence + fraction * span);
    },
    [span, window.minSequence],
  );

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      const node = ref.current;
      if (node === null) return;
      const bounds = node.getBoundingClientRect();
      const fraction = (event.clientX - bounds.left) / Math.max(1, bounds.width);
      const inViewport = fraction >= visibleStartFraction && fraction <= visibleEndFraction;
      if (inViewport) {
        event.currentTarget.setPointerCapture(event.pointerId);
        setDragging({
          pointerId: event.pointerId,
          mode: "pan",
          grabFraction: fraction - visibleStartFraction,
        });
      } else {
        // Click outside the viewport — center the window there
        // (and seek the cursor).
        const visibleSpan = visibleEndSequence - visibleStartSequence;
        const center = sequenceFromClientX(event.clientX);
        let newStart = Math.max(
          window.minSequence,
          Math.min(window.maxSequence - visibleSpan, center - Math.floor(visibleSpan / 2)),
        );
        let newEnd = newStart + visibleSpan;
        if (newEnd > window.maxSequence) {
          newEnd = window.maxSequence;
          newStart = Math.max(window.minSequence, newEnd - visibleSpan);
        }
        onViewportChange(newStart, newEnd);
        dispatch(seekFromFraction(fraction, window));
      }
    },
    [
      dispatch,
      onViewportChange,
      sequenceFromClientX,
      visibleEndFraction,
      visibleEndSequence,
      visibleStartFraction,
      visibleStartSequence,
      window,
    ],
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (dragging === null || event.pointerId !== dragging.pointerId) return;
      const node = ref.current;
      if (node === null) return;
      const bounds = node.getBoundingClientRect();
      const fraction = Math.max(
        0,
        Math.min(1, (event.clientX - bounds.left) / Math.max(1, bounds.width)),
      );
      const visibleSpan = visibleEndSequence - visibleStartSequence;
      let newStartFraction = fraction - dragging.grabFraction;
      newStartFraction = Math.max(0, Math.min(1 - visibleWidthFraction, newStartFraction));
      const newStart = Math.round(window.minSequence + newStartFraction * span);
      const newEnd = Math.min(window.maxSequence, newStart + visibleSpan);
      onViewportChange(newStart, newEnd);
    },
    [
      dragging,
      onViewportChange,
      span,
      visibleEndSequence,
      visibleStartSequence,
      visibleWidthFraction,
      window.maxSequence,
      window.minSequence,
    ],
  );

  const handlePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (dragging === null || event.pointerId !== dragging.pointerId) return;
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // already released
      }
      setDragging(null);
    },
    [dragging],
  );

  return (
    <div
      ref={ref}
      role="region"
      aria-label="Replay minimap"
      className="relative w-full cursor-pointer touch-none select-none rounded border border-line bg-canvas"
      style={{ height: heightPx }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => setDragging(null)}
    >
      <svg
        aria-hidden="true"
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${Math.max(1, width)} ${heightPx}`}
        preserveAspectRatio="none"
      >
        {buckets.map((bucket, idx) => {
          const total = bucket.markerCount;
          if (total === 0) return null;
          const severity: ReplayMarkerSeverity = bucket.severityCount.critical
            ? "critical"
            : bucket.severityCount.warning
              ? "warning"
              : "info";
          const ratio = Math.min(1, Math.log10(total + 1) / Math.log10(50));
          const barHeight = Math.max(2, ratio * (heightPx - 6));
          return (
            <rect
              key={`${bucket.startSequence}-${bucket.endSequence}`}
              x={idx}
              y={heightPx - barHeight - 1}
              width={1}
              height={barHeight}
              fill={SEVERITY_COLOR[severity]}
            />
          );
        })}
        {bookmarks.length > 0 &&
          bookmarks.map((b) => {
            const f = span > 0 ? (b.sequence - window.minSequence) / span : 0;
            const x = Math.round(Math.max(0, Math.min(1, f)) * Math.max(1, width));
            return (
              <rect
                key={b.id}
                x={x}
                y={0}
                width={1}
                height={4}
                fill="var(--color-accent, #60a5fa)"
              />
            );
          })}
      </svg>

      {/* visible-window overlay */}
      <div
        className={cn(
          "absolute top-0 bottom-0 border-l border-r border-accent bg-accent/15",
          dragging?.mode === "pan" ? "cursor-grabbing" : "cursor-grab",
        )}
        style={{
          left: `${(visibleStartFraction * 100).toFixed(3)}%`,
          width: `${(visibleWidthFraction * 100).toFixed(3)}%`,
        }}
        aria-hidden="true"
      />
      {/* cursor pip */}
      <div
        className="pointer-events-none absolute top-0 bottom-0 w-px bg-accent"
        style={{
          left: `${(cursorFraction * 100).toFixed(3)}%`,
          boxShadow: "0 0 4px var(--color-accent, #60a5fa)",
        }}
        aria-hidden="true"
      />
    </div>
  );
});

interface DragState {
  readonly pointerId: number;
  readonly mode: "pan";
  /** Where inside the viewport the user grabbed it (0..visibleFraction). */
  readonly grabFraction: number;
}
