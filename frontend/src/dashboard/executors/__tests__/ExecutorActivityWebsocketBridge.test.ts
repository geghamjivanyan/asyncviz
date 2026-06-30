import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  executorActivityPayloadFromEnvelope,
  makeExecutorActivitySubscribeFactory,
} from "@/dashboard/executors/hooks/useExecutorActivityWebsocketBridge";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";
import {
  makeHydration,
  makeRecord,
  makeSaturationChanged,
  makeUpdated,
} from "@/dashboard/executors/__fixtures__/executorActivityFixtures";
import type { RuntimeEnvelope } from "@/types/runtime";

const envelope = (payload: unknown): RuntimeEnvelope => ({
  protocol_version: "1",
  type: "runtime_event",
  timestamp: 0,
  payload: payload as Record<string, unknown>,
});

beforeEach(() => {
  useExecutorActivityStore.getState().reset();
});

describe("executorActivityPayloadFromEnvelope", () => {
  it("returns null for non-executor event_type", () => {
    expect(
      executorActivityPayloadFromEnvelope(envelope({ event_type: "asyncio.task.created" })),
    ).toBeNull();
  });

  it("returns the payload for matching event_type", () => {
    const payload = makeUpdated();
    expect(executorActivityPayloadFromEnvelope(envelope(payload))).not.toBeNull();
  });

  it("returns null for empty payloads", () => {
    expect(executorActivityPayloadFromEnvelope(envelope({}))).toBeNull();
  });
});

describe("makeExecutorActivitySubscribeFactory", () => {
  it("forwards matching envelopes to apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeExecutorActivitySubscribeFactory(source)(apply);
    listeners[0](envelope(makeUpdated({ executor_id: "e-77" })));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls[0][0].executor_id).toBe("e-77");
  });

  it("skips non-executor envelopes", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeExecutorActivitySubscribeFactory(source)(apply);
    listeners[0](envelope({ event_type: "asyncio.task.created" }));
    expect(apply).not.toHaveBeenCalled();
  });

  it("integrates end-to-end with the store via apply", () => {
    useExecutorActivityStore
      .getState()
      .hydrateSnapshot(makeHydration({ executors: [makeRecord({ executor_id: "e-1" })] }));
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    makeExecutorActivitySubscribeFactory(source)((payload) =>
      useExecutorActivityStore.getState().applyEventPayload(payload),
    );
    listeners[0](envelope(makeSaturationChanged({ executor_id: "e-1", new_level: "critical" })));
    const state = useExecutorActivityStore.getState();
    expect(state.recordsById["e-1"]?.saturation.level).toBe("critical");
    expect(state.markers).toHaveLength(1);
  });
});
