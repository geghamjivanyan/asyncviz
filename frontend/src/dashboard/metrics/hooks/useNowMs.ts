/**
 * Heartbeat hook — yields a fresh ``performance.now()`` value on a
 * fixed cadence so "last frame N ms ago" indicators stay current
 * without rendering on every store mutation.
 *
 * Default cadence is 1Hz; tests can pass a faster interval.
 */

import { useEffect, useState } from "react";

export function useNowMs(intervalMs: number = 1000): number {
  const [now, setNow] = useState(() =>
    typeof performance !== "undefined" ? performance.now() : Date.now(),
  );
  useEffect(() => {
    const handle = window.setInterval(() => {
      setNow(typeof performance !== "undefined" ? performance.now() : Date.now());
    }, intervalMs);
    return () => window.clearInterval(handle);
  }, [intervalMs]);
  return now;
}
