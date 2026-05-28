/**
 * End-to-end bootstrap smoke tests.
 *
 * Confirms that :func:`bootstrapApplication` produces a renderable
 * tree even with the production router swapped for a memory one, and
 * that the default config flows all the way through the providers
 * onto the dashboard shell.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { bootstrapApplication } from "@/app/bootstrap";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import { DashboardShell } from "@/app/layout/DashboardShell";
import { ROUTES } from "@/app/routing/routes";
import { DiagnosticsPage } from "@/dashboard/pages/DiagnosticsPage";

describe("bootstrapApplication", () => {
  it("produces a tree that renders without throwing", () => {
    const tree = bootstrapApplication({
      config: createTestConfig(),
      router: (
        <MemoryRouter initialEntries={[ROUTES.diagnostics]}>
          <Routes>
            <Route element={<DashboardShell />}>
              <Route path={ROUTES.diagnostics} element={<DiagnosticsPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      ),
    });
    render(<>{tree}</>);
    // The diagnostics page renders the env-bound websocket URL.
    expect(screen.getByText(/ws:\/\//i)).toBeInTheDocument();
  });

  it("flows the provided config through every consumer", () => {
    const tree = bootstrapApplication({
      config: createTestConfig({ buildVersion: "test-1.2.3" }),
      router: (
        <MemoryRouter initialEntries={[ROUTES.diagnostics]}>
          <Routes>
            <Route element={<DashboardShell />}>
              <Route path={ROUTES.diagnostics} element={<DiagnosticsPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      ),
    });
    render(<>{tree}</>);
    expect(screen.getByText(/test-1\.2\.3/)).toBeInTheDocument();
  });
});
