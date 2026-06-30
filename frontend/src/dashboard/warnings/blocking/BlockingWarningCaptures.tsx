/**
 * Correlated-captures preview.
 *
 * Each warning group carries the ids of every stack capture the
 * emitter correlated to it. The panel renders these as a compact
 * chip list with a click-through that the inspector can wire to the
 * stack-capture endpoint.
 *
 * The full capture payloads aren't fetched here — that's the
 * inspector's job. This component just lists the references so the
 * operator can see "this freeze produced 4 traces" at a glance.
 */

import { memo, useCallback } from "react";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";

export interface BlockingWarningCapturesProps {
  view: BlockingWarningView;
  onSelectCapture?: (captureId: number, groupId: string) => void;
  className?: string;
}

function BlockingWarningCapturesImpl({
  view,
  onSelectCapture,
  className,
}: BlockingWarningCapturesProps) {
  const handleClick = useCallback(
    (captureId: number) => {
      recordBlockingWarningTrace({
        kind: "reveal-capture",
        detail: `${view.groupId}:${captureId}`,
      });
      onSelectCapture?.(captureId, view.groupId);
    },
    [view.groupId, onSelectCapture],
  );

  if (view.captureIds.length === 0) {
    return (
      <p className={className} data-testid="blocking-warning-captures-empty">
        <span className="text-subtle text-xs">No captures correlated yet.</span>
      </p>
    );
  }

  return (
    <ul
      className={className}
      aria-label="Correlated stack captures"
      data-testid="blocking-warning-captures"
    >
      <li className="text-subtle uppercase tracking-wider text-[10px] mb-1">Captures</li>
      <li className="flex flex-wrap gap-1">
        {view.captureIds.map((captureId) => (
          <button
            key={captureId}
            type="button"
            onClick={() => handleClick(captureId)}
            className="inline-flex items-center rounded border border-line bg-elevated px-2 py-0.5 font-mono text-xs text-text hover:border-accent hover:text-accent"
            aria-label={`Open capture #${captureId}`}
            data-testid={`blocking-warning-capture-${captureId}`}
          >
            #{captureId}
          </button>
        ))}
      </li>
    </ul>
  );
}

export const BlockingWarningCaptures = memo(BlockingWarningCapturesImpl);
