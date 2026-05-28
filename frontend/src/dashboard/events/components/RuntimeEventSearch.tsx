/**
 * Search input for the runtime event feed.
 */

import type { ChangeEvent } from "react";

export interface RuntimeEventSearchProps {
  value: string;
  onChange: (next: string) => void;
}

export function RuntimeEventSearch({ value, onChange }: RuntimeEventSearchProps) {
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value);
  return (
    <label className="flex flex-1 items-center gap-2 text-subtle">
      <span className="text-[10px] uppercase tracking-widest text-muted">Search</span>
      <input
        type="search"
        value={value}
        onChange={handleChange}
        placeholder="Filter by id, name, task, or coroutine…"
        aria-label="Filter events"
        className="flex-1 rounded border border-line bg-canvas px-2 py-0.5 font-mono text-xs text-text outline-none placeholder:text-subtle focus:border-accent"
      />
    </label>
  );
}
