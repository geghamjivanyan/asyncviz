/**
 * Responsive grid for the metrics header cards.
 *
 * The grid wraps onto two rows at narrow widths and onto a single row
 * at desktop widths. Each cell pins to a minimum width so a sudden
 * value change doesn't shrink neighbors.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface MetricsGridProps {
  children: ReactNode;
  className?: string;
}

export function MetricsGrid({ children, className }: MetricsGridProps) {
  return (
    <div
      role="list"
      aria-label="Runtime metrics"
      data-metrics-grid="true"
      className={cn(
        "grid w-full grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-8",
        className,
      )}
    >
      {children}
    </div>
  );
}
