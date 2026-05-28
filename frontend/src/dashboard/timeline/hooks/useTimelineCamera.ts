/**
 * Local camera state for the timeline canvas.
 *
 * Component-local on purpose — pan/zoom/scroll are UI concerns. The
 * hook exposes a small mutation surface; tests can drive it directly.
 *
 * When ``autoFit`` is true (the default), the camera tracks the
 * incoming time range. Once the user pans/zooms manually, autoFit
 * flips to ``false`` so the renderer keeps the user's view.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_CAMERA,
  panCamera,
  scrollCamera,
  setRowHeight,
  zoomCameraAroundTime,
  type TimelineCamera,
} from "@/dashboard/timeline/viewport/TimelineCamera";

export interface TimelineCameraStateValue {
  camera: TimelineCamera;
  setCamera: (camera: TimelineCamera) => void;
  pan: (deltaSeconds: number) => void;
  scroll: (deltaRows: number) => void;
  zoomAround: (anchorSeconds: number, factor: number) => void;
  setRowHeightPx: (rowHeightPx: number) => void;
  fitTo: (start: number, end: number) => void;
  /** ``true`` until the user manually pans/zooms. */
  autoFit: boolean;
  disableAutoFit: () => void;
  enableAutoFit: () => void;
}

export interface UseTimelineCameraOptions {
  initial?: TimelineCamera;
  /** Auto-fit data range while the user hasn't moved the camera. */
  autoFitTo?: { start: number; end: number };
}

export function useTimelineCamera(
  options: UseTimelineCameraOptions = {},
): TimelineCameraStateValue {
  const [camera, setCameraState] = useState<TimelineCamera>(options.initial ?? DEFAULT_CAMERA);
  const [autoFit, setAutoFit] = useState(true);
  const autoFitRef = useRef(autoFit);
  autoFitRef.current = autoFit;

  // Track the auto-fit target by *value*, not by object identity — the
  // container produces a fresh object every render, so depending on
  // ``options.autoFitTo`` would loop. Numeric deps are stable.
  const targetStart = options.autoFitTo?.start;
  const targetEnd = options.autoFitTo?.end;
  useEffect(() => {
    if (!autoFitRef.current) return;
    if (targetStart === undefined || targetEnd === undefined) return;
    if (targetEnd <= targetStart) return;
    setCameraState((prev) => {
      if (prev.timeStart === targetStart && prev.timeEnd === targetEnd) return prev;
      return { ...prev, timeStart: targetStart, timeEnd: targetEnd };
    });
  }, [targetStart, targetEnd]);

  const setCamera = useCallback((next: TimelineCamera) => {
    setCameraState(next);
  }, []);

  const pan = useCallback((deltaSeconds: number) => {
    setAutoFit(false);
    setCameraState((prev) => panCamera(prev, deltaSeconds));
  }, []);

  const scroll = useCallback((deltaRows: number) => {
    setCameraState((prev) => scrollCamera(prev, deltaRows));
  }, []);

  const zoomAround = useCallback((anchorSeconds: number, factor: number) => {
    setAutoFit(false);
    setCameraState((prev) => zoomCameraAroundTime(prev, anchorSeconds, factor));
  }, []);

  const setRowHeightPx = useCallback((rowHeightPx: number) => {
    setCameraState((prev) => setRowHeight(prev, rowHeightPx));
  }, []);

  const fitTo = useCallback((start: number, end: number) => {
    if (end <= start) return;
    setCameraState((prev) => ({ ...prev, timeStart: start, timeEnd: end }));
  }, []);

  return {
    camera,
    setCamera,
    pan,
    scroll,
    zoomAround,
    setRowHeightPx,
    fitTo,
    autoFit,
    disableAutoFit: useCallback(() => setAutoFit(false), []),
    enableAutoFit: useCallback(() => setAutoFit(true), []),
  };
}
