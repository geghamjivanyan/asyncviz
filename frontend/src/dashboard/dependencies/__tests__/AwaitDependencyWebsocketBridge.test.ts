import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  gatherPayloadFromEnvelope,
  makeAwaitDependencySubscribeFactory,
} from "@/dashboard/dependencies/hooks/useAwaitDependencyWebsocketBridge";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";
import {
  makeGatherCompleted,
  makeGatherCreated,
} from "@/dashboard/dependencies/__fixtures__/awaitDependencyFixtures";
import type { RuntimeEnvelope } from "@/types/runtime";

const envelope = (payload: unknown): RuntimeEnvelope => ({
  protocol_version: "1",
  type: "runtime_event",
  timestamp: 0,
  payload: payload as Record<string, unknown>,
});

beforeEach(() => {
  useAwaitDependencyStore.getState().reset();
});

describe("gatherPayloadFromEnvelope", () => {
  it("returns null for non-gather event_type", () => {
    expect(
      gatherPayloadFromEnvelope(envelope({ event_type: "asyncio.task.created" })),
    ).toBeNull();
  });

  it("returns the payload for matching event_type", () => {
    const payload = makeGatherCreated();
    expect(gatherPayloadFromEnvelope(envelope(payload))).not.toBeNull();
  });

  it("returns null for empty payloads", () => {
    expect(gatherPayloadFromEnvelope(envelope({}))).toBeNull();
  });
});

describe("makeAwaitDependencySubscribeFactory", () => {
  it("forwards matching envelopes to apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(
        _filter: "runtime_event",
        listener: (envelope: RuntimeEnvelope) => void,
      ) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeAwaitDependencySubscribeFactory(source)(apply);
    listeners[0](envelope(makeGatherCreated({ gather_id: "g-77" })));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls[0][0].gather_id).toBe("g-77");
  });

  it("skips non-gather envelopes", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(
        _filter: "runtime_event",
        listener: (envelope: RuntimeEnvelope) => void,
      ) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeAwaitDependencySubscribeFactory(source)(apply);
    listeners[0](envelope({ event_type: "asyncio.task.created" }));
    expect(apply).not.toHaveBeenCalled();
  });

  it("integrates end-to-end with the store via apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(
        _filter: "runtime_event",
        listener: (envelope: RuntimeEnvelope) => void,
      ) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    makeAwaitDependencySubscribeFactory(source)((payload) =>
      useAwaitDependencyStore.getState().applyEventPayload(payload),
    );
    listeners[0](
      envelope(
        makeGatherCreated({ gather_id: "g-1", child_task_ids: ["t-a"] }),
      ),
    );
    listeners[0](envelope(makeGatherCompleted({ gather_id: "g-1" })));
    const state = useAwaitDependencyStore.getState();
    expect(state.nodesById["g-1"]?.state).toBe("completed");
  });
});
