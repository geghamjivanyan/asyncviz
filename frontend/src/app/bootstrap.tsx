/**
 * Application bootstrap orchestrator.
 *
 * Single responsibility: assemble the provider stack + the router + the
 * top-level error boundary, return the resulting React tree. Everything
 * upstream (``main.tsx``) just mounts the result; everything downstream
 * (the router + pages) consumes the providers via hooks.
 *
 * Tests use :func:`renderApplication` with a custom config to bypass
 * ``import.meta.env`` and stub the websocket client.
 */

import type { ReactNode } from "react";
import { AppProviders } from "@/app/providers/AppProviders";
import { AppErrorBoundary } from "@/app/error/AppErrorBoundary";
import { AppRouter } from "@/app/routing/AppRouter";
import { loadRuntimeConfig } from "@/app/configuration/runtimeConfig";
import type { RuntimeConfig } from "@/app/configuration/runtimeConfig";

export interface BootstrapApplicationOptions {
  /** Test override — bypass ``import.meta.env`` resolution. */
  config?: RuntimeConfig;
  /** Override the router. Tests use :class:`MemoryRouter` instead. */
  router?: ReactNode;
}

/**
 * Build the canonical React tree.
 *
 * Returns the JSX so callers can mount it however they want — the
 * production entrypoint hands it to ``createRoot``; tests hand it to
 * :func:`render` from ``@testing-library/react``.
 */
export function bootstrapApplication(options: BootstrapApplicationOptions = {}): ReactNode {
  const config = options.config ?? loadRuntimeConfig();
  const inner = options.router ?? <AppRouter />;
  return (
    <AppErrorBoundary>
      <AppProviders config={config}>{inner}</AppProviders>
    </AppErrorBoundary>
  );
}
