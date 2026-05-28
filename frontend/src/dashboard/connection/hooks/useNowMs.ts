/**
 * 1Hz heartbeat hook — yields a fresh ``performance.now()`` value so
 * "last frame N ms ago" indicators stay current without re-rendering
 * on every store mutation.
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
