import { describe, expect, it, vi } from "vitest";
import type { RuntimeEnvelope } from "@/types/runtime";
import {
  blockingPayloadFromEnvelope,
  makeBlockingWarningSubscribeFactory,
  type BlockingWarningEnvelopeSource,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningWebsocketBridge";
import { makeEvent } from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

function buildEnvelope(eventType: string, inner: unknown): RuntimeEnvelope {
  return {
    protocol_version: "1.0",
    type: "runtime_event",
    timestamp: 1.0,
    sequence: 7,
    payload: {
      event_id: "evt-1",
      event_type: eventType,
      timestamp: 1.0,
      monotonic_timestamp: 1.0,
      monotonic_ns: 1_000_000,
      runtime_id: "rt-1",
      source: "runtime",
      payload_version: 1,
      payload: inner,
    } as unknown as Record<string, unknown>,
  };
}

describe("blockingPayloadFromEnvelope", () => {
  it("extracts the inner payload for a blocking event type", () => {
    const event = makeEvent({ transition: "opened", state: "opened" });
    const envelope = buildEnvelope("runtime.warnings.blocking.opened", event);
    const result = blockingPayloadFromEnvelope(envelope);
    expect(result).not.toBeNull();
    expect(result?.group_id).toBe(event.group_id);
  });

  it("returns null for non-blocking event types", () => {
    const envelope = buildEnvelope("asyncio.task.started", {});
    expect(blockingPayloadFromEnvelope(envelope)).toBeNull();
  });

  it("returns null when the inner payload is missing", () => {
    const envelope = buildEnvelope("runtime.warnings.blocking.opened", null);
    expect(blockingPayloadFromEnvelope(envelope)).toBeNull();
  });

  it("returns null when the outer payload lacks event_type", () => {
    const envelope: RuntimeEnvelope = {
      protocol_version: "1.0",
      type: "runtime_event",
      timestamp: 1.0,
      payload: {},
    };
    expect(blockingPayloadFromEnvelope(envelope)).toBeNull();
  });
});

describe("makeBlockingWarningSubscribeFactory", () => {
  it("forwards blocking payloads + ignores other event types", () => {
    const handlers = new Set<(env: RuntimeEnvelope) => void>();
    const source: BlockingWarningEnvelopeSource = {
      subscribe: (filter, listener) => {
        expect(filter).toBe("runtime_event");
        handlers.add(listener);
        return { unsubscribe: () => handlers.delete(listener) };
      },
    };
    const apply = vi.fn();
    const factory = makeBlockingWarningSubscribeFactory(source);
    const unsubscribe = factory(apply);

    const event = makeEvent({ transition: "active" });
    for (const handler of handlers) {
      handler(buildEnvelope("runtime.warnings.blocking.active", event));
      handler(buildEnvelope("asyncio.task.started", { foo: "bar" }));
    }

    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls[0][0].group_id).toBe(event.group_id);

    unsubscribe();
    expect(handlers.size).toBe(0);
  });
});
