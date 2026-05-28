import { describe, expect, it } from "vitest";
import {
  DEV_DEFAULT_API_BASE_URL,
  DEV_DEFAULT_WS_URL,
  WS_PATH,
  createTestConfig,
  getApiBaseUrl,
  getWebSocketUrl,
  isDevelopmentMode,
} from "@/app/configuration/runtimeConfig";
import type { BrowserLocationLike, RuntimeEnv } from "@/app/configuration/runtimeConfig";

const DEV_ENV: RuntimeEnv = { DEV: true, PROD: false, MODE: "development" };
const PROD_ENV: RuntimeEnv = { DEV: false, PROD: true, MODE: "production" };

const SAME_ORIGIN_HTTP: BrowserLocationLike = {
  protocol: "http:",
  host: "asyncviz.example:8000",
};
const SAME_ORIGIN_HTTPS: BrowserLocationLike = {
  protocol: "https:",
  host: "asyncviz.example",
};

describe("isDevelopmentMode", () => {
  it("is true when Vite reports DEV=true", () => {
    expect(isDevelopmentMode(DEV_ENV)).toBe(true);
  });

  it("is false in a production build", () => {
    expect(isDevelopmentMode(PROD_ENV)).toBe(false);
  });

  it("is false when there is no env at all (SSR / Node)", () => {
    expect(isDevelopmentMode(null)).toBe(false);
  });

  it("does not treat DEV=undefined as dev", () => {
    expect(isDevelopmentMode({})).toBe(false);
  });
});

describe("getApiBaseUrl", () => {
  it("returns localhost:8000 in Vite dev mode by default", () => {
    expect(getApiBaseUrl(DEV_ENV)).toBe("http://localhost:8000");
    expect(getApiBaseUrl(DEV_ENV)).toBe(DEV_DEFAULT_API_BASE_URL);
  });

  it("returns empty string (same-origin) in embedded production", () => {
    expect(getApiBaseUrl(PROD_ENV)).toBe("");
  });

  it("respects VITE_API_BASE_URL overrides", () => {
    expect(
      getApiBaseUrl({ ...DEV_ENV, VITE_API_BASE_URL: "https://api.dev.example:9000" }),
    ).toBe("https://api.dev.example:9000");
    // Overrides also apply in prod builds (e.g. a static SPA hosted
    // on a CDN talking to an API on a different origin).
    expect(
      getApiBaseUrl({ ...PROD_ENV, VITE_API_BASE_URL: "https://api.example.com" }),
    ).toBe("https://api.example.com");
  });

  it("falls back to the legacy VITE_RUNTIME_API_URL alias", () => {
    expect(
      getApiBaseUrl({ ...DEV_ENV, VITE_RUNTIME_API_URL: "http://legacy.example:8000" }),
    ).toBe("http://legacy.example:8000");
  });

  it("prefers VITE_API_BASE_URL when both names are set", () => {
    expect(
      getApiBaseUrl({
        ...DEV_ENV,
        VITE_API_BASE_URL: "http://canonical.example:8000",
        VITE_RUNTIME_API_URL: "http://legacy.example:8000",
      }),
    ).toBe("http://canonical.example:8000");
  });

  it("strips trailing slashes so consumers can use simple template literals", () => {
    expect(
      getApiBaseUrl({ ...DEV_ENV, VITE_API_BASE_URL: "http://localhost:8000/" }),
    ).toBe("http://localhost:8000");
    expect(
      getApiBaseUrl({ ...DEV_ENV, VITE_API_BASE_URL: "http://localhost:8000///" }),
    ).toBe("http://localhost:8000");
  });

  it("treats empty / whitespace overrides as unset", () => {
    expect(getApiBaseUrl({ ...DEV_ENV, VITE_API_BASE_URL: "" })).toBe(
      DEV_DEFAULT_API_BASE_URL,
    );
    expect(getApiBaseUrl({ ...DEV_ENV, VITE_API_BASE_URL: "   " })).toBe(
      DEV_DEFAULT_API_BASE_URL,
    );
  });

  it("falls back to embedded same-origin when there is no env at all", () => {
    expect(getApiBaseUrl(null)).toBe("");
  });
});

