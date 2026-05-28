/**
 * Layout-state primitives.
 *
 * Kept out of the context module so the shape can be imported by tests
 * and reducer helpers without round-tripping through React.
 *
 * The state surface is intentionally narrow today — sidebar collapse +
 * fullscreen panel id. Future layout customizations (panel sizes,
 * persisted preferences) plug in here without touching the components
 * that consume the state.
 */

/** Panel that is currently maximized to cover the whole content area. */
export type FullscreenPanelId = string | null;

/** Sidebar visibility. ``collapsed`` collapses to an icon strip later. */
export type SidebarMode = "expanded" | "collapsed" | "hidden";

export interface DashboardLayoutState {
  sidebar: SidebarMode;
  fullscreenPanel: FullscreenPanelId;
  /** Whether the runtime status bar at the bottom is visible. */
  statusBarVisible: boolean;
  /** Whether the diagnostics drawer/panel is requested by the user. */
  diagnosticsVisible: boolean;
}

export const DEFAULT_LAYOUT_STATE: DashboardLayoutState = {
  sidebar: "expanded",
  fullscreenPanel: null,
  statusBarVisible: true,
  diagnosticsVisible: false,
};
