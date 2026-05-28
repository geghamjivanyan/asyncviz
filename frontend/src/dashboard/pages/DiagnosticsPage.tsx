import { useEffect, useState } from "react";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { TaskDiagnostics } from "@/dashboard/tasks";
import { MetricsDiagnostics } from "@/dashboard/metrics";
import { RuntimeEventDiagnostics } from "@/dashboard/events";
import { ConnectionDiagnostics } from "@/dashboard/connection";
import { TimelineDiagnostics } from "@/dashboard/timeline";
import { BlockingWarningsDiagnostics } from "@/dashboard/warnings/blocking";
import { FreezeRegionDiagnostics } from "@/dashboard/timeline/freeze_regions";
import { QueuePressureDiagnostics } from "@/dashboard/queues";
import { SemaphoreContentionDiagnostics } from "@/dashboard/semaphores";
import { AwaitDependencyDiagnostics } from "@/dashboard/dependencies";
import { ExecutorActivityDiagnostics } from "@/dashboard/executors";

interface ClientStats {
  envelopesReceived: number;
  envelopesDropped: number;
  websocketConnectAttempts: number;
  websocketReconnects: number;
  websocketFailures: number;
  protocolMismatches: number;
  snapshotHydrations: number;
  snapshotHydrationFailures: number;
  renderErrors: number;
}

/**
 * Diagnostics page — live frontend counters next to backend version /
 * config metadata. Future iterations will pull the backend's
 * ``/api/runtime/snapshot/metrics`` etc. and render them inline.
 */
export function DiagnosticsPage() {
  const config = useRuntimeConfig();
  const metrics = useClientMetrics();
  const [stats, setStats] = useState<ClientStats>(() => projectStats(metrics.snapshot()));

  useEffect(() => {
    // Poll the metrics instance once per second — JS-side counters
    // change as websocket envelopes arrive.
    const handle = window.setInterval(() => {
      setStats(projectStats(metrics.snapshot()));
    }, 1000);
    return () => window.clearInterval(handle);
  }, [metrics]);

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">Diagnostics</h1>
        <Badge intent="accent">build {config.buildVersion}</Badge>
      </header>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        <Card>
          <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">Config</h2>
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
            <dt className="text-muted">API base</dt>
            <dd className="text-text">{config.apiBaseUrl || "<same-origin>"}</dd>
            <dt className="text-muted">WS url</dt>
            <dd className="text-text">{config.websocketUrl}</dd>
            <dt className="text-muted">Protocol</dt>
            <dd className="text-text">{config.protocolVersion}</dd>
          </dl>
        </Card>

        <Card>
          <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">Websocket</h2>
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
            <dt className="text-muted">attempts</dt>
            <dd className="text-text">{stats.websocketConnectAttempts}</dd>
            <dt className="text-muted">reconnects</dt>
            <dd className="text-text">{stats.websocketReconnects}</dd>
            <dt className="text-muted">failures</dt>
            <dd className="text-text">{stats.websocketFailures}</dd>
          </dl>
        </Card>

        <Card>
          <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">Envelopes</h2>
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
            <dt className="text-muted">received</dt>
            <dd className="text-text">{stats.envelopesReceived}</dd>
            <dt className="text-muted">dropped</dt>
            <dd className="text-text">{stats.envelopesDropped}</dd>
            <dt className="text-muted">protocol mismatch</dt>
            <dd className="text-text">{stats.protocolMismatches}</dd>
          </dl>
        </Card>

        <Card>
          <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">Hydration</h2>
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
            <dt className="text-muted">hydrations</dt>
            <dd className="text-text">{stats.snapshotHydrations}</dd>
            <dt className="text-muted">failures</dt>
            <dd className="text-text">{stats.snapshotHydrationFailures}</dd>
            <dt className="text-muted">render errors</dt>
            <dd className="text-text">{stats.renderErrors}</dd>
          </dl>
        </Card>

        <Card>
          <TaskDiagnostics />
        </Card>

        <Card>
          <MetricsDiagnostics />
        </Card>

        <Card>
          <RuntimeEventDiagnostics />
        </Card>

        <Card>
          <ConnectionDiagnostics />
        </Card>

        <Card>
          <TimelineDiagnostics />
        </Card>

        <Card>
          <BlockingWarningsDiagnostics />
        </Card>

        <Card>
          <FreezeRegionDiagnostics />
        </Card>

        <Card>
          <QueuePressureDiagnostics />
        </Card>

        <Card>
          <SemaphoreContentionDiagnostics />
        </Card>

        <Card>
          <AwaitDependencyDiagnostics />
        </Card>

        <Card>
          <ExecutorActivityDiagnostics />
        </Card>
      </section>
    </div>
  );
}

function projectStats(
  snap: ReturnType<ReturnType<typeof useClientMetrics>["snapshot"]>,
): ClientStats {
  return {
    envelopesReceived: snap.envelopesReceived,
    envelopesDropped: snap.envelopesDropped,
    websocketConnectAttempts: snap.websocketConnectAttempts,
    websocketReconnects: snap.websocketReconnects,
    websocketFailures: snap.websocketFailures,
    protocolMismatches: snap.protocolMismatches,
    snapshotHydrations: snap.snapshotHydrations,
    snapshotHydrationFailures: snap.snapshotHydrationFailures,
    renderErrors: snap.renderErrors,
  };
}
