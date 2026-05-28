/**
 * Routing tests.
 *
 * Uses :class:`MemoryRouter` + the canonical route element tree so the
 * test exercises real navigation without touching ``window.history``
 * or :func:`createBrowserRouter`.
 */

import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ROUTES, NAVIGABLE_ROUTES } from "@/app/routing/routes";
import { DashboardShell } from "@/app/layout/DashboardShell";
import { TimelinePage } from "@/dashboard/pages/TimelinePage";
import { MetricsPage } from "@/dashboard/pages/MetricsPage";
import { WarningsPage } from "@/dashboard/pages/WarningsPage";
import { ReplayPage } from "@/dashboard/pages/ReplayPage";
import { renderWithProviders } from "@/test/render";

function TestRoutes({ initialPath }: { initialPath: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<DashboardShell />}>
          <Route path={ROUTES.timeline} element={<TimelinePage />} />
          <Route path={ROUTES.metrics} element={<MetricsPage />} />
          <Route path={ROUTES.warnings} element={<WarningsPage />} />
          <Route path={ROUTES.replay} element={<ReplayPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("Routing", () => {
  it("exposes a stable canonical route table", () => {
    expect(ROUTES.overview).toBe("/");
    expect(ROUTES.timeline).toBe("/timeline");
    expect(ROUTES.diagnostics).toBe("/diagnostics");
  });

  it("declares every navigable route in NAVIGABLE_ROUTES", () => {
    const paths = NAVIGABLE_ROUTES.map((r) => r.path);
    expect(paths).toContain(ROUTES.overview);
    expect(paths).toContain(ROUTES.timeline);
    expect(paths).toContain(ROUTES.metrics);
    expect(paths).toContain(ROUTES.warnings);
    expect(paths).toContain(ROUTES.replay);
    expect(paths).toContain(ROUTES.diagnostics);
  });

  it("renders the TimelinePage when navigating to /timeline", () => {
    renderWithProviders(<TestRoutes initialPath={ROUTES.timeline} />);
    // The timeline route now mounts the canvas-backed container.
    expect(screen.getByRole("img", { name: /Timeline canvas/i })).toBeInTheDocument();
  });

  it("renders the MetricsPage when navigating to /metrics", () => {
    renderWithProviders(<TestRoutes initialPath={ROUTES.metrics} />);
    expect(screen.getByText(/Aggregate runtime metrics/i)).toBeInTheDocument();
  });

  it("renders the WarningsPage when navigating to /warnings", () => {
    renderWithProviders(<TestRoutes initialPath={ROUTES.warnings} />);
    expect(
      screen.getByRole("heading", { name: /Blocking Warnings/i }),
    ).toBeInTheDocument();
  });

  it("renders the ReplayPage when navigating to /replay", () => {
    renderWithProviders(<TestRoutes initialPath={ROUTES.replay} />);
    expect(screen.getByText(/Replay buffer inspection/i)).toBeInTheDocument();
  });
});
