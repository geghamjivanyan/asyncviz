/**
 * Default landing page — live runtime overview.
 *
 * Composed on top of the canonical :class:`DashboardLayout`:
 *
 *   * The default route sidebar is replaced with the task tree.
 *   * The :class:`InspectorPanel` is injected as the ``aside`` slot,
 *     producing the three-pane layout the legacy dashboard had.
 *   * The body is a vertical split: the canonical live task table on
 *     top, the timeline panel in the middle, and the canonical
 *     :class:`RuntimeEventFeedContainer` on the bottom (the legacy
 *     ``EventPanel`` is now retired from the default route).
 *
 * The status bar + metrics header stay default — the runtime summary
 * is identical across every route.
 */

import { Sidebar } from "@/components/Sidebar";
import { InspectorPanel } from "@/components/panels/InspectorPanel";
import { TimelinePanel } from "@/components/panels/TimelinePanel";
import {
  DashboardLayout,
  DashboardPanel,
  DashboardSplitView,
  PanelBody,
  PanelHeader,
} from "@/dashboard/layout";
import { TaskTableContainer } from "@/dashboard/tasks";
import { RuntimeEventFeedContainer } from "@/dashboard/events";

export function OverviewPage() {
  return (
    <DashboardLayout
      sidebar={<Sidebar />}
      aside={
        <aside
          role="complementary"
          aria-label="Inspector"
          className="w-72 shrink-0 border-l border-line"
        >
          <InspectorPanel />
        </aside>
      }
    >
      <DashboardSplitView orientation="vertical" className="flex-1">
        <DashboardSplitView.Pane size="primary" className="border-b border-line">
          <DashboardSplitView orientation="vertical" className="h-full">
            <DashboardSplitView.Pane size="primary" className="border-b border-line">
              <DashboardPanel id="live-tasks">
                <PanelHeader title="Live tasks" />
                <PanelBody scroll="none">
                  <TaskTableContainer className="h-full" />
                </PanelBody>
              </DashboardPanel>
            </DashboardSplitView.Pane>
            <DashboardSplitView.Pane size="auxiliary" basis="14rem" minSize="9rem">
              <TimelinePanel />
            </DashboardSplitView.Pane>
          </DashboardSplitView>
        </DashboardSplitView.Pane>
        <DashboardSplitView.Pane size="auxiliary" basis="16rem" minSize="10rem">
          <DashboardPanel id="runtime-events">
            <PanelHeader title="Runtime events" />
            <PanelBody scroll="none">
              <RuntimeEventFeedContainer className="h-full" />
            </PanelBody>
          </DashboardPanel>
        </DashboardSplitView.Pane>
      </DashboardSplitView>
    </DashboardLayout>
  );
}
