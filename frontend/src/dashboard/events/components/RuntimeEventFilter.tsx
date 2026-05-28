/**
 * Foundational filter toggles for the runtime event feed.
 *
 * The buttons are pressed/unpressed via ``aria-pressed`` so screen
 * readers + tests can drive them by accessible name.
 */

import { cn } from "@/lib/cn";

export interface RuntimeEventFilterProps {
  warningsOnly: boolean;
  replayOnly: boolean;
  terminalOnly: boolean;
  activeTimelineOnly: boolean;
  onChange: (
    next: Partial<{
      warningsOnly: boolean;
      replayOnly: boolean;
      terminalOnly: boolean;
      activeTimelineOnly: boolean;
    }>,
  ) => void;
}

export function RuntimeEventFilter({
  warningsOnly,
  replayOnly,
  terminalOnly,
  activeTimelineOnly,
  onChange,
}: RuntimeEventFilterProps) {
  return (
    <div role="group" aria-label="Event filters" className="flex items-center gap-1">
      <FilterButton
        label="Warnings"
        active={warningsOnly}
        onClick={() => onChange({ warningsOnly: !warningsOnly })}
      />
      <FilterButton
        label="Replay"
        active={replayOnly}
        onClick={() => onChange({ replayOnly: !replayOnly })}
      />
      <FilterButton
        label="Terminal"
        active={terminalOnly}
        onClick={() => onChange({ terminalOnly: !terminalOnly })}
      />
      <FilterButton
        label="Active"
        active={activeTimelineOnly}
        onClick={() => onChange({ activeTimelineOnly: !activeTimelineOnly })}
      />
    </div>
  );
}

function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest",
        active
          ? "border-accent text-accent"
          : "border-line text-subtle hover:border-accent hover:text-accent",
      )}
    >
      {label}
    </button>
  );
}
