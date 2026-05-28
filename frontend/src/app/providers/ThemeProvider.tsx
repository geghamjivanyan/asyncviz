/**
 * Sets the ``data-theme`` attribute on ``document.documentElement`` so
 * the Tailwind 4 ``@theme`` block can react to it.
 *
 * AsyncViz is dark-theme-first today; the provider exists so a future
 * light-theme toggle has a place to plug in without touching the rest
 * of the application.
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export interface ThemeProviderProps {
  defaultTheme?: Theme;
  children: ReactNode;
}

export function ThemeProvider({ defaultTheme = "dark", children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(defaultTheme);

  useEffect(() => {
    // ``documentElement`` is undefined in non-DOM test environments;
    // the JSDOM setup in ``test/setup.ts`` provides one for Vitest.
    if (typeof document !== "undefined" && document.documentElement) {
      document.documentElement.setAttribute("data-theme", theme);
    }
  }, [theme]);

  const value = useMemo<ThemeContextValue>(() => ({ theme, setTheme }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error(
      "useTheme must be used inside a <ThemeProvider>. Wrap your app in <AppProviders>.",
    );
  }
  return ctx;
}
