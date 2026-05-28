/**
 * Top-level orchestrator — composes every replay-control piece.
 *
 * One component to drop on the replay page. Owns:
 *   - the engine bridge subscription
 *   - the keyboard handler
 *   - the layout of playback controls + scrubber + markers + minimap +
 *     bookmarks + accessibility helpers
 */

import { useCallback, useMemo, type JSX } from "react";
import { ReplayPlaybackControls } from "@/dashboard/replay/ReplayPlaybackControls";
import { ReplayTimelineBookmarks } from "@/dashboard/replay/ReplayTimelineBookmarks";
import { ReplayTimelineMarkers } from "@/dashboard/replay/ReplayTimelineMarkers";
import { ReplayTimelineMiniMap } from "@/dashboard/replay/ReplayTimelineMiniMap";
import { ReplayTimelinePlayback } from "@/dashboard/replay/ReplayTimelinePlayback";
import { ReplayTimelineScrubber } from "@/dashboard/replay/ReplayTimelineScrubber";
import {
  REPLAY_KEYBOARD_HELP,
} from "@/dashboard/replay/ReplayTimelineAccessibility";
import { useReplayEngineBridge } from "@/dashboard/replay/hooks/useReplayEngineBridge";
import { useReplayKeyboard } from "@/dashboard/replay/hooks/useReplayKeyboard";
import {
  useReplayPlayback,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  recordSeekRequested,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  recordReplayTimelineTrace,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import type { ReplayEngineBridge } from "@/dashboard/replay/hooks/ReplayEngineBridge";
import type {
  ReplayControlIntent,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface ReplayTimelineControlsProps {
  readonly bridge: ReplayEngineBridge;
  readonly enableKeyboard?: boolean;
  readonly className?: string;
}

export function ReplayTimelineControls({
  bridge,
  enableKeyboard = true,
  className,
}: ReplayTimelineControlsProps): JSX.Element {
  useReplayEngineBridge({ bridge });
  const window = useReplayWindow();
  const playback = useReplayPlayback();
  const recordSeekStoreCounter = useReplayTimelineStore(
    (s) => s.recordSeekRequested,
  );
  const addBookmark = useReplayTimelineStore((s) => s.addBookmark);

  const dispatch = useCallback(
    (intent: ReplayControlIntent) => {
      // Mirror the intent into our diagnostics + observability
      // counters, then forward to the engine bridge.
      if (
        intent.type === "seek-sequence" ||
        intent.type === "seek-timestamp" ||
        intent.type === "jump-to-bookmark"
      ) {
        recordSeekRequested();
        recordSeekStoreCounter();
        recordReplayTimelineTrace("seek-requested", JSON.stringify(intent));
      }
      Promise.resolve(bridge.dispatch(intent)).catch(() => undefined);
    },
    [bridge, recordSeekStoreCounter],
  );

  const onBookmark = useCallback(
    (sequence: number) => {
      addBookmark({
        id: `bookmark-${Date.now()}`,
        label: `Bookmark at ${sequence}`,
        sequence,
        monotonicNs: playback.lastMonotonicNs,
        createdAtMs: Date.now(),
      });
    },
    [addBookmark, playback.lastMonotonicNs],
  );

  useReplayKeyboard({
    enabled: enableKeyboard,
    window,
    playback,
    dispatch,
    onBookmark,
  });

  // ARIA describedby content lives in a sibling sr-only node so the
  // scrubber can reference it without leaking text into the layout.
  const helpId = useMemo(
    () => `replay-keyboard-help-${Math.random().toString(36).slice(2, 8)}`,
    [],
  );

  return (
    <section
      aria-label="Replay timeline controls"
      className={"flex flex-col gap-4 " + (className ?? "")}
    >
      <span id={helpId} className="sr-only">
        {REPLAY_KEYBOARD_HELP}
      </span>
      <ReplayPlaybackControls dispatch={dispatch} />
      <ReplayTimelinePlayback />
      <div className="flex flex-col gap-1">
        <ReplayTimelineScrubber dispatch={dispatch} />
        <ReplayTimelineMarkers dispatch={dispatch} />
      </div>
      <ReplayTimelineMiniMap dispatch={dispatch} />
      <ReplayTimelineBookmarks dispatch={dispatch} />
    </section>
  );
}
