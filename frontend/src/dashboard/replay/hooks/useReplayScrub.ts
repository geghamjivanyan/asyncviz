/**
 * Scrub gesture coordinator.
 *
 * Wires pointer down/move/up against the scrubber's bounding box,
 * publishes :class:`ReplayScrubPreview`s into the store while the
 * drag is in flight, and dispatches a final seek intent on release.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clamp,
  pixelToSequence,
  sequenceToTimestamp,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  recordScrubEnd,
  recordScrubStart,
  recordScrubUpdate,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import { recordReplayTimelineTrace } from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import type {
  ReplayControlIntent,
  ReplaySessionWindow,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface UseReplayScrubOptions {
  readonly viewport: ReplayTimelineViewport;
  readonly window: ReplaySessionWindow;
  readonly dispatch: (intent: ReplayControlIntent) => void;
}

export interface UseReplayScrubResult {
  readonly onPointerDown: (event: React.PointerEvent<HTMLElement>) => void;
  readonly isDragging: boolean;
}

export function useReplayScrub({
  viewport,
  window: replayWindow,
  dispatch,
}: UseReplayScrubOptions): UseReplayScrubResult {
  const beginScrub = useReplayTimelineStore((s) => s.beginScrub);
  const updateScrub = useReplayTimelineStore((s) => s.updateScrub);
  const endScrub = useReplayTimelineStore((s) => s.endScrub);
  const recordSeekRequested = useReplayTimelineStore((s) => s.recordSeekRequested);
  const [dragging, setDragging] = useState(false);
  const elementRef = useRef<HTMLElement | null>(null);

  const buildPreview = useCallback(
    (clientX: number, bounds: DOMRect) => {
      const localX = clamp(clientX - bounds.left, 0, bounds.width);
      const sequence = pixelToSequence(localX, {
        ...viewport,
        widthPx: bounds.width,
      });
      const monotonicNs = sequenceToTimestamp(sequence, replayWindow);
      return {
        sequence,
        monotonicNs,
        clientX,
        normalizedFraction: bounds.width > 0 ? localX / bounds.width : 0,
      };
    },
    [viewport, replayWindow],
  );

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      const element = event.currentTarget;
      elementRef.current = element;
      element.setPointerCapture?.(event.pointerId);
      const bounds = element.getBoundingClientRect();
      const preview = buildPreview(event.clientX, bounds);
      beginScrub(preview);
      setDragging(true);
      recordScrubStart();
      recordReplayTimelineTrace("scrub-start", `seq=${preview.sequence}`);
    },
    [beginScrub, buildPreview],
  );

  // Move + up handlers — attach to the captured element while
  // dragging so they survive the pointer leaving the scrubber's
  // bounding box.
  useEffect(() => {
    if (!dragging) return undefined;
    const element = elementRef.current;
    if (!element) return undefined;

    const handleMove = (event: PointerEvent) => {
      const bounds = element.getBoundingClientRect();
      const preview = buildPreview(event.clientX, bounds);
      updateScrub(preview);
      recordScrubUpdate();
      recordReplayTimelineTrace("scrub-update", `seq=${preview.sequence}`);
    };

    const handleUp = (event: PointerEvent) => {
      const bounds = element.getBoundingClientRect();
      const preview = buildPreview(event.clientX, bounds);
      updateScrub(preview);
      endScrub();
      setDragging(false);
      recordScrubEnd();
      recordSeekRequested();
      recordReplayTimelineTrace("scrub-end", `seq=${preview.sequence}`);
      dispatch({ type: "seek-sequence", sequence: preview.sequence });
      element.releasePointerCapture?.(event.pointerId);
    };

    element.addEventListener("pointermove", handleMove);
    element.addEventListener("pointerup", handleUp);
    element.addEventListener("pointercancel", handleUp);
    return () => {
      element.removeEventListener("pointermove", handleMove);
      element.removeEventListener("pointerup", handleUp);
      element.removeEventListener("pointercancel", handleUp);
    };
  }, [dragging, buildPreview, updateScrub, endScrub, dispatch, recordSeekRequested]);

  return { onPointerDown, isDragging: dragging };
}
