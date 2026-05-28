import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReplayPlaybackControls } from "@/dashboard/replay/ReplayPlaybackControls";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";

afterEach(() => {
  useReplayTimelineStore.getState().reset();
});

describe("<ReplayPlaybackControls/>", () => {
  it("renders play button when paused", () => {
    useReplayTimelineStore.setState({
      playback: {
        state: "paused",
        speed: 1,
        lastSequence: 0,
        lastMonotonicNs: 0,
        framesDispatched: 0,
        paused: true,
      },
    });
    const dispatch = vi.fn();
    render(<ReplayPlaybackControls dispatch={dispatch} />);
    expect(screen.getByRole("button", { name: /play replay/i })).toBeInTheDocument();
  });

  it("dispatches play when play button clicked", async () => {
    useReplayTimelineStore.setState({
      playback: {
        state: "paused",
        speed: 1,
        lastSequence: 0,
        lastMonotonicNs: 0,
        framesDispatched: 0,
        paused: true,
      },
    });
    const dispatch = vi.fn();
    render(<ReplayPlaybackControls dispatch={dispatch} />);
    await userEvent.click(screen.getByRole("button", { name: /play replay/i }));
    expect(dispatch).toHaveBeenCalledWith({ type: "play" });
  });

  it("dispatches pause when playing", async () => {
    useReplayTimelineStore.setState({
      playback: {
        state: "playing",
        speed: 1,
        lastSequence: 10,
        lastMonotonicNs: 100,
        framesDispatched: 10,
        paused: false,
      },
    });
    const dispatch = vi.fn();
    render(<ReplayPlaybackControls dispatch={dispatch} />);
    await userEvent.click(screen.getByRole("button", { name: /pause replay/i }));
    expect(dispatch).toHaveBeenCalledWith({ type: "pause" });
  });

  it("dispatches step-forward", async () => {
    const dispatch = vi.fn();
    render(<ReplayPlaybackControls dispatch={dispatch} />);
    await userEvent.click(screen.getByRole("button", { name: /step forward/i }));
    expect(dispatch).toHaveBeenCalledWith({ type: "step-forward" });
  });

  it("dispatches set-speed", async () => {
    const dispatch = vi.fn();
    render(<ReplayPlaybackControls dispatch={dispatch} />);
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /replay speed/i }),
      "2",
    );
    expect(dispatch).toHaveBeenCalledWith({ type: "set-speed", speed: 2 });
  });
});
