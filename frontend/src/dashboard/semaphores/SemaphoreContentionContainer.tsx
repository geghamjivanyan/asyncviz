/**
 * Stateful container for the semaphore contention panel.
 *
 * Owns: hydration, websocket bridge, projection memoization, selection
 * routing into the runtime store (inspector reveal).
 */

import { useCallback, useMemo } from "react";
import { useSemaphoreContentionHydration } from "@/dashboard/semaphores/hooks/useSemaphoreContentionHydration";
import { useSemaphoreContentionWebsocketBridge } from "@/dashboard/semaphores/hooks/useSemaphoreContentionWebsocketBridge";
import { useSemaphoreContentionSelection } from "@/dashboard/semaphores/hooks/useSemaphoreContentionSelection";
import { useSemaphoreContentionViewsBundle } from "@/dashboard/semaphores/hooks/useSemaphoreContentionViews";
import { SemaphoreContentionPanel } from "@/dashboard/semaphores/SemaphoreContentionPanel";
import {
  useSemaphoreContentionErrorMessage,
  useSemaphoreContentionStatus,
} from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";

export interface SemaphoreContentionContainerProps {
  disableLiveUpdates?: boolean;
  className?: string;
}

export function SemaphoreContentionContainer({
  disableLiveUpdates = false,
  className,
}: SemaphoreContentionContainerProps): JSX.Element {
  useSemaphoreContentionHydration({ enabled: !disableLiveUpdates });
  useSemaphoreContentionWebsocketBridge({ enabled: !disableLiveUpdates });

  const { bySeverityDescending, alarmCount } = useSemaphoreContentionViewsBundle();
  const { selectedSemaphoreId, selectSemaphore } = useSemaphoreContentionSelection();
  const status = useSemaphoreContentionStatus();
  const errorMessage = useSemaphoreContentionErrorMessage();

  const handleSelect = useCallback(
    (semaphoreId: string | null) => selectSemaphore(semaphoreId),
    [selectSemaphore],
  );

  const statusProps = useMemo(() => ({ status, errorMessage }), [status, errorMessage]);

  return (
    <SemaphoreContentionPanel
      views={bySeverityDescending}
      alarmCount={alarmCount}
      selectedSemaphoreId={selectedSemaphoreId}
      onSelectSemaphore={handleSelect}
      status={statusProps}
      className={className}
    />
  );
}
