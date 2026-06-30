/**
 * Playback controls — play / pause / step / speed selector.
 *
 * Renders a small button group bound to a :class:`ReplayEngineBridge`
 * dispatch callback. All visual state is derived from the playback
 * snapshot in the store so the button labels always match the engine.
 */

import type { JSX } from "react";
import { useReplayPlayback } from "@/dashboard/replay/ReplayTimelineSelectors";
import { REPLAY_SPEED_PRESETS } from "@/dashboard/replay/ReplayPlaybackPresets";
import type { ReplayControlIntent } from "@/dashboard/replay/models/ReplayTimelineModels";

export interface ReplayPlaybackControlsProps {
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly className?: string;
}

export function ReplayPlaybackControls({
  dispatch,
  className,
}: ReplayPlaybackControlsProps): JSX.Element {
  const playback = useReplayPlayback();
  const isPlaying = playback.state === "playing" && !playback.paused;

  return (
    <div
      className={
        "flex items-center gap-2 text-xs font-mono uppercase tracking-widest " + (className ?? "")
      }
      role="group"
      aria-label="Replay playback controls"
    >
      <button
        type="button"
        aria-label={isPlaying ? "Pause replay" : "Play replay"}
        aria-pressed={isPlaying}
        onClick={() => dispatch({ type: isPlaying ? "pause" : "play" })}
        className="rounded border border-border bg-surface px-3 py-1 text-text"
      >
        {isPlaying ? "Pause" : "Play"}
      </button>

      <button
        type="button"
        aria-label="Step forward one frame"
        onClick={() => dispatch({ type: "step-forward" })}
        className="rounded border border-border bg-surface px-3 py-1 text-text"
      >
        Step
      </button>

      <button
        type="button"
        aria-label="Stop replay"
        onClick={() => dispatch({ type: "stop" })}
        className="rounded border border-border bg-surface px-3 py-1 text-text"
      >
        Stop
      </button>

      <label className="flex items-center gap-1 text-text">
        <span className="text-textMuted">Speed</span>
        <select
          aria-label="Replay speed"
          value={playback.speed}
          onChange={(event) =>
            dispatch({
              type: "set-speed",
              speed: Number.parseFloat(event.target.value),
            })
          }
          className="rounded border border-border bg-surface px-2 py-0.5 text-text"
        >
          {REPLAY_SPEED_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}x
            </option>
          ))}
        </select>
      </label>

      <span aria-live="polite" className="ml-2 text-textMuted normal-case tracking-normal">
        {playback.state}
        {playback.paused && playback.state !== "paused" ? " (paused)" : ""}
        {playback.errorDetail ? ` — ${playback.errorDetail}` : ""}
      </span>
    </div>
  );
}
