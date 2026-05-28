import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardSplitView } from "@/dashboard/layout/DashboardSplitView";

describe("DashboardSplitView", () => {
  it("renders panes in declared order", () => {
    render(
      <DashboardSplitView orientation="vertical">
        <DashboardSplitView.Pane size="primary">primary</DashboardSplitView.Pane>
        <DashboardSplitView.Pane size="auxiliary" basis="14rem">
          auxiliary
        </DashboardSplitView.Pane>
      </DashboardSplitView>,
    );
    const panes = screen.getByRole("group").querySelectorAll(":scope > div");
    expect(panes).toHaveLength(2);
    expect(panes[0]).toHaveTextContent("primary");
    expect(panes[1]).toHaveTextContent("auxiliary");
  });

  it("orients horizontally when requested", () => {
    render(
      <DashboardSplitView orientation="horizontal">
        <DashboardSplitView.Pane size="primary">a</DashboardSplitView.Pane>
        <DashboardSplitView.Pane size="auxiliary" basis="14rem">
          b
        </DashboardSplitView.Pane>
      </DashboardSplitView>,
    );
    expect(screen.getByRole("group")).toHaveAttribute("aria-orientation", "horizontal");
  });

  it("applies basis as flex-basis on auxiliary panes", () => {
    render(
      <DashboardSplitView orientation="vertical">
        <DashboardSplitView.Pane size="primary">a</DashboardSplitView.Pane>
        <DashboardSplitView.Pane size="auxiliary" basis="200px">
          b
        </DashboardSplitView.Pane>
      </DashboardSplitView>,
    );
    const aux = screen.getByText("b").closest("div");
    expect(aux?.style.flexBasis).toBe("200px");
  });
});
