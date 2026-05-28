/**
 * Public surface of the runtime-event-feed system.
 *
 * Consumers import from this barrel — the internal layout (components,
 * hooks, selectors, observability, utils) can evolve without breaking
 * callers.
 */

export { RuntimeEventFeed } from "@/dashboard/events/components/RuntimeEventFeed";
export type { RuntimeEventFeedProps } from "@/dashboard/events/components/RuntimeEventFeed";
export { RuntimeEventFeedContainer } from "@/dashboard/events/components/RuntimeEventFeedContainer";
export type { RuntimeEventFeedContainerProps } from "@/dashboard/events/components/RuntimeEventFeedContainer";
export { RuntimeEventList } from "@/dashboard/events/components/RuntimeEventList";
export type { RuntimeEventListProps } from "@/dashboard/events/components/RuntimeEventList";
export { RuntimeEventRow } from "@/dashboard/events/components/RuntimeEventRow";
export type { RuntimeEventRowProps } from "@/dashboard/events/components/RuntimeEventRow";
export { RuntimeEventBadge } from "@/dashboard/events/components/RuntimeEventBadge";
export { RuntimeEventTimestamp } from "@/dashboard/events/components/RuntimeEventTimestamp";
export { RuntimeEventMetadata } from "@/dashboard/events/components/RuntimeEventMetadata";
export { RuntimeEventToolbar } from "@/dashboard/events/components/RuntimeEventToolbar";
export { RuntimeEventFilter } from "@/dashboard/events/components/RuntimeEventFilter";
export { RuntimeEventSearch } from "@/dashboard/events/components/RuntimeEventSearch";
export { RuntimeEventGrouping } from "@/dashboard/events/components/RuntimeEventGrouping";
export { RuntimeEventDiagnostics } from "@/dashboard/events/components/RuntimeEventDiagnostics";

export {
  buildEventRow,
  categoryForEvent,
  compareEventRowsNewestFirst,
  compareEventRowsOldestFirst,
  deriveEventLabel,
  intentForCategory,
  signEventRow,
  summarizeWarnings,
  type EventCategory,
  type EventRow,
  type EventRowIntent,
  type EventRowTimelineSummary,
  type EventRowWarningSummary,
  type EventSource,
} from "@/dashboard/events/models/eventRow";

export {
  DEFAULT_EVENT_FILTERS,
  DEFAULT_EVENT_GROUPING,
  DEFAULT_EVENT_SORT,
  isDefaultEventFilterState,
  type EventFilterState,
  type EventGroupingMode,
  type EventGroupingState,
  type EventSortDirection,
  type EventSortState,
} from "@/dashboard/events/models/filters";

export {
  applyEventFilterAndSort,
  filterEventRows,
  sortEventRows,
} from "@/dashboard/events/utils/sortFilter";

export { groupEventRows, type EventGroup } from "@/dashboard/events/utils/grouping";

export {
  formatCategory,
  formatEventDuration,
  formatEventTime,
  formatTaskIdCompact,
} from "@/dashboard/events/utils/format";

export {
  projectEventRows,
  type EventProjectionInputs,
} from "@/dashboard/events/selectors/projectEvents";

export { useProjectedEventRows } from "@/dashboard/events/selectors/storeSelectors";
export { useEventFeedState } from "@/dashboard/events/hooks/useEventFeedState";
export type { EventFeedStateValue } from "@/dashboard/events/hooks/useEventFeedState";
export { useEventRows } from "@/dashboard/events/hooks/useEventRows";
export { useEventGroups } from "@/dashboard/events/hooks/useEventGroups";
export {
  EVENT_ROW_HEIGHT_PX,
  useEventVirtualization,
  type EventVirtualizationWindow,
} from "@/dashboard/events/hooks/useEventVirtualization";

export {
  EventFeedMetrics,
  type EventFeedMetricsSnapshot,
  getEventFeedMetrics,
  resetEventFeedMetrics,
} from "@/dashboard/events/observability";
