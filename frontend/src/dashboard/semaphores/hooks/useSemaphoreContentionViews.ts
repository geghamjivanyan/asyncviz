/**
 * Convenience hook bundling the projection + ordering selectors a
 * panel typically needs together.
 */

import { useMemo } from "react";
import { useSemaphoreRecords } from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";
import { projectSemaphoreContention } from "@/dashboard/semaphores/SemaphoreContentionProjection";
import type { SemaphoreContentionProjection } from "@/dashboard/semaphores/SemaphoreContentionProjection";

export function useSemaphoreContentionViewsBundle(): SemaphoreContentionProjection {
  const records = useSemaphoreRecords();
  return useMemo(() => projectSemaphoreContention({ records }), [records]);
}
