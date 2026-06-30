/**
 * Canonical frontend configuration surface.
 *
 * The config is built once at bootstrap and consumed via
 * ``ConfigProvider``. Every value has an env override + a deterministic
 * default so the dev server, embedded build, and CI all hit the same
 * code paths.
 *
 * No file outside ``app/configuration/`` reads ``import.meta.env``
 * directly — that keeps environment surface area in one place and
 * makes tests trivial (just construct a fresh ``RuntimeConfig``).
 *
 * Runtime endpoint resolution (API + WebSocket) is environment-aware:
 *
 *   * **Embedded production** — the SPA is served by FastAPI on the
 *     backend's own origin. API requests go to ``""`` (same-origin
 *     relative URLs) and the websocket URL is derived from
 *     ``window.location`` so HTTPS deployments automatically get
 *     ``wss://``.
 *   * **Vite standalone dev** — the SPA is served by Vite on a
 *     different origin (``:5173``) from the backend (``:8000`` by
 *     default). API + websocket requests target the backend origin
 *     directly. Operators can override via ``VITE_API_BASE_URL`` /
 *     ``VITE_WS_BASE_URL`` for non-default ports or remote hosts.
 *
 * Tests should construct a :func:`createTestConfig` rather than rely
 * on the env-driven loader.
 */

/** Default dev-mode backend HTTP origin. Matches Vite proxy default. */
export const DEV_DEFAULT_API_BASE_URL = "http://localhost:8000";

/** Default dev-mode backend websocket URL. */
export const DEV_DEFAULT_WS_URL = "ws://localhost:8000/ws";

/** Websocket path used by the backend's ``websocket_router``. */
export const WS_PATH = "/ws";

export interface RuntimeConfig {
  /**
   * Base URL for REST calls.
   *
   *   * ``""`` (empty) — same-origin relative URLs. Used when the SPA
   *     is embedded inside the backend's FastAPI app.
   *   * ``"http://host:port"`` — absolute cross-origin URL. Used in
   *     Vite dev mode (default ``http://localhost:8000``) or any
   *     deployment where the SPA and backend live on different
   *     origins.
   *
   * Always returned without a trailing slash so consumers can build
   * paths with simple template literals (``${apiBaseUrl}/api/...``).
   */
  apiBaseUrl: string;
  /**
   * Absolute websocket URL (``ws://`` or ``wss://`` with ``/ws``
   * path). The browser's ``WebSocket`` constructor rejects relative
   * URLs, so this is always absolute — either derived from
   * ``window.location`` in embedded mode or pinned to the dev
   * backend in standalone mode.
   */
  websocketUrl: string;
  /** Protocol version the frontend expects on websocket envelopes. */
  protocolVersion: string;
  /** Whether to show in-app diagnostics surfaces (frontend perf + websocket counters). */
  enableDiagnostics: boolean;
  /** Whether to show developer-only routes. */
  enableDevRoutes: boolean;
  /** Runtime build metadata for the about/diagnostics panel. */
  buildVersion: string;
}

/**
 * Minimal shape of ``import.meta.env`` that the loader cares about.
 *
 * Defined separately from the Vite-generated ``ImportMetaEnv`` so the
 * helpers can be unit-tested by passing a plain object without
 * touching ``import.meta``.
 */
export interface RuntimeEnv {
  /** Vite's canonical dev-mode flag. ``true`` during ``vite dev``. */
  DEV?: boolean;
  PROD?: boolean;
  MODE?: string;
  /** Canonical override — backend HTTP origin (e.g. ``http://localhost:8000``). */
  VITE_API_BASE_URL?: string;
  /** Canonical override — backend websocket URL (e.g. ``ws://localhost:8000/ws``). */
  VITE_WS_BASE_URL?: string;
  /** Legacy aliases — kept so downstream ``.env`` files don't churn. */
  VITE_RUNTIME_API_URL?: string;
  VITE_RUNTIME_WS_URL?: string;
  VITE_PROTOCOL_VERSION?: string;
  VITE_ENABLE_DIAGNOSTICS?: string;
  VITE_ENABLE_DEV_ROUTES?: string;
  VITE_BUILD_VERSION?: string;
  [key: string]: unknown;
}

/**
 * Browser-API surface the websocket-URL derivation needs. Modeled as
 * an interface so tests can pass a plain object instead of mutating
 * the jsdom ``window``.
 */
export interface BrowserLocationLike {
  protocol: string;
  host: string;
}

