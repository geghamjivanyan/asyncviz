import { describe, expect, it } from "vitest";
import { ClientMetrics } from "@/runtime/observability/clientMetrics";

describe("ClientMetrics", () => {
  it("starts with every counter at zero", () => {
    const metrics = new ClientMetrics();
    const snap = metrics.snapshot();
    expect(snap.envelopesReceived).toBe(0);
    expect(snap.websocketReconnects).toBe(0);
    expect(snap.snapshotHydrations).toBe(0);
    expect(snap.renderErrors).toBe(0);
  });

  it("increments counters via the per-event record methods", () => {
    const metrics = new ClientMetrics();
    metrics.recordConnectAttempt();
    metrics.recordConnectAttempt();
    metrics.recordReconnect();
    metrics.recordEnvelope();
    metrics.recordEnvelope();
    metrics.recordEnvelopeDrop();
    metrics.recordProtocolMismatch();
    metrics.recordSnapshotHydration();
    metrics.recordSnapshotHydrationFailure();
    metrics.recordRenderError();
    metrics.recordWebsocketFailure();
    const snap = metrics.snapshot();
    expect(snap.websocketConnectAttempts).toBe(2);
    expect(snap.websocketReconnects).toBe(1);
    expect(snap.envelopesReceived).toBe(2);
    expect(snap.envelopesDropped).toBe(1);
    expect(snap.protocolMismatches).toBe(1);
    expect(snap.snapshotHydrations).toBe(1);
    expect(snap.snapshotHydrationFailures).toBe(1);
    expect(snap.renderErrors).toBe(1);
    expect(snap.websocketFailures).toBe(1);
    expect(snap.lastEnvelopeAtMonotonicMs).toBeGreaterThan(0);
  });

  it("reset clears every counter", () => {
    const metrics = new ClientMetrics();
    metrics.recordEnvelope();
    metrics.recordReconnect();
    metrics.reset();
    const snap = metrics.snapshot();
    expect(snap.envelopesReceived).toBe(0);
    expect(snap.websocketReconnects).toBe(0);
    expect(snap.lastEnvelopeAtMonotonicMs).toBe(0);
  });
});
