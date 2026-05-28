/**
 * Provides per-instance layout state to every nested layout component.
 *
 * One :class:`DashboardLayoutProvider` per :class:`DashboardLayout`.
 * Tests render the provider directly with an initial state override to
 * exercise collapsed-sidebar / fullscreen-panel behavior without a
 * full router setup.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  DEFAULT_LAYOUT_STATE,
  type DashboardLayoutState,
  type FullscreenPanelId,
  type SidebarMode,
} from "@/dashboard/layout/models/layoutState";

export interface DashboardLayoutActions {
  setSidebar: (mode: SidebarMode) => void;
  toggleSidebar: () => void;
  setFullscreenPanel: (id: FullscreenPanelId) => void;
  setStatusBarVisible: (visible: boolean) => void;
  setDiagnosticsVisible: (visible: boolean) => void;
}

export interface DashboardLayoutContextValue extends DashboardLayoutState, DashboardLayoutActions {}

const DashboardLayoutContext = createContext<DashboardLayoutContextValue | null>(null);

export interface DashboardLayoutProviderProps {
  /** Initial layout state. Tests override to start collapsed / in fullscreen. */
  initialState?: Partial<DashboardLayoutState>;
  children: ReactNode;
}

export function DashboardLayoutProvider({ initialState, children }: DashboardLayoutProviderProps) {
  const [state, setState] = useState<DashboardLayoutState>(() => ({
    ...DEFAULT_LAYOUT_STATE,
    ...initialState,
  }));

  const setSidebar = useCallback((mode: SidebarMode) => {
    setState((prev) => (prev.sidebar === mode ? prev : { ...prev, sidebar: mode }));
  }, []);

  const toggleSidebar = useCallback(() => {
    setState((prev) => ({
      ...prev,
      sidebar: prev.sidebar === "expanded" ? "collapsed" : "expanded",
    }));
  }, []);

  const setFullscreenPanel = useCallback((id: FullscreenPanelId) => {
    setState((prev) => (prev.fullscreenPanel === id ? prev : { ...prev, fullscreenPanel: id }));
  }, []);

  const setStatusBarVisible = useCallback((visible: boolean) => {
    setState((prev) =>
      prev.statusBarVisible === visible ? prev : { ...prev, statusBarVisible: visible },
    );
  }, []);

  const setDiagnosticsVisible = useCallback((visible: boolean) => {
    setState((prev) =>
      prev.diagnosticsVisible === visible ? prev : { ...prev, diagnosticsVisible: visible },
    );
  }, []);

  const value = useMemo<DashboardLayoutContextValue>(
    () => ({
      ...state,
      setSidebar,
      toggleSidebar,
      setFullscreenPanel,
      setStatusBarVisible,
      setDiagnosticsVisible,
    }),
    [
      state,
      setSidebar,
      toggleSidebar,
      setFullscreenPanel,
      setStatusBarVisible,
      setDiagnosticsVisible,
    ],
  );

  return (
    <DashboardLayoutContext.Provider value={value}>{children}</DashboardLayoutContext.Provider>
  );
}

export function useDashboardLayout(): DashboardLayoutContextValue {
  const ctx = useContext(DashboardLayoutContext);
  if (ctx === null) {
    throw new Error(
      "useDashboardLayout must be used inside a <DashboardLayoutProvider>. Wrap your dashboard in <DashboardLayout>.",
    );
  }
  return ctx;
}
