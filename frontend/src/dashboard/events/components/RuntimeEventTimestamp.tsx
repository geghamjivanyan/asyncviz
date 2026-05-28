/**
 * Timestamp cell — renders the wall time + duration when available.
 */

import { cn } from "@/lib/cn";
import { formatEventDuration, formatEventTime } from "@/dashboard/events/utils/format";

export interface RuntimeEventTimestampProps {
  timestampSeconds: number;
  durationSeconds: number | null;
  className?: string;
}

export function RuntimeEventTimestamp({
  timestampSeconds,
  durationSeconds,
  className,
}: RuntimeEventTimestampProps) {
  const duration = formatEventDuration(durationSeconds);
  return (
    <div
      className={cn(
        "flex shrink-0 flex-col items-end font-mono text-[10px] text-subtle",
        className,
      )}
    >
      <span aria-label={`Event time ${formatEventTime(timestampSeconds)}`} className="tabular-nums">
        {formatEventTime(timestampSeconds)}
      </span>
      {duration !== "" && (
        <span aria-label={`Duration ${duration}`} className="tabular-nums text-muted">
          {duration}
        </span>
      )}
    </div>
  );
}
