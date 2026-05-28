import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { ExecutorActivityOverlay } from "@/dashboard/executors/ExecutorActivityOverlay";
import { layoutFrame } from "@/dashboard/executors/ExecutorActivityRenderer";
import type { ExecutorActivityMarker } from "@/dashboard/executors/models/ExecutorActivityModels";

const marker = (id: string, ns: number): ExecutorActivityMarker => ({
  id,
  executorId: `e-${id}`,
  kind: "contention",
  severity: "warning",
  monotonicNs: ns,
  label: id,
});

describe("<ExecutorActivityOverlay />", () => {
  it("renders one button per visible marker", () => {
    const frame = layoutFrame({
      markers: [marker("a", 100), marker("b", 500), marker("c", 900)],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    render(<ExecutorActivityOverlay frame={frame} heightPx={20} />);
    expect(screen.getAllByTestId("executor-activity-overlay-marker")).toHaveLength(3);
  });

  it("invokes onActivate with marker id + executor id", async () => {
    const onActivate = vi.fn();
    const frame = layoutFrame({
      markers: [marker("a", 500)],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    render(
      <ExecutorActivityOverlay
        frame={frame}
        heightPx={20}
        onActivate={onActivate}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTestId("executor-activity-overlay-marker"));
    expect(onActivate).toHaveBeenCalledWith("a", "e-a");
  });

  it("renders an overflow badge when virtualization caps the list", () => {
    const markers = Array.from({ length: 20 }, (_, i) => marker(`m-${i}`, i * 10));
    const frame = layoutFrame({
      markers,
      startNs: 0,
      endNs: 1000,
      viewportWidth: 1000,
      maxMarkers: 5,
    });
    render(<ExecutorActivityOverlay frame={frame} heightPx={20} />);
    expect(
      screen.getByTestId("executor-activity-overlay-overflow"),
    ).toHaveTextContent(/\+15 more/);
  });

  it("hides itself when empty and hideWhenEmpty is set", () => {
    const frame = layoutFrame({
      markers: [],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    const { queryByTestId } = render(
      <ExecutorActivityOverlay frame={frame} heightPx={20} hideWhenEmpty />,
    );
    expect(queryByTestId("executor-activity-overlay")).toBeNull();
  });
});
