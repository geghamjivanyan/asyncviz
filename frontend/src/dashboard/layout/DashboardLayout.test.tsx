/**
 * Tests for the canonical :class:`DashboardLayout` composition.
 *
 * Each test mounts the layout with the canonical provider stack via
 * :func:`renderWithRouter` so :func:`useRuntimeConnection`,
 * :func:`useDashboardLayout`, and :class:`NavLink` resolve correctly.
 */

import { describe, expect, it } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { renderWithRouter } from "@/test/render";
import { DashboardLayout } from "@/dashboard/layout/DashboardLayout";
import { DashboardSidebar } from "@/dashboard/layout/DashboardSidebar";
import { ROUTES } from "@/app/routing/routes";

function MountAt({ path, ui }: { path: string; ui: React.ReactNode }) {
  return (
    <Routes>
      <Route path={path} element={ui} />
    </Routes>
  );
}

describe("DashboardLayout", () => {
  it("renders the canonical header + content + status bar", () => {
    renderWithRouter(
      <MountAt
        path={ROUTES.diagnostics}
        ui={<DashboardLayout>diagnostics body</DashboardLayout>}
      />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByText("diagnostics body")).toBeInTheDocument();
  });

  it("renders the default sidebar by default", () => {
    renderWithRouter(
      <MountAt path={ROUTES.diagnostics} ui={<DashboardLayout>body</DashboardLayout>} />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    // Two complementary regions exist: one is the default sidebar.
    const sidebars = screen.getAllByRole("complementary");
    expect(sidebars.length).toBeGreaterThanOrEqual(1);
  });

  it("hides default chrome when slots are explicitly null", () => {
    renderWithRouter(
      <MountAt
        path={ROUTES.diagnostics}
        ui={
          <DashboardLayout header={null} sidebar={null} footer={null}>
            body
          </DashboardLayout>
        }
      />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("renders the aside slot to the right of the main content", () => {
    renderWithRouter(
      <MountAt
        path={ROUTES.diagnostics}
        ui={
          <DashboardLayout
            aside={
              <aside role="complementary" aria-label="Inspector">
                aside-content
              </aside>
            }
          >
            body
          </DashboardLayout>
        }
      />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    expect(screen.getByLabelText("Inspector")).toHaveTextContent("aside-content");
  });

  it("toggles the sidebar when the header button is clicked", () => {
    renderWithRouter(
      <MountAt path={ROUTES.diagnostics} ui={<DashboardLayout>body</DashboardLayout>} />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    const toggle = screen.getByRole("button", { name: /sidebar/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("starts with the sidebar collapsed when initialState requests it", () => {
    renderWithRouter(
      <MountAt
        path={ROUTES.diagnostics}
        ui={
          <DashboardLayout initialState={{ sidebar: "collapsed" }} sidebar={<DashboardSidebar />}>
            body
          </DashboardLayout>
        }
      />,
      { initialEntries: [ROUTES.diagnostics] },
    );
    const toggle = screen.getByRole("button", { name: /sidebar/i });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });
});
