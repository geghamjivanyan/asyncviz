/**
 * Semaphore contention page.
 *
 * Composes the contention panel + the timeline strip. The panel is
 * stateless; the container owns hydration + the websocket bridge.
 */

import { SemaphoreContentionContainer } from "@/dashboard/semaphores/SemaphoreContentionContainer";
import { SemaphoreContentionTimeline } from "@/dashboard/semaphores/SemaphoreContentionTimeline";
import { useSemaphoreContentionMarkers } from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";

export function SemaphoresPage(): JSX.Element {
  const markers = useSemaphoreContentionMarkers();

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Semaphores
        </h1>
      </header>

      <SemaphoreContentionTimeline markers={markers} heightPx={28} />

      <SemaphoreContentionContainer />
    </div>
  );
}
