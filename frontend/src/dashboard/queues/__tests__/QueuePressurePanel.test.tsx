import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { QueuePressurePanel } from "@/dashboard/queues/QueuePressurePanel";
import { projectQueuePressure } from "@/dashboard/queues/QueuePressureProjection";
import { makeRecord } from "@/dashboard/queues/__fixtures__/queuePressureFixtures";

function renderPanel({
  records,
  selectedQueueId = null,
  onSelectQueue = vi.fn(),
}: {
  records: ReturnType<typeof makeRecord>[];
  selectedQueueId?: string | null;
  onSelectQueue?: (id: string | null) => void;
}) {
  const { views, alarmCount } = projectQueuePressure({ records });
  return {
    onSelectQueue,
    ...render(
      <QueuePressurePanel
        views={views}
        alarmCount={alarmCount}
        selectedQueueId={selectedQueueId}
        onSelectQueue={onSelectQueue}
        status={{ status: "ready", errorMessage: null }}
      />,
    ),
  };
}

describe("<QueuePressurePanel />", () => {
  it("renders the empty state when no queues are present", () => {
    renderPanel({ records: [] });
    expect(screen.getByTestId("queue-pressure-empty")).toBeInTheDocument();
  });

  it("renders a card per queue + the severity badge", () => {
    renderPanel({
      records: [
        makeRecord({ queue_id: "q-a" }),
        makeRecord({
          queue_id: "q-b",
          pressure: { ...makeRecord().pressure, level: "critical", pressure_score: 0.9 },
        }),
      ],
    });
    expect(screen.getAllByTestId("queue-pressure-card")).toHaveLength(2);
    expect(screen.getByTestId("queue-pressure-alarm-count")).toHaveTextContent(/1 alarm/);
  });

  it("invokes onSelectQueue with the clicked queue id", async () => {
    const onSelect = vi.fn();
    renderPanel({
      records: [makeRecord({ queue_id: "q-only" })],
      onSelectQueue: onSelect,
    });
    const user = userEvent.setup();
    await user.click(screen.getByTestId("queue-pressure-card"));
    expect(onSelect).toHaveBeenCalledWith("q-only");
  });

  it("announces severity composition via the live region", () => {
    renderPanel({
      records: [
        makeRecord({ queue_id: "q-a" }),
        makeRecord({
          queue_id: "q-b",
          pressure: { ...makeRecord().pressure, level: "warning", pressure_score: 0.7 },
        }),
      ],
    });
    expect(screen.getByTestId("queue-pressure-live-region")).toHaveTextContent(
      /2 queues/,
    );
  });

  it("shows blocked-producer / blocked-consumer badges on contended queues", () => {
    renderPanel({
      records: [
        makeRecord({
          queue_id: "q-contended",
          contention: {
            ...makeRecord().contention,
            blocked_producers: 3,
            blocked_consumers: 2,
          },
        }),
      ],
    });
    expect(screen.getByTestId("queue-pressure-blocked-producers")).toBeInTheDocument();
    expect(screen.getByTestId("queue-pressure-blocked-consumers")).toBeInTheDocument();
  });
});
