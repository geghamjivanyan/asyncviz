/**
 * Provides the :class:`RuntimeConfig` to every component below.
 *
 * Read via :func:`useRuntimeConfig`. Tests pass a custom config in
 * via the ``config`` prop — they never touch ``import.meta.env``.
 */

import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import type { RuntimeConfig } from "@/app/configuration/runtimeConfig";

const ConfigContext = createContext<RuntimeConfig | null>(null);

export interface ConfigProviderProps {
  config: RuntimeConfig;
  children: ReactNode;
}

export function ConfigProvider({ config, children }: ConfigProviderProps) {
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>;
}

export function useRuntimeConfig(): RuntimeConfig {
  const config = useContext(ConfigContext);
  if (config === null) {
    throw new Error(
      "useRuntimeConfig must be used inside a <ConfigProvider>. Wrap your app in <AppProviders>.",
    );
  }
  return config;
}
