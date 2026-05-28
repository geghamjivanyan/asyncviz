/**
 * Compact badge for the event category.
 */

import { Badge } from "@/ui/primitives/Badge";
import type { Intent } from "@/ui/theme/tokens";
import type { EventCategory, EventRowIntent } from "@/dashboard/events/models/eventRow";
import { formatCategory } from "@/dashboard/events/utils/format";

const INTENT_BY_ROW: Record<EventRowIntent, Intent> = {
  default: "default",
  accent: "accent",
  success: "success",
  warning: "warning",
  danger: "danger",
};

export interface RuntimeEventBadgeProps {
  category: EventCategory;
  intent: EventRowIntent;
}

export function RuntimeEventBadge({ category, intent }: RuntimeEventBadgeProps) {
  return (
    <Badge intent={INTENT_BY_ROW[intent]} aria-label={`Event category ${category}`}>
      {formatCategory(category)}
    </Badge>
  );
}
