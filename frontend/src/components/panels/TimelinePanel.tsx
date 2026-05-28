/**
 * Canvas-backed timeline panel.
 *
 * Composes the canonical :class:`TimelineContainer` inside the legacy
 * :class:`PanelShell` so existing dashboard layouts pick up the new
 * renderer without changing their composition.
 */

import { TimelineContainer } from "@/dashboard/timeline";
import { PanelShell } from "./PanelShell";

export function TimelinePanel() {
  return (
    <PanelShell title="Timeline">
      <TimelineContainer className="h-full" />
    </PanelShell>
  );
}
