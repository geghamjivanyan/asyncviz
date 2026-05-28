/**
 * Compact playback summary banner.
 *
 * Shows the playback state, current speed, and human-readable
 * position. Designed to be unobtrusive — sits alongside the
 * scrubber as a tiny piece of read-only context.
 */

import type { JSX } from "react";
import {
  describePlaybackForAccessibility,
} from "@/dashboard/replay/ReplayTimelineAccessibility";
import {
  useReplayPlayback,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";

export interface ReplayTimelinePlaybackProps {
  readonly className?: string;
}

export function ReplayTimelinePlayback({
  className,
}: ReplayTimelinePlaybackProps): JSX.Element {
  const playback = useReplayPlayback();
  const window = useReplayWindow();
  const summary = describePlaybackForAccessibility(playback, window);
  return (
    <div
      aria-live="polite"
      className={
        "text-xs font-mono uppercase tracking-widest text-textMuted " +
        (className ?? "")
      }
    >
      {summary}
    </div>
  );
}
