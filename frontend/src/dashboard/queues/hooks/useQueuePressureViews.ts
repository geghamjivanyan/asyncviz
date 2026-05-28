/**
 * Convenience hook bundling the projection + ordering selectors a panel
 * typically needs together. Single-call ergonomics for a component
 * that wants both the by-severity list and the alarm count without
 * subscribing twice.
 */

import { useMemo } from "react";
import { useQueueRecords } from "@/dashboard/queues/selectors/QueuePressureSelectors";
import { projectQueuePressure } from "@/dashboard/queues/QueuePressureProjection";
import type { QueuePressureProjection } from "@/dashboard/queues/QueuePressureProjection";

export function useQueuePressureViewsBundle(): QueuePressureProjection {
  const records = useQueueRecords();
  return useMemo(() => projectQueuePressure({ records }), [records]);
}
