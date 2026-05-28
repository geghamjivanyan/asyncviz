/**
 * Group-mode selector for the event feed.
 *
 * Today exposes ``none / task / category / replay-batch``. Stays a
 * thin shell so other modes (lineage / coroutine / time-window) can
 * be wired in without further re-design.
 */

import type { EventGroupingMode } from "@/dashboard/events/models/filters";

const MODES: Array<{ value: EventGroupingMode; label: string }> = [
  { value: "none", label: "None" },
  { value: "task", label: "Task" },
  { value: "category", label: "Category" },
  { value: "replay-batch", label: "Replay" },
];

export interface RuntimeEventGroupingProps {
  mode: EventGroupingMode;
  onChange: (mode: EventGroupingMode) => void;
}

export function RuntimeEventGrouping({ mode, onChange }: RuntimeEventGroupingProps) {
  return (
    <label className="flex items-center gap-1.5 text-subtle">
      <span className="text-[10px] uppercase tracking-widest text-muted">Group</span>
      <select
        value={mode}
        onChange={(e) => onChange(e.target.value as EventGroupingMode)}
        aria-label="Group events"
        className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-text focus:border-accent focus:outline-none"
      >
        {MODES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
    </label>
  );
}
