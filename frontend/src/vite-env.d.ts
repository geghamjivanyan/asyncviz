/// <reference types="vite/client" />

/**
 * Typed surface for ``import.meta.env``.
 *
 * The runtime endpoint helpers in
 * ``src/app/configuration/runtimeConfig.ts`` are the only consumers
 * that read these directly — every other module reads the resolved
 * :class:`RuntimeConfig` from the ConfigProvider.
 */
interface ImportMetaEnv {
  /** Canonical backend HTTP origin override (e.g. ``http://localhost:8000``). */
  readonly VITE_API_BASE_URL?: string;
  /** Canonical backend websocket URL override (e.g. ``ws://localhost:8000/ws``). */
  readonly VITE_WS_BASE_URL?: string;
  /** Legacy alias for ``VITE_API_BASE_URL``. */
  readonly VITE_RUNTIME_API_URL?: string;
  /** Legacy alias for ``VITE_WS_BASE_URL``. */
  readonly VITE_RUNTIME_WS_URL?: string;
  readonly VITE_PROTOCOL_VERSION?: string;
  readonly VITE_ENABLE_DIAGNOSTICS?: string;
  readonly VITE_ENABLE_DEV_ROUTES?: string;
  readonly VITE_BUILD_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
