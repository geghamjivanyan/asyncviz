/**
 * Classify a task as framework infrastructure.
 *
 * AsyncViz instruments **every** asyncio task — including the
 * Starlette / Uvicorn / FastAPI / ASGI plumbing that the dashboard
 * itself runs on top of. That's the right behavior at the wire level
 * (we never want to silently drop instrumentation), but on a fresh
 * dashboard page those infrastructure tasks easily outnumber the
 * user's own tasks 10:1 and bury the very thing the operator is
 * trying to inspect.
 *
 * The Tasks table hides framework rows by default through a small
 * filter; the toolbar exposes a "Framework" toggle to bring them
 * back. This classifier is the pure, central rule that drives both.
 *
 * Match against the **coroutine name** + **task name**. Both come
 * straight from the runtime snapshot. The list of prefixes is
 * intentionally conservative — we only match families that ship as
 * part of the runtime (Starlette/Uvicorn/FastAPI/ASGI/AnyIO/h11/
 * httptools/watchfiles) plus AsyncViz's own bookkeeping coroutines
 * (``asyncviz-*`` / ``_*_loop`` from the internal services).
 */

/** Prefixes that identify framework-infrastructure tasks. Matched
 *  case-sensitively against either ``coroutine_name`` or ``task_name``. */
const FRAMEWORK_NAME_PREFIXES: readonly string[] = [
  "starlette.",
  "uvicorn.",
  "fastapi.",
  "anyio.",
  "asgi.",
  "h11.",
  "httptools.",
  "watchfiles.",
];

/** Substrings inside the coroutine name that indicate framework code. */
const FRAMEWORK_NAME_SUBSTRINGS: readonly string[] = [
  "BaseHTTPMiddleware",
  "ServerErrorMiddleware",
  "ExceptionMiddleware",
  "AuthenticationMiddleware",
  "CORSMiddleware",
  "TrustedHostMiddleware",
];

/** Prefixes that identify AsyncViz's own internal bookkeeping tasks. */
const ASYNCVIZ_INTERNAL_PREFIXES: readonly string[] = ["asyncviz-", "asyncviz."];

/**
 * Pure: return ``true`` when the inputs name a framework / runtime
 * infrastructure task that the operator did not author themselves.
 *
 * Designed to be cheap (O(prefixes × small)) so the projection layer
 * can call it for every task on every reconciliation.
 */
export function isFrameworkTask(inputs: {
  readonly coroutineName: string | null;
  readonly taskName: string | null;
}): boolean {
  const candidates = [inputs.coroutineName, inputs.taskName];
  for (const candidate of candidates) {
    if (candidate === null || candidate === "") continue;
    for (const prefix of FRAMEWORK_NAME_PREFIXES) {
      if (candidate.startsWith(prefix)) return true;
    }
    for (const prefix of ASYNCVIZ_INTERNAL_PREFIXES) {
      if (candidate.startsWith(prefix)) return true;
    }
    for (const sub of FRAMEWORK_NAME_SUBSTRINGS) {
      if (candidate.includes(sub)) return true;
    }
  }
  return false;
}
