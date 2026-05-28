import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { ExecutorActivityPanel } from "@/dashboard/executors/ExecutorActivityPanel";
import { projectExecutorActivity } from "@/dashboard/executors/ExecutorActivityProjection";
import { makeRecord } from "@/dashboard/executors/__fixtures__/executorActivityFixtures";

function renderPanel({
  records,
  selectedExecutorId = null,
  onSelectExecutor = vi.fn(),
}: {
  records: ReturnType<typeof makeRecord>[];
  selectedExecutorId?: string | null;
  onSelectExecutor?: (id: string | null) => void;
}) {
  const { views, alarmCount } = projectExecutorActivity({ records });
  return {
    onSelectExecutor,
    ...render(
      <ExecutorActivityPanel
        views={views}
        alarmCount={alarmCount}
        selectedExecutorId={selectedExecutorId}
        onSelectExecutor={onSelectExecutor}
        status={{ status: "ready", errorMessage: null }}
      />,
    ),
  };
}

describe("<ExecutorActivityPanel />", () => {
  it("renders the empty state when no executors are tracked", () => {
    renderPanel({ records: [] });
    expect(screen.getByTestId("executor-activity-empty")).toBeInTheDocument();
  });

  it("renders a card per executor and the alarm badge", () => {
    renderPanel({
      records: [
        makeRecord({ executor_id: "e-a" }),
        makeRecord({
          executor_id: "e-b",
          saturation: { ...makeRecord().saturation, level: "critical" },
        }),
      ],
    });
    expect(screen.getAllByTestId("executor-activity-card")).toHaveLength(2);
    expect(screen.getByTestId("executor-activity-alarm-count")).toHaveTextContent(
      /1 alarm/,
    );
  });

  it("invokes onSelectExecutor with the clicked executor id", async () => {
    const onSelect = vi.fn();
    renderPanel({
      records: [makeRecord({ executor_id: "e-only" })],
      onSelectExecutor: onSelect,
    });
    const user = userEvent.setup();
    await user.click(screen.getByTestId("executor-activity-card"));
    expect(onSelect).toHaveBeenCalledWith("e-only");
  });

  it("announces severity composition via the live region", () => {
    renderPanel({
      records: [
        makeRecord({ executor_id: "e-a" }),
        makeRecord({
          executor_id: "e-b",
          saturation: { ...makeRecord().saturation, level: "warning" },
        }),
      ],
    });
    expect(
      screen.getByTestId("executor-activity-live-region"),
    ).toHaveTextContent(/2 executors/);
  });

  it("shows backlog + failures badges on contended executors", () => {
    renderPanel({
      records: [
        makeRecord({
          executor_id: "e-contended",
          throughput: { ...makeRecord().throughput, backlog: 4, failures: 2 },
        }),
      ],
    });
    expect(screen.getByTestId("executor-activity-backlog")).toBeInTheDocument();
    expect(screen.getByTestId("executor-activity-failures")).toBeInTheDocument();
  });
});