/**
 * Sentinel meaning "no value supplied — explicitly absent". Lets
 * tests pass ``null`` to assert behavior when ``import.meta.env`` is
 * unreachable or ``window.location`` is missing, without colliding
 * with TypeScript's default-parameter semantics (where passing
 * ``undefined`` would trigger the default).
 */
type Maybe<T> = T | null | undefined;

/**
 * Detect Vite standalone dev mode.
 *
 * The canonical signal is ``import.meta.env.DEV``, which Vite sets to
 * ``true`` during ``vite dev`` and ``false`` for production builds.
 * The flag is also ``true`` under Vitest (its env is built on top of
 * Vite), which is fine — tests construct their config explicitly via
 * :func:`createTestConfig` rather than going through the loader.
 *
 * Pass an explicit ``RuntimeEnv`` (including ``{}`` for "no env") to
 * bypass the ``import.meta.env`` read. ``null`` is treated as "no
 * env at all"; omitting the argument reads the ambient env.
 */
export function isDevelopmentMode(env?: Maybe<RuntimeEnv>): boolean {
  const effective = resolveEnv(env);
  return effective?.DEV === true;
}

/**
 * Resolve the API base URL for the current environment.
 *
 * Resolution order:
 *
 *   1. Explicit override — ``VITE_API_BASE_URL`` (canonical) or the
 *      legacy ``VITE_RUNTIME_API_URL``.
 *   2. Dev-mode default — ``"http://localhost:8000"``.
 *   3. Embedded default — ``""`` (same-origin relative).
 *
 * Always returned without a trailing slash. Pass ``null`` for ``env``
 * to assert "no env available" behavior in tests.
 */
export function getApiBaseUrl(env?: Maybe<RuntimeEnv>): string {
  const effective = resolveEnv(env);
  const override =
    readEnvString(effective?.VITE_API_BASE_URL) ?? readEnvString(effective?.VITE_RUNTIME_API_URL);
  if (override !== undefined) {
    return stripTrailingSlash(override);
  }
  if (isDevelopmentMode(effective ?? null)) {
    return DEV_DEFAULT_API_BASE_URL;
  }
  return "";
}

/**
 * Resolve the WebSocket URL for the current environment.
 *
 * Resolution order:
 *
 *   1. Explicit override — ``VITE_WS_BASE_URL`` (canonical) or
 *      ``VITE_RUNTIME_WS_URL`` (legacy). If the override is an HTTP
 *      origin (``http://`` / ``https://``), it is upgraded to
 *      ``ws://`` / ``wss://`` automatically; if it lacks a ``/ws``
 *      suffix, one is appended.
 *   2. Dev-mode default — ``"ws://localhost:8000/ws"``.
 *   3. Embedded default — derived from ``window.location`` so HTTPS
 *      origins automatically pick ``wss://`` and any port on the
 *      backend's origin is preserved.
 *
 * If ``window`` is unavailable and no override is set (Node, SSR),
 * falls back to the dev default so callers never receive an empty
 * string (which the browser's ``WebSocket`` constructor would reject).
 *
 * Pass ``null`` for ``env`` or ``location`` to assert the
 * "no env" / "no window" branches in tests without depending on the
 * ambient ``import.meta.env`` or jsdom's ``window.location``.
 */
export function getWebSocketUrl(
  env?: Maybe<RuntimeEnv>,
  location?: Maybe<BrowserLocationLike>,
): string {
  const effectiveEnv = resolveEnv(env);
  const override =
    readEnvString(effectiveEnv?.VITE_WS_BASE_URL) ??
    readEnvString(effectiveEnv?.VITE_RUNTIME_WS_URL);
  if (override !== undefined) {
    return normalizeWebSocketUrl(override);
  }
  if (isDevelopmentMode(effectiveEnv ?? null)) {
    return DEV_DEFAULT_WS_URL;
  }
  const effectiveLocation = resolveLocation(location);
  if (effectiveLocation !== undefined) {
    return deriveSameOriginWebSocketUrl(effectiveLocation);
  }
  return DEV_DEFAULT_WS_URL;
}

/**
 * Resolve config from ``import.meta.env`` + sensible defaults.
 *
 * Splitting this out keeps the env-touching code small and easy to
 * mock — Vitest tests construct a fresh ``RuntimeConfig`` via
 * :func:`createTestConfig` without touching ``import.meta``.
 */
