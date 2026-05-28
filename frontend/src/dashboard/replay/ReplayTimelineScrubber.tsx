/**
 * Horizontal scrubber + playhead.
 *
 * Renders a thin track + a draggable thumb at the current playhead.
 * Pointer events fire through :hook:`useReplayScrub`; keyboard
 * focus + ARIA make it a fully usable slider for screen reader
 * users.
 */

import { useEffect, useMemo, useRef, type JSX } from "react";
import {
  useReplayPlayback,
  useReplayScrubPreview,
  useReplayViewport,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import { useReplayScrub } from "@/dashboard/replay/hooks/useReplayScrub";
import {
  describePlaybackForAccessibility,
} from "@/dashboard/replay/ReplayTimelineAccessibility";
import {
  sequenceToPixel,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayControlIntent,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface ReplayTimelineScrubberProps {
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly heightPx?: number;
  readonly className?: string;
}

export function ReplayTimelineScrubber({
  dispatch,
  heightPx = 32,
  className,
}: ReplayTimelineScrubberProps): JSX.Element {
  const playback = useReplayPlayback();
  const window = useReplayWindow();
  const viewport = useReplayViewport();
  const preview = useReplayScrubPreview();
  const setViewport = useReplayTimelineStore((s) => s.setViewport);
  const trackRef = useRef<HTMLDivElement | null>(null);

  // Observe element width so the viewport stays in sync with layout.
  useEffect(() => {
    const node = trackRef.current;
    if (!node) return undefined;
    const setWidth = (width: number) => {
      setViewport({
        startSequence: window.minSequence,
        endSequence: Math.max(window.minSequence, window.maxSequence),
        widthPx: width,
      });
    };
    setWidth(node.getBoundingClientRect().width);
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [setViewport, window.maxSequence, window.minSequence]);

  const { onPointerDown, isDragging } = useReplayScrub({
    viewport,
    window,
    dispatch,
  });

  const playheadX = useMemo(
    () => sequenceToPixel(playback.lastSequence, viewport),
    [playback.lastSequence, viewport],
  );

  const previewX = useMemo(() => {
    if (preview === null) return null;
    return sequenceToPixel(preview.sequence, viewport);
  }, [preview, viewport]);

  const ariaLabel = describePlaybackForAccessibility(playback, window);
  const sliderValue =
    window.maxSequence > 0
      ? Math.round(
          ((preview ? preview.sequence : playback.lastSequence) /
            window.maxSequence) *
            100,
        )
      : 0;

  return (
    <div
      ref={trackRef}
      role="slider"
      tabIndex={0}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={sliderValue}
      aria-label={ariaLabel}
      onPointerDown={onPointerDown}
      data-dragging={isDragging || undefined}
      style={{ height: heightPx }}
      className={
        "relative w-full cursor-pointer select-none rounded bg-surface " +
        "border border-border " +
        (className ?? "")
      }
    >
      {/* Filled portion of the track up to the playhead. */}
      <div
        className="absolute inset-y-0 left-0 rounded-l bg-accent/30"
        style={{ width: playheadX }}
        aria-hidden
      />
      {/* Scrub preview marker (during drag). */}
      {previewX !== null && (
        <div
          className="absolute inset-y-0 w-px bg-accent/80"
          style={{ left: previewX }}
          aria-hidden
        />
      )}
      {/* Playhead thumb. */}
      <div
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-3/4 w-1 rounded bg-accent"
        style={{ left: playheadX }}
        aria-hidden
      />
    </div>
  );
}
