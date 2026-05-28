import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { QueuePressureOverlay } from "@/dashboard/queues/QueuePressureOverlay";
import { layoutFrame } from "@/dashboard/queues/QueuePressureRenderer";
import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";

const marker = (id: string, ns: number): QueuePressureMarker => ({
  id,
  queueId: `q-${id}`,
  kind: "pressure-change",
  severity: "warning",
  monotonicNs: ns,
  label: id,
});

describe("<QueuePressureOverlay />", () => {
  it("renders one button per visible marker", () => {
    const frame = layoutFrame({
      markers: [marker("a", 100), marker("b", 500), marker("c", 900)],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    render(<QueuePressureOverlay frame={frame} heightPx={20} />);
    expect(screen.getAllByTestId("queue-pressure-overlay-marker")).toHaveLength(3);
  });

  it("invokes onActivate with marker id + queue id", async () => {
    const onActivate = vi.fn();
    const frame = layoutFrame({
      markers: [marker("a", 500)],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    render(
      <QueuePressureOverlay frame={frame} heightPx={20} onActivate={onActivate} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTestId("queue-pressure-overlay-marker"));
    expect(onActivate).toHaveBeenCalledWith("a", "q-a");
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
    render(<QueuePressureOverlay frame={frame} heightPx={20} />);
    expect(screen.getByTestId("queue-pressure-overlay-overflow")).toHaveTextContent(
      /\+15 more/,
    );
  });

  it("hides itself when empty and hideWhenEmpty is set", () => {
    const frame = layoutFrame({
      markers: [],
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    const { queryByTestId } = render(
      <QueuePressureOverlay frame={frame} heightPx={20} hideWhenEmpty />,
    );
    expect(queryByTestId("queue-pressure-overlay")).toBeNull();
  });
});
