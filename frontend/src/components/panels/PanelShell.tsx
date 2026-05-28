/**
 * Legacy panel wrapper preserved for backward compatibility.
 *
 * Delegates to the canonical :class:`DashboardPanel` so every existing
 * panel (Timeline, Event, Inspector) inherits the new accessibility
 * + observability surface without touching its component code.
 */

import type { ReactNode } from "react";
import { DashboardPanel, PanelBody, PanelHeader, PanelToolbar } from "@/dashboard/layout";

interface PanelShellProps {
  title: string;
  className?: string;
  toolbar?: ReactNode;
  children: ReactNode;
}

export function PanelShell({ title, className, toolbar, children }: PanelShellProps) {
  // Derive a stable panel id from the title — used by the layout
  // observability hook to record per-panel mount timings.
  const panelId = title.toLowerCase().replace(/\s+/g, "-");
  return (
    <DashboardPanel id={panelId} className={className}>
      <PanelHeader title={title}>{toolbar && <PanelToolbar>{toolbar}</PanelToolbar>}</PanelHeader>
      <PanelBody>{children}</PanelBody>
    </DashboardPanel>
  );
}
