/**
 * Convenience hook bundling projection + ordering selectors together.
 */

import { useMemo } from "react";
import { useExecutorRecords } from "@/dashboard/executors/selectors/ExecutorActivitySelectors";
import { projectExecutorActivity } from "@/dashboard/executors/ExecutorActivityProjection";
import type { ExecutorActivityProjection } from "@/dashboard/executors/ExecutorActivityProjection";

export function useExecutorActivityViewsBundle(): ExecutorActivityProjection {
  const records = useExecutorRecords();
  return useMemo(() => projectExecutorActivity({ records }), [records]);
}
