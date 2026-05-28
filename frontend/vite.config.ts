import path from "node:path";
import process from "node:process";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Backend origin used by the Vite dev-server proxy.
 *
 * Precedence:
 *   1. ``VITE_API_BASE_URL`` — canonical name shared with the runtime
 *      endpoint helpers (``frontend/src/app/configuration/runtimeConfig.ts``).
 *   2. ``BACKEND_URL`` — legacy env name still honored so existing
 *      dev workflows keep working.
 *   3. ``http://localhost:8000`` — matches the documented default
 *      backend port and the dev-mode default the frontend resolves to
 *      when no override is supplied.
 *
 * The websocket proxy target is derived by swapping ``http``/``https``
 * for ``ws``/``wss``.
 */
const BACKEND_HTTP =
  process.env.VITE_API_BASE_URL ?? process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_WS = BACKEND_HTTP.replace(/^http/i, "ws");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    watch: {
      usePolling: process.env.CHOKIDAR_USEPOLLING === "true",
    },
    // The proxy is a belt-and-suspenders convenience for operators
    // who prefer same-origin requests in dev. The frontend runtime
    // also resolves the backend origin directly via
    // ``getApiBaseUrl()`` / ``getWebSocketUrl()`` so the SPA works
    // either way.
    proxy: {
      "/api": {
        target: BACKEND_HTTP,
        changeOrigin: true,
      },
      "/ws": {
        target: BACKEND_WS,
        ws: true,
      },
    },
  },
});
