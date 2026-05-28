/**
 * Single composition root for application-wide providers.
 *
 * Order matters:
 *
 * 1. :class:`ConfigProvider` — everything below reads from
 *    :func:`useRuntimeConfig`.
 * 2. :class:`ThemeProvider` — establishes the ``data-theme`` attribute
 *    before any rendered UI computes class names.
 * 3. :class:`RuntimeProvider` — needs the config + the theme bound to
 *    the document so its eager observability instrumentation reflects
 *    the right environment.
 *
 * Tests bypass this whole stack by importing the individual providers
 * directly with stub instances.
 */

import type { ReactNode } from "react";
import { ConfigProvider } from "@/app/providers/ConfigProvider";
import { RuntimeProvider } from "@/app/providers/RuntimeProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import type { RuntimeConfig } from "@/app/configuration/runtimeConfig";

export interface AppProvidersProps {
  config: RuntimeConfig;
  children: ReactNode;
}

export function AppProviders({ config, children }: AppProvidersProps) {
  return (
    <ConfigProvider config={config}>
      <ThemeProvider>
        <RuntimeProvider>{children}</RuntimeProvider>
      </ThemeProvider>
    </ConfigProvider>
  );
}
