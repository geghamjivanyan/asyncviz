/**
 * Queue pressure page.
 *
 * Composes the queue panel + the timeline strip + a small footer
 * highlighting the most-pressured queue's contention. The panel
 * + timeline are stateless; the container owns hydration + the
 * websocket bridge.
 */

import { QueuePressureContainer } from "@/dashboard/queues/QueuePressureContainer";
import { QueuePressureTimeline } from "@/dashboard/queues/QueuePressureTimeline";
import { useQueuePressureMarkers } from "@/dashboard/queues/selectors/QueuePressureSelectors";

export function QueuesPage(): JSX.Element {
  const markers = useQueuePressureMarkers();

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Queues
        </h1>
      </header>

      <QueuePressureTimeline markers={markers} heightPx={28} />

      <QueuePressureContainer />
    </div>
  );
}
