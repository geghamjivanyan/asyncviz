/**
 * Dedicated timeline route.
 *
 * Wires the canonical :class:`TimelineContainer` alongside the
 * task detail inspector so the dashboard renders the canvas + the
 * runtime introspection surface side-by-side.
 */

import { useCallback } from "react";
import { TimelineContainer } from "@/dashboard/timeline";
import { TaskInspectorContainer, useInspectorFocusBridge } from "@/dashboard/inspector";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions";

export function TimelinePage() {
  const { actions, setActions } = useInspectorFocusBridge();
  const handleFocusActions = useCallback(
    (next: { reveal: () => void; fit: () => void }) => {
      setActions(next);
    },
    [setActions],
  );

  // Canvas → panel cross-link: a freeze clicked on the timeline opens
  // the matching card in the blocking-warnings panel store. The panel
  // doesn't have to be mounted here — selection lives in the store so
  // whichever container picks it up next renders the inspector.
  const setBlockingSelected = useBlockingWarningStore((s) => s.setSelectedGroup);
  const handleFreezeFocus = useCallback(
    (region: FreezeRegionView | null) => {
      setBlockingSelected(region?.groupId ?? null);
    },
    [setBlockingSelected],
  );

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 gap-2" data-timeline-page="true">
      <div className="flex h-full min-h-0 flex-1 flex-col">
        <TimelineContainer
          className="h-full"
          onFocusActions={handleFocusActions}
          onFreezeFocus={handleFreezeFocus}
        />
      </div>
      <aside
        className="hidden h-full w-[360px] flex-shrink-0 md:flex"
        aria-label="Task inspector"
        data-timeline-page-inspector="true"
      >
        <TaskInspectorContainer
          className="h-full w-full"
          onRevealSelection={actions.reveal}
          onFitSelection={actions.fit}
        />
      </aside>
    </div>
  );
}
