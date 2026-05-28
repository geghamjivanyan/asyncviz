/**
 * Render the row's flattened metadata as a compact key/value list.
 *
 * Truncated to a bounded entry count by the projection so this can
 * stay rendered without measurement.
 */

import { cn } from "@/lib/cn";

export interface RuntimeEventMetadataProps {
  entries: ReadonlyArray<readonly [string, string]>;
  className?: string;
}

export function RuntimeEventMetadata({ entries, className }: RuntimeEventMetadataProps) {
  if (entries.length === 0) return null;
  return (
    <dl
      className={cn(
        "flex flex-wrap gap-x-2 gap-y-0.5 font-mono text-[10px] text-subtle",
        className,
      )}
    >
      {entries.map(([key, value]) => (
        <span key={key} className="inline-flex items-center gap-1">
          <dt className="text-muted">{key}</dt>
          <dd className="text-text">{value}</dd>
        </span>
      ))}
    </dl>
  );
}
