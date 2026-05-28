/**
 * Subscribes a component to a CSS media query.
 *
 * Used by the layout primitives to decide between desktop / narrow
 * layouts. Kept inside ``dashboard/layout/`` because the layout is
 * the only consumer today; if future widgets need it, promote to
 * ``hooks/``.
 *
 * SSR-safe: ``window.matchMedia`` is only touched inside ``useEffect``
 * so server-rendered shells don't crash. The initial render falls back
 * to the ``initial`` argument.
 */

import { useEffect, useState } from "react";

export interface UseMediaQueryOptions {
  /** Value returned on the first render (before ``useEffect`` runs). */
  initial?: boolean;
}

export function useMediaQuery(query: string, options: UseMediaQueryOptions = {}): boolean {
  const { initial = false } = options;
  const [matches, setMatches] = useState<boolean>(initial);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    const mql = window.matchMedia(query);
    const sync = (event: MediaQueryListEvent | MediaQueryList) => {
      setMatches("matches" in event ? event.matches : false);
    };
    sync(mql);
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, [query]);

  return matches;
}

/** Canonical breakpoint matching desktop-class viewports. */
export const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)";

/** Canonical breakpoint matching tablet-and-up viewports. */
export const TABLET_MEDIA_QUERY = "(min-width: 768px)";

/** ``true`` on desktop viewports. */
export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_MEDIA_QUERY, { initial: true });
}

/** ``true`` on tablet-and-up viewports. */
export function useIsTablet(): boolean {
  return useMediaQuery(TABLET_MEDIA_QUERY, { initial: true });
}
