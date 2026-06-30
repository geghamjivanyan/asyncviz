import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "@/app/providers/ConfigProvider";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import { BlockingWarningsPanel } from "@/dashboard/warnings/blocking/BlockingWarningsPanel";
import {
  bucketViews,
  projectGroup,
  summarize,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import {
  makeGroup,
  makeMetrics,
  makeStatistics,
} from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

function renderPanel(overrides: Partial<React.ComponentProps<typeof BlockingWarningsPanel>> = {}) {
  const active = projectGroup(makeGroup({ group_id: "active-1" }));
  const recent = projectGroup(
    makeGroup({
      group_id: "recent-1",
      state: "recovered",
      recovered_ns: 2_500_000,
    }),
  );
  const buckets = bucketViews([active, recent]);
  const counts = summarize([active, recent]);
  return render(
    <ConfigProvider config={createTestConfig()}>
      <BlockingWarningsPanel
        buckets={buckets}
        totalCounts={counts}
        filteredCounts={counts}
        statistics={makeStatistics()}
        metrics={makeMetrics()}
        filterMode="all"
        onChangeFilterMode={() => {}}
        selectedGroupId={null}
        onSelectGroup={() => {}}
        status={{ status: "ready", errorMessage: null }}
        {...overrides}
      />
    </ConfigProvider>,
  );
}

describe("BlockingWarningsPanel", () => {
  it("renders active + recent sections with the correct counts", () => {
    renderPanel();
    expect(screen.getByTestId("blocking-warnings-panel")).toBeInTheDocument();
    expect(screen.getAllByTestId("blocking-warnings-card-list").length).toBe(2);
    expect(screen.getByText(/Blocking Warnings/i)).toBeInTheDocument();
    expect(screen.getByTestId("blocking-warning-card-active-1")).toBeInTheDocument();
    expect(screen.getByTestId("blocking-warning-card-recent-1")).toBeInTheDocument();
  });

  it("renders an empty state when there are no warnings", () => {
    const counts = summarize([]);
    renderPanel({
      buckets: { active: [], recent: [] },
      totalCounts: counts,
      filteredCounts: counts,
    });
    expect(screen.getByTestId("blocking-warnings-empty")).toBeInTheDocument();
  });

  it("renders an error banner when status is 'error'", () => {
    renderPanel({ status: { status: "error", errorMessage: "boom" } });
    expect(screen.getByTestId("blocking-warnings-error")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/boom/);
  });

  it("invokes onChangeFilterMode when a chip is clicked", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    renderPanel({ onChangeFilterMode: handler });
    await user.click(screen.getByTestId("blocking-warning-filter-freeze-only"));
    expect(handler).toHaveBeenCalledWith("freeze-only");
  });

  it("invokes onSelectGroup when a card header is clicked", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    renderPanel({ onSelectGroup: handler });
    await user.click(screen.getByTestId("blocking-warning-card-toggle-active-1"));
    expect(handler).toHaveBeenCalledWith("active-1");
  });

  it("renders the expanded inspector for the selected card", () => {
    renderPanel({ selectedGroupId: "active-1" });
    expect(screen.getByTestId("blocking-warning-inspector")).toBeInTheDocument();
  });

  it("shows a 'truncated' notice when the visible cap clips the bucket", () => {
    const many = Array.from({ length: 3 }, (_, i) =>
      projectGroup(makeGroup({ group_id: `a-${i}` })),
    );
    const buckets = bucketViews(many);
    const counts = summarize(many);
    renderPanel({
      buckets,
      totalCounts: counts,
      filteredCounts: counts,
      activeVisibleCap: 2,
    });
    expect(screen.getByTestId("blocking-warnings-truncated")).toHaveTextContent(/\+ 1 more hidden/);
  });

  it("uses a filtered announcement when filterMode != 'all'", () => {
    renderPanel({ filterMode: "freeze-only" });
    expect(screen.getByTestId("blocking-warnings-announcement")).toHaveTextContent(
      /filtered view/i,
    );
  });
});
