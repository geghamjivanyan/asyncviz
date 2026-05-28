/**
 * Store-aware wrapper for :class:`ConnectionStatusIndicator`.
 *
 * The container is the only piece that reaches into the canonical
 * Zustand store. Everything below it is pure data → JSX.
 */

import { ConnectionStatusIndicator } from "@/dashboard/connection/components/ConnectionStatusIndicator";
import { useConnectionSummary } from "@/dashboard/connection/hooks/useConnectionSummary";

export interface ConnectionStatusContainerProps {
  badgeOnly?: boolean;
  className?: string;
}

export function ConnectionStatusContainer({
  badgeOnly,
  className,
}: ConnectionStatusContainerProps) {
  const summary = useConnectionSummary();
  return (
    <ConnectionStatusIndicator summary={summary} badgeOnly={badgeOnly} className={className} />
  );
}