export function loadRuntimeConfig(): RuntimeConfig {
  const env = readImportMetaEnv();
  return {
    apiBaseUrl: getApiBaseUrl(env),
    websocketUrl: getWebSocketUrl(env),
    protocolVersion: readEnvString(env?.VITE_PROTOCOL_VERSION) ?? "1.0",
    enableDiagnostics: parseBool(env?.VITE_ENABLE_DIAGNOSTICS, true),
    enableDevRoutes: parseBool(env?.VITE_ENABLE_DEV_ROUTES, false),
    buildVersion: readEnvString(env?.VITE_BUILD_VERSION) ?? "dev",
  };
}

/** Test-only helper. Produces a config with overrides on top of the defaults. */
export function createTestConfig(overrides: Partial<RuntimeConfig> = {}): RuntimeConfig {
  return {
    apiBaseUrl: "",
    websocketUrl: DEV_DEFAULT_WS_URL,
    protocolVersion: "1.0",
    enableDiagnostics: true,
    enableDevRoutes: false,
    buildVersion: "test",
    ...overrides,
  };
}

// ── Internal helpers ──────────────────────────────────────────────────────

/**
 * Map the caller's ``Maybe<RuntimeEnv>`` to a concrete env or
 * ``undefined``. ``undefined`` (no argument) → ambient
 * ``import.meta.env``; explicit ``null`` → "no env available".
 */
function resolveEnv(env: Maybe<RuntimeEnv>): RuntimeEnv | undefined {
  if (env === null) return undefined;
  if (env === undefined) return readImportMetaEnv();
  return env;
}

function resolveLocation(location: Maybe<BrowserLocationLike>): BrowserLocationLike | undefined {
  if (location === null) return undefined;
  if (location === undefined) return readBrowserLocation();
  return location;
}

function readImportMetaEnv(): RuntimeEnv | undefined {
  // ``import.meta.env`` is replaced at build time by Vite. Guarded for
  // Node / SSR contexts where ``import.meta`` lacks ``env``.
  try {
    return (import.meta.env as RuntimeEnv | undefined) ?? undefined;
  } catch {
    return undefined;
  }
}

function readBrowserLocation(): BrowserLocationLike | undefined {
  if (typeof window === "undefined" || window.location === undefined) {
    return undefined;
  }
  const { protocol, host } = window.location;
  if (typeof protocol !== "string" || typeof host !== "string" || host === "") {
    return undefined;
  }
  return { protocol, host };
}

function readEnvString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function deriveSameOriginWebSocketUrl(location: BrowserLocationLike): string {
  const wsProtocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${location.host}${WS_PATH}`;
}

/**
 * Coerce an arbitrary override into a canonical ``ws://`` URL ending
 * in ``/ws``.
 *
 *   * ``http://host:port`` → ``ws://host:port/ws``
 *   * ``https://host`` → ``wss://host/ws``
 *   * ``ws://host:port`` → ``ws://host:port/ws``
 *   * ``ws://host:port/ws`` → ``ws://host:port/ws`` (idempotent)
 *   * ``ws://host:port/custom`` → ``ws://host:port/custom`` (respected)
 */
function normalizeWebSocketUrl(raw: string): string {
  let url = raw.trim();
  if (/^https?:/i.test(url)) {
    url = url.replace(/^http/i, "ws");
  }
  // Strip the trailing slash before deciding whether a path was supplied
  // so ``ws://host/`` doesn't read as "has a path".
  const trimmed = stripTrailingSlash(url);
  // Look at what's after the host. If only the origin was given, append
  // the canonical ``/ws`` path.
  const schemeMatch = trimmed.match(/^(wss?:\/\/)([^/]+)(\/.*)?$/i);
  if (schemeMatch === null) {
    // Not a recognized absolute URL — return unchanged so the caller
    // (or the browser's WebSocket constructor) surfaces the error.
    return trimmed;
  }
  const [, scheme, host, pathPart] = schemeMatch;
  if (pathPart === undefined || pathPart === "") {
    return `${scheme}${host}${WS_PATH}`;
  }
  return `${scheme}${host}${pathPart}`;
}

function parseBool(value: unknown, fallback: boolean): boolean {
  if (typeof value !== "string") return fallback;
  const normalized = value.toLowerCase().trim();
  if (normalized === "true" || normalized === "1" || normalized === "yes") return true;
  if (normalized === "false" || normalized === "0" || normalized === "no") return false;
  return fallback;
}