describe("getWebSocketUrl", () => {
  it("returns ws://localhost:8000/ws in Vite dev mode by default", () => {
    expect(getWebSocketUrl(DEV_ENV, null)).toBe("ws://localhost:8000/ws");
    expect(getWebSocketUrl(DEV_ENV, null)).toBe(DEV_DEFAULT_WS_URL);
  });

  it("derives same-origin ws:// in embedded production over http", () => {
    expect(getWebSocketUrl(PROD_ENV, SAME_ORIGIN_HTTP)).toBe(
      "ws://asyncviz.example:8000/ws",
    );
  });

  it("derives same-origin wss:// in embedded production over https", () => {
    expect(getWebSocketUrl(PROD_ENV, SAME_ORIGIN_HTTPS)).toBe(
      "wss://asyncviz.example/ws",
    );
  });

  it("respects VITE_WS_BASE_URL overrides", () => {
    expect(
      getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "ws://other.host:9000/ws" }, null),
    ).toBe("ws://other.host:9000/ws");
  });

  it("upgrades http(s) override schemes to ws(s)", () => {
    expect(
      getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "http://other.host:9000" }, undefined),
    ).toBe("ws://other.host:9000/ws");
    expect(
      getWebSocketUrl({ ...PROD_ENV, VITE_WS_BASE_URL: "https://api.example.com" }, undefined),
    ).toBe("wss://api.example.com/ws");
  });

  it("appends /ws when the override omits the path", () => {
    expect(
      getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "ws://localhost:8000" }, undefined),
    ).toBe("ws://localhost:8000/ws");
    expect(
      getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "ws://localhost:8000/" }, undefined),
    ).toBe("ws://localhost:8000/ws");
  });

  it("preserves an explicit non-/ws path in the override", () => {
    expect(
      getWebSocketUrl(
        { ...DEV_ENV, VITE_WS_BASE_URL: "ws://localhost:8000/custom-stream" },
        undefined,
      ),
    ).toBe("ws://localhost:8000/custom-stream");
  });

  it("is idempotent on a fully-formed override", () => {
    const fully = "wss://api.example.com:443/ws";
    expect(getWebSocketUrl({ ...PROD_ENV, VITE_WS_BASE_URL: fully }, undefined)).toBe(fully);
  });

  it("falls back to the legacy VITE_RUNTIME_WS_URL alias", () => {
    expect(
      getWebSocketUrl(
        { ...DEV_ENV, VITE_RUNTIME_WS_URL: "ws://legacy.example/ws" },
        undefined,
      ),
    ).toBe("ws://legacy.example/ws");
  });

  it("prefers VITE_WS_BASE_URL when both names are set", () => {
    expect(
      getWebSocketUrl(
        {
          ...DEV_ENV,
          VITE_WS_BASE_URL: "ws://canonical.example/ws",
          VITE_RUNTIME_WS_URL: "ws://legacy.example/ws",
        },
        undefined,
      ),
    ).toBe("ws://canonical.example/ws");
  });

  it("treats empty / whitespace overrides as unset", () => {
    expect(getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "" }, undefined)).toBe(
      DEV_DEFAULT_WS_URL,
    );
    expect(getWebSocketUrl({ ...DEV_ENV, VITE_WS_BASE_URL: "   " }, undefined)).toBe(
      DEV_DEFAULT_WS_URL,
    );
  });

  it("falls back to the dev default when no location is available in prod", () => {
    // SSR / headless context with no window.location and no env override.
    expect(getWebSocketUrl(PROD_ENV, null)).toBe(DEV_DEFAULT_WS_URL);
  });

  it("never returns an empty string — the browser WebSocket ctor would reject it", () => {
    expect(getWebSocketUrl(DEV_ENV, null)).not.toBe("");
    expect(getWebSocketUrl(PROD_ENV, SAME_ORIGIN_HTTP)).not.toBe("");
    expect(getWebSocketUrl(undefined, undefined)).not.toBe("");
  });

  it("always produces a ws:// or wss:// URL with a path", () => {
    const cases: Array<{ env: RuntimeEnv; location?: BrowserLocationLike }> = [
      { env: DEV_ENV },
      { env: PROD_ENV, location: SAME_ORIGIN_HTTP },
      { env: PROD_ENV, location: SAME_ORIGIN_HTTPS },
      { env: { ...PROD_ENV, VITE_WS_BASE_URL: "https://api.example.com" } },
      { env: { ...DEV_ENV, VITE_WS_BASE_URL: "http://localhost:9000" } },
    ];
    for (const { env, location } of cases) {
      const url = getWebSocketUrl(env, location);
      expect(url).toMatch(/^wss?:\/\/.+\/.+/);
    }
  });
});

describe("WS_PATH", () => {
  it("matches the backend websocket route", () => {
    // Lock the constant — the backend's ``websocket_router`` mounts
    // its single route at ``/ws``. Drift here would silently break
    // every dev-mode reconnect.
    expect(WS_PATH).toBe("/ws");
  });
});

describe("createTestConfig", () => {
  it("returns deterministic defaults when no overrides are passed", () => {
    const config = createTestConfig();
    expect(config.protocolVersion).toBe("1.0");
    expect(config.enableDiagnostics).toBe(true);
    expect(config.enableDevRoutes).toBe(false);
    expect(config.buildVersion).toBe("test");
    expect(config.websocketUrl).toContain("ws://");
  });

  it("merges overrides on top of the defaults", () => {
    const config = createTestConfig({
      apiBaseUrl: "https://api.example",
      enableDevRoutes: true,
    });
    expect(config.apiBaseUrl).toBe("https://api.example");
    expect(config.enableDevRoutes).toBe(true);
    // Other fields fall back to defaults.
    expect(config.protocolVersion).toBe("1.0");
  });
});
