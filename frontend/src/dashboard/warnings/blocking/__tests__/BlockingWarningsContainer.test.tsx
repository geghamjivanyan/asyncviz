import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { BlockingWarningsContainer } from "@/dashboard/warnings/blocking/BlockingWarningsContainer";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import { injectBlockingWarningEvent } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningLiveUpdates";
import { resetBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
import {
  makeEvent,
  makeGroup,
  makeMetrics,
  makeSnapshot,
  makeStatistics,
} from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

beforeEach(() => {
  useBlockingWarningStore.getState().reset();
  resetBlockingWarningPanelMetrics();
});

describe("BlockingWarningsContainer", () => {
  it("renders panel header and reflects pre-seeded store state", () => {
    useBlockingWarningStore.getState().hydrateSnapshot(makeSnapshot());
    renderWithProviders(<BlockingWarningsContainer disableHydration disableLiveUpdates />);
    expect(screen.getByTestId("blocking-warnings-panel")).toBeInTheDocument();
    expect(screen.getByTestId("blocking-warning-card-grp-1")).toBeInTheDocument();
    expect(screen.getByTestId("blocking-warning-card-grp-2")).toBeInTheDocument();
  });

  it("reconciles a live opened event into the active bucket", () => {
    renderWithProviders(<BlockingWarningsContainer disableHydration disableLiveUpdates={false} />);
    act(() => {
      injectBlockingWarningEvent(
        makeEvent({
          group_id: "live-1",
          warning_id: "live-1",
          sequence: 1,
          state: "opened",
          transition: "opened",
        }),
      );
    });
    expect(screen.getByTestId("blocking-warning-card-live-1")).toBeInTheDocument();
  });

  it("invokes onRevealTask when a task link is clicked", async () => {
    const user = userEvent.setup();
    useBlockingWarningStore.getState().hydrateSnapshot(
      makeSnapshot({
        active_groups: [makeGroup({ group_id: "g1", task_id: "t1", task_name: "render" })],
        recent_groups: [],
        statistics: makeStatistics(),
        metrics: makeMetrics(),
      }),
    );
    useBlockingWarningStore.getState().setSelectedGroup("g1");
    const onRevealTask = vi.fn();
    renderWithProviders(
      <BlockingWarningsContainer disableHydration disableLiveUpdates onRevealTask={onRevealTask} />,
    );
    await user.click(screen.getByTestId("blocking-warning-task-link"));
    expect(onRevealTask).toHaveBeenCalledWith("t1");
  });

  it("invokes onRevealCapture when a capture chip is clicked", async () => {
    const user = userEvent.setup();
    useBlockingWarningStore.getState().hydrateSnapshot(
      makeSnapshot({
        active_groups: [makeGroup({ group_id: "g1", capture_ids: [42] })],
        recent_groups: [],
        statistics: makeStatistics(),
        metrics: makeMetrics(),
      }),
    );
    useBlockingWarningStore.getState().setSelectedGroup("g1");
    const onRevealCapture = vi.fn();
    renderWithProviders(
      <BlockingWarningsContainer
        disableHydration
        disableLiveUpdates
        onRevealCapture={onRevealCapture}
      />,
    );
    await user.click(screen.getByTestId("blocking-warning-capture-42"));
    expect(onRevealCapture).toHaveBeenCalledWith(42, "g1");
  });
});
