/**
 * Placeholder for panels without data yet.
 *
 * Used by page placeholders that haven't been implemented + by
 * dashboards waiting for a websocket hydration.
 */

import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-12 text-center text-muted">
      <p className="font-mono text-xs uppercase tracking-widest text-subtle">{title}</p>
      {description !== undefined && <p className="max-w-md text-sm">{description}</p>}
      {action !== undefined && <div className="mt-2">{action}</div>}
    </div>
  );
}
