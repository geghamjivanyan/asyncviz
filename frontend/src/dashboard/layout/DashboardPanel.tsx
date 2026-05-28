/**
 * Canonical panel primitive.
 *
 * Replaces the legacy ``PanelShell``. Provides a small composition
 * surface — :class:`PanelHeader`, :class:`PanelBody`,
 * :class:`PanelToolbar`, :class:`PanelStatusBadge` — so every
 * panel-shaped widget in the dashboard renders with the same chrome,
 * focus behavior, and observability.
 *
 * Composition example::
 *
 *   <DashboardPanel id="timeline" intent="default">
 *     <PanelHeader title="Timeline">
 *       <PanelToolbar>
 *         <PanelStatusBadge intent="success">live</PanelStatusBadge>
 *       </PanelToolbar>
 *     </PanelHeader>
 *     <PanelBody scroll="y">
 *       ...
 *     </PanelBody>
 *   </DashboardPanel>
 */

import { createContext, useContext } from "react";
import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Badge } from "@/ui/primitives/Badge";
import type { BadgeProps } from "@/ui/primitives/Badge";
import { INTENT_BORDER } from "@/ui/theme/tokens";
import type { Intent } from "@/ui/theme/tokens";
import { useLayoutObservability } from "@/dashboard/layout/hooks/useLayoutObservability";
import { DashboardRegion } from "@/dashboard/layout/DashboardRegion";
import type { RegionScroll } from "@/dashboard/layout/DashboardRegion";

interface PanelContextValue {
  id: string;
  loading: boolean;
  hasError: boolean;
}

const PanelContext = createContext<PanelContextValue | null>(null);

export interface DashboardPanelProps {
  /** Stable id used for observability + the fullscreen layout state. */
  id: string;
  /** Bordered accent applied to the panel frame. */
  intent?: Intent;
  /** Whether the body is currently rendering a loading state. */
  loading?: boolean;
  /** Whether the body is currently rendering an error state. */
  error?: Error | null;
  /** Custom class — composed with the panel frame defaults. */
  className?: string;
  children: ReactNode;
}

export function DashboardPanel({
  id,
  intent = "default",
  loading = false,
  error = null,
  className,
  children,
}: DashboardPanelProps) {
  useLayoutObservability(id);
  return (
    <PanelContext.Provider value={{ id, loading, hasError: error !== null }}>
      <section
        role="group"
        aria-label={`Panel ${id}`}
        data-panel-id={id}
        data-panel-loading={loading ? "true" : "false"}
        data-panel-error={error !== null ? "true" : "false"}
        className={cn(
          "flex h-full min-h-0 min-w-0 flex-col rounded border bg-panel",
          INTENT_BORDER[intent],
          className,
        )}
      >
        {children}
      </section>
    </PanelContext.Provider>
  );
}

function usePanel(): PanelContextValue {
  const ctx = useContext(PanelContext);
  if (ctx === null) {
    throw new Error("Panel subcomponents must be used inside <DashboardPanel>");
  }
  return ctx;
}

export interface PanelHeaderProps extends HTMLAttributes<HTMLElement> {
  title: string;
  /** Optional subtitle rendered next to the title. */
  subtitle?: ReactNode;
  /** Right-aligned toolbar content; usually a :class:`PanelToolbar`. */
  children?: ReactNode;
}

export function PanelHeader({ title, subtitle, className, children, ...rest }: PanelHeaderProps) {
  return (
    <header
      {...rest}
      className={cn(
        "flex h-9 shrink-0 items-center justify-between gap-3 border-b border-line px-3",
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-2 truncate">
        <span className="font-mono text-xs uppercase tracking-widest text-muted">{title}</span>
        {subtitle !== undefined && (
          <span className="truncate font-mono text-xs text-subtle">{subtitle}</span>
        )}
      </div>
      {children !== undefined && (
        <div className="flex items-center gap-2 text-xs text-subtle">{children}</div>
      )}
    </header>
  );
}

export interface PanelBodyProps {
  scroll?: RegionScroll;
  className?: string;
  children: ReactNode;
}

export function PanelBody({ scroll = "auto", className, children }: PanelBodyProps) {
  const { id } = usePanel();
  return (
    <DashboardRegion label={`${id} body`} scroll={scroll} grow className={cn("p-0", className)}>
      {children}
    </DashboardRegion>
  );
}

export interface PanelToolbarProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function PanelToolbar({ className, children, ...rest }: PanelToolbarProps) {
  return (
    <div {...rest} className={cn("flex items-center gap-2 text-xs text-subtle", className)}>
      {children}
    </div>
  );
}

export type PanelStatusBadgeProps = BadgeProps;

/**
 * Status badge with panel-aware defaults. Today it just forwards to
 * the canonical :class:`Badge`; the indirection exists so future
 * panel-level visual coupling (e.g. pulse animation when status
 * transitions) can be added in one place.
 */
export function PanelStatusBadge(props: PanelStatusBadgeProps) {
  return <Badge {...props} />;
}
