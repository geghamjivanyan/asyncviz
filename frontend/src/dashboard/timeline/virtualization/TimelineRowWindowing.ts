/**
 * Row-specific windowing facade.
 *
 * Wraps :func:`cullRowsByWindow` so the engine can hand the row
 * subsystem a single import. Keeping the facade separate keeps the
 * unit boundaries between rows + segments crisp.
 */

import {
  cullRowsByWindow,
  type CullableRow,
} from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import type { TimelineRowWindow } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export function projectRowWindow<T extends CullableRow>(
  rows: readonly T[],
  window: TimelineRowWindow,
): T[] {
  return cullRowsByWindow(rows, window);
}
