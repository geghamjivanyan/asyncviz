/**
 * Browser router for the application.
 *
 * Routes are defined declaratively using the canonical :data:`ROUTES`
 * constants from ``routes.ts``. The router wraps every page in
 * :class:`DashboardShell`, which decides whether to render its own
 * header chrome based on the active path.
 *
 * The :func:`createBrowserRouter` call is wrapped in :func:`useMemo`
 * so the router instance is stable across re-renders without leaking
 * the eager-construction side effect into module load time (which
 * would break unit tests that mount a :class:`MemoryRouter` instead).
 */

import { useMemo } from "react";
import {
  Route,
  RouterProvider,
  createBrowserRouter,
  createRoutesFromElements,
} from "react-router-dom";
import { DashboardShell } from "@/app/layout/DashboardShell";
import { ROUTES } from "@/app/routing/routes";
import { OverviewPage } from "@/dashboard/pages/OverviewPage";
import { TimelinePage } from "@/dashboard/pages/TimelinePage";
import { MetricsPage } from "@/dashboard/pages/MetricsPage";
import { WarningsPage } from "@/dashboard/pages/WarningsPage";
import { QueuesPage } from "@/dashboard/pages/QueuesPage";
import { SemaphoresPage } from "@/dashboard/pages/SemaphoresPage";
import { DependenciesPage } from "@/dashboard/pages/DependenciesPage";
import { ExecutorsPage } from "@/dashboard/pages/ExecutorsPage";
import { ReplayPage } from "@/dashboard/pages/ReplayPage";
import { DiagnosticsPage } from "@/dashboard/pages/DiagnosticsPage";

export function AppRouter() {
  const router = useMemo(
    () =>
      createBrowserRouter(
        createRoutesFromElements(
          <Route element={<DashboardShell />}>
            <Route path={ROUTES.overview} element={<OverviewPage />} />
            <Route path={ROUTES.timeline} element={<TimelinePage />} />
            <Route path={ROUTES.metrics} element={<MetricsPage />} />
            <Route path={ROUTES.warnings} element={<WarningsPage />} />
            <Route path={ROUTES.queues} element={<QueuesPage />} />
            <Route path={ROUTES.semaphores} element={<SemaphoresPage />} />
            <Route path={ROUTES.dependencies} element={<DependenciesPage />} />
            <Route path={ROUTES.executors} element={<ExecutorsPage />} />
            <Route path={ROUTES.replay} element={<ReplayPage />} />
            <Route path={ROUTES.diagnostics} element={<DiagnosticsPage />} />
          </Route>,
        ),
      ),
    [],
  );
  return <RouterProvider router={router} />;
}
