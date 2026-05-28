import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { SemaphoreContentionPanel } from "@/dashboard/semaphores/SemaphoreContentionPanel";
import { projectSemaphoreContention } from "@/dashboard/semaphores/SemaphoreContentionProjection";
import { makeRecord } from "@/dashboard/semaphores/__fixtures__/semaphoreContentionFixtures";

function renderPanel({
  records,
  selectedSemaphoreId = null,
  onSelectSemaphore = vi.fn(),
}: {
  records: ReturnType<typeof makeRecord>[];
  selectedSemaphoreId?: string | null;
  onSelectSemaphore?: (id: string | null) => void;
}) {
  const { views, alarmCount } = projectSemaphoreContention({ records });
  return {
    onSelectSemaphore,
    ...render(
      <SemaphoreContentionPanel
        views={views}
        alarmCount={alarmCount}
        selectedSemaphoreId={selectedSemaphoreId}
        onSelectSemaphore={onSelectSemaphore}
        status={{ status: "ready", errorMessage: null }}
      />,
    ),
  };
}

describe("<SemaphoreContentionPanel />", () => {
  it("renders the empty state when no semaphores are tracked", () => {
    renderPanel({ records: [] });
    expect(screen.getByTestId("semaphore-contention-empty")).toBeInTheDocument();
  });

  it("renders a card per semaphore and the alarm badge", () => {
    renderPanel({
      records: [
        makeRecord({ semaphoreId: "s-a" }),
        makeRecord({
          semaphoreId: "s-b",
          currentValue: 0,
          waiterCount: 2,
        }),
      ],
    });
    expect(screen.getAllByTestId("semaphore-contention-card")).toHaveLength(2);
    expect(screen.getByTestId("semaphore-contention-alarm-count")).toHaveTextContent(
      /1 alarm/,
    );
  });

  it("invokes onSelectSemaphore with the clicked semaphore id", async () => {
    const onSelect = vi.fn();
    renderPanel({
      records: [makeRecord({ semaphoreId: "s-only" })],
      onSelectSemaphore: onSelect,
    });
    const user = userEvent.setup();
    await user.click(screen.getByTestId("semaphore-contention-card"));
    expect(onSelect).toHaveBeenCalledWith("s-only");
  });

  it("announces severity composition via the live region", () => {
    renderPanel({
      records: [
        makeRecord({ semaphoreId: "s-a" }),
        makeRecord({
          semaphoreId: "s-b",
          currentValue: 1,
          waiterCount: 0,
        }),
      ],
    });
    expect(
      screen.getByTestId("semaphore-contention-live-region"),
    ).toHaveTextContent(/2 semaphores/);
  });

  it("shows waiter + cancelled badges on contended semaphores", () => {
    renderPanel({
      records: [
        makeRecord({
          semaphoreId: "s-contended",
          currentValue: 0,
          waiterCount: 3,
          cancelledWaitCount: 2,
        }),
      ],
    });
    expect(screen.getByTestId("semaphore-contention-waiters")).toBeInTheDocument();
    expect(screen.getByTestId("semaphore-contention-cancelled")).toBeInTheDocument();
  });
});
