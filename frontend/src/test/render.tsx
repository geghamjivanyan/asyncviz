/**
 * Test render utility.
 *
 * Wraps :func:`render` with the canonical provider stack so tests can
 * mount real components against real providers (typed config,
 * websocket stubs) without the routing layer.
 *
 * Use :func:`renderWithProviders` for component tests; use
 * :func:`renderWithRouter` for tests that exercise router-aware
 * components (NavLink, ``useLocation``).
 */

import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import type { RenderOptions, RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProviders } from "@/app/providers/AppProviders";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import type { RuntimeConfig } from "@/app/configuration/runtimeConfig";

export interface ProviderRenderOptions extends Omit<RenderOptions, "wrapper"> {
  config?: Partial<RuntimeConfig>;
}

export function renderWithProviders(
  ui: ReactNode,
  options: ProviderRenderOptions = {},
): RenderResult {
  const { config: configOverrides, ...rest } = options;
  const config = createTestConfig(configOverrides);
  return render(<AppProviders config={config}>{ui}</AppProviders>, rest);
}

export interface RouterRenderOptions extends ProviderRenderOptions {
  initialEntries?: string[];
}

export function renderWithRouter(ui: ReactNode, options: RouterRenderOptions = {}): RenderResult {
  const { initialEntries = ["/"], config, ...rest } = options;
  return renderWithProviders(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>, {
    config,
    ...rest,
  });
}
