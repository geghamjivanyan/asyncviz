/**
 * Executor activity page.
 *
 * Composes the executor panel + the timeline strip.
 */

import { ExecutorActivityContainer } from "@/dashboard/executors/ExecutorActivityContainer";
import { ExecutorActivityTimeline } from "@/dashboard/executors/ExecutorActivityTimeline";
import { useExecutorActivityMarkers } from "@/dashboard/executors/selectors/ExecutorActivitySelectors";

export function ExecutorsPage(): JSX.Element {
  const markers = useExecutorActivityMarkers();

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Executors
        </h1>
      </header>

      <ExecutorActivityTimeline markers={markers} heightPx={28} />

      <ExecutorActivityContainer />
    </div>
  );
}
