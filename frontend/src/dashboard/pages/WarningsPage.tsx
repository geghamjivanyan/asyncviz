import { BlockingWarningsContainer } from "@/dashboard/warnings/blocking";

/**
 * Operator-facing entry point for blocking-warning visualization.
 *
 * Mounts the canonical :class:`BlockingWarningsContainer`, which owns
 * snapshot hydration, websocket live updates, projection
 * memoization, selection routing, and render-duration observability.
 *
 * Future warning families (e.g. starvation, deadlock) will mount as
 * sibling sections under the same page chrome — for now the page is a
 * thin wrapper so changing the layout doesn't touch the container.
 */
export function WarningsPage() {
  return <BlockingWarningsContainer />;
}
