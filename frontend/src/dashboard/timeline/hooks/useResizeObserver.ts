/**
 * Resize-observer hook.
 *
 * Tracks the bounding rect of an element + the current
 * ``devicePixelRatio``. The hook is tolerant of environments without
 * :class:`ResizeObserver` (jsdom) — callers always receive at least
 * one synchronous reading via ``useLayoutEffect``.
 */

import { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { readDevicePixelRatio } from "@/dashboard/timeline/utils/canvas";
import {
  EMPTY_VIEWPORT,
  viewportEqual,
  type TimelineViewport,
} from "@/dashboard/timeline/viewport/TimelineViewport";

export function useElementViewport(): {
  ref: RefObject<HTMLDivElement>;
  viewport: TimelineViewport;
} {
  const ref = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<TimelineViewport>(EMPTY_VIEWPORT);

  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null) return;

    const sync = (): void => {
      const rect = element.getBoundingClientRect();
      const next: TimelineViewport = {
        cssWidth: Math.max(0, Math.floor(rect.width)),
        cssHeight: Math.max(0, Math.floor(rect.height)),
        devicePixelRatio: readDevicePixelRatio(),
      };
      setViewport((prev) => (viewportEqual(prev, next) ? prev : next));
    };

    sync();

    if (typeof ResizeObserver === "undefined") {
      const onResize = () => sync();
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }

    const observer = new ResizeObserver(sync);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, viewport };
}
