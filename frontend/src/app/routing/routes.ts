/**
 * Canonical route table.
 *
 * One place to add / rename / reorder routes. Components consume the
 * paths as constants (``ROUTES.timeline``) so a refactor of the URL
 * structure is a single-file change. The matching React Router
 * configuration lives in :class:`AppRouter`.
 */

export const ROUTES = {
  overview: "/",
  timeline: "/timeline",
  metrics: "/metrics",
  warnings: "/warnings",
  queues: "/queues",
  semaphores: "/semaphores",
  dependencies: "/dependencies",
  executors: "/executors",
  replay: "/replay",
  diagnostics: "/diagnostics",
} as const;

export interface RouteDefinition {
  path: (typeof ROUTES)[keyof typeof ROUTES];
  label: string;
  description: string;
}

/**
 * Ordered route list — drives the sidebar / topbar navigation.
 * ``description`` is for the page placeholder + future tooltips.
 */
export const NAVIGABLE_ROUTES: readonly RouteDefinition[] = [
  { path: ROUTES.overview, label: "Overview", description: "Realtime runtime overview" },
  { path: ROUTES.timeline, label: "Timeline", description: "Task lifecycle timeline" },
  { path: ROUTES.metrics, label: "Metrics", description: "Aggregate runtime metrics" },
  { path: ROUTES.warnings, label: "Warnings", description: "Active runtime warnings" },
  { path: ROUTES.queues, label: "Queues", description: "asyncio.Queue pressure + throughput" },
  { path: ROUTES.semaphores, label: "Semaphores", description: "asyncio.Semaphore contention + permits" },
  { path: ROUTES.dependencies, label: "Dependencies", description: "asyncio.gather await topology" },
  { path: ROUTES.executors, label: "Executors", description: "run_in_executor activity + utilization" },
  { path: ROUTES.replay, label: "Replay", description: "Replay buffer + checkpoints" },
  { path: ROUTES.diagnostics, label: "Diagnostics", description: "Backend + frontend diagnostics" },
] as const;
