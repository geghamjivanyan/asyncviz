/**
 * Stateful container for the executor activity panel.
 */

import { useCallback, useMemo } from "react";
import { useExecutorActivityHydration } from "@/dashboard/executors/hooks/useExecutorActivityHydration";
import { useExecutorActivityWebsocketBridge } from "@/dashboard/executors/hooks/useExecutorActivityWebsocketBridge";
import { useExecutorActivitySelection } from "@/dashboard/executors/hooks/useExecutorActivitySelection";
import { useExecutorActivityViewsBundle } from "@/dashboard/executors/hooks/useExecutorActivityViews";
import { ExecutorActivityPanel } from "@/dashboard/executors/ExecutorActivityPanel";
import {
  useExecutorActivityErrorMessage,
  useExecutorActivityStatus,
} from "@/dashboard/executors/selectors/ExecutorActivitySelectors";

export interface ExecutorActivityContainerProps {
  disableLiveUpdates?: boolean;
  className?: string;
}

export function ExecutorActivityContainer({
  disableLiveUpdates = false,
  className,
}: ExecutorActivityContainerProps): JSX.Element {
  useExecutorActivityHydration({ enabled: !disableLiveUpdates });
  useExecutorActivityWebsocketBridge({ enabled: !disableLiveUpdates });

  const { bySeverityDescending, alarmCount } = useExecutorActivityViewsBundle();
  const { selectedExecutorId, selectExecutor } = useExecutorActivitySelection();
  const status = useExecutorActivityStatus();
  const errorMessage = useExecutorActivityErrorMessage();

  const handleSelect = useCallback(
    (executorId: string | null) => selectExecutor(executorId),
    [selectExecutor],
  );

  const statusProps = useMemo(() => ({ status, errorMessage }), [status, errorMessage]);

  return (
    <ExecutorActivityPanel
      views={bySeverityDescending}
      alarmCount={alarmCount}
      selectedExecutorId={selectedExecutorId}
      onSelectExecutor={handleSelect}
      status={statusProps}
      className={className}
    />
  );
}
