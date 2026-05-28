/**
 * Public surface of the canonical dashboard layout system.
 *
 * Consumers import primitives from this barrel — keeps the import
 * paths short and decouples them from the package's internal file
 * layout.
 */

export { DashboardLayout } from "@/dashboard/layout/DashboardLayout";
export type { DashboardLayoutProps } from "@/dashboard/layout/DashboardLayout";
export { DashboardGrid } from "@/dashboard/layout/DashboardGrid";
export type { DashboardGridProps } from "@/dashboard/layout/DashboardGrid";
export { DashboardHeader } from "@/dashboard/layout/DashboardHeader";
export type { DashboardHeaderProps } from "@/dashboard/layout/DashboardHeader";
export { DashboardSidebar } from "@/dashboard/layout/DashboardSidebar";
export type { DashboardSidebarProps } from "@/dashboard/layout/DashboardSidebar";
export { DashboardContent } from "@/dashboard/layout/DashboardContent";
export type { DashboardContentProps } from "@/dashboard/layout/DashboardContent";
export { DashboardStatusBar } from "@/dashboard/layout/DashboardStatusBar";
export type { DashboardStatusBarProps } from "@/dashboard/layout/DashboardStatusBar";
export { DashboardRegion } from "@/dashboard/layout/DashboardRegion";
export type { DashboardRegionProps, RegionScroll } from "@/dashboard/layout/DashboardRegion";
export {
  DashboardPanel,
  PanelHeader,
  PanelBody,
  PanelToolbar,
  PanelStatusBadge,
} from "@/dashboard/layout/DashboardPanel";
export type {
  DashboardPanelProps,
  PanelHeaderProps,
  PanelBodyProps,
  PanelToolbarProps,
  PanelStatusBadgeProps,
} from "@/dashboard/layout/DashboardPanel";
export { DashboardSplitView } from "@/dashboard/layout/DashboardSplitView";
export type {
  DashboardSplitViewProps,
  DashboardSplitPaneProps,
  PaneSize,
  SplitOrientation,
} from "@/dashboard/layout/DashboardSplitView";
export {
  DashboardLayoutProvider,
  useDashboardLayout,
} from "@/dashboard/layout/context/DashboardLayoutContext";
export type {
  DashboardLayoutContextValue,
  DashboardLayoutProviderProps,
} from "@/dashboard/layout/context/DashboardLayoutContext";
export {
  DEFAULT_LAYOUT_STATE,
  type DashboardLayoutState,
  type FullscreenPanelId,
  type SidebarMode,
} from "@/dashboard/layout/models/layoutState";
export {
  DESKTOP_MEDIA_QUERY,
  TABLET_MEDIA_QUERY,
  useIsDesktop,
  useIsTablet,
  useMediaQuery,
} from "@/dashboard/layout/hooks/useMediaQuery";
export { useLayoutObservability } from "@/dashboard/layout/hooks/useLayoutObservability";
export { useNavigationObservability } from "@/dashboard/layout/hooks/useNavigationObservability";
