/**
 * Stateful container for the queue pressure panel.
 *
 * Owns: hydration, websocket bridge, projection memoization,
 * selection routing into the runtime store (inspector reveal).
 * Renders props onto :class:`QueuePressurePanel`.
 */

import { useCallback, useMemo } from "react";
import { useQueuePressureHydration } from "@/dashboard/queues/hooks/useQueuePressureHydration";
import { useQueuePressureWebsocketBridge } from "@/dashboard/queues/hooks/useQueuePressureWebsocketBridge";
import { useQueuePressureSelection } from "@/dashboard/queues/hooks/useQueuePressureSelection";
import { useQueuePressureViewsBundle } from "@/dashboard/queues/hooks/useQueuePressureViews";
import { QueuePressurePanel } from "@/dashboard/queues/QueuePressurePanel";
import {
  useQueuePressureErrorMessage,
  useQueuePressureStatus,
} from "@/dashboard/queues/selectors/QueuePressureSelectors";

export interface QueuePressureContainerProps {
  /** Disable websocket / fetch (tests + scripted scenarios). */
  disableLiveUpdates?: boolean;
  className?: string;
}

export function QueuePressureContainer({
  disableLiveUpdates = false,
  className,
}: QueuePressureContainerProps): JSX.Element {
  useQueuePressureHydration({ enabled: !disableLiveUpdates });
  useQueuePressureWebsocketBridge({ enabled: !disableLiveUpdates });

  const { bySeverityDescending, alarmCount } = useQueuePressureViewsBundle();
  const { selectedQueueId, selectQueue } = useQueuePressureSelection();
  const status = useQueuePressureStatus();
  const errorMessage = useQueuePressureErrorMessage();

  const handleSelect = useCallback(
    (queueId: string | null) => selectQueue(queueId),
    [selectQueue],
  );

  const statusProps = useMemo(
    () => ({ status, errorMessage }),
    [status, errorMessage],
  );

  return (
    <QueuePressurePanel
      views={bySeverityDescending}
      alarmCount={alarmCount}
      selectedQueueId={selectedQueueId}
      onSelectQueue={handleSelect}
      status={statusProps}
      className={className}
    />
  );
}
