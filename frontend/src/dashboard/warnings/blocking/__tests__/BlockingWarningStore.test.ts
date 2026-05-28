import { beforeEach, describe, expect, it } from "vitest";
import {
  BLOCKING_WARNING_EVENT_TYPES,
  countActiveBySeverity,
  reduceEvent,
  reduceHydration,
  useBlockingWarningStore,
} from "@/dashboard/warnings/blocking/BlockingWarningStore";
import {
  makeEvent,
  makeGroup,
  makeSnapshot,
} from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

describe("BlockingWarningStore — pure reducers", () => {
  it("hydrates active and recent buckets distinctly", () => {
    const snapshot = makeSnapshot();
    const result = reduceHydration(snapshot);
    expect(result.activeIds).toEqual(["grp-1"]);
    expect(result.recentIds).toEqual(["grp-2"]);
    expect(Object.keys(result.groupsById)).toEqual(["grp-1", "grp-2"]);
  });

  it("applies a fresh event and indexes the new group", () => {
    const event = makeEvent({ group_id: "new", sequence: 5, state: "opened" });
    const outcome = reduceEvent(
      { groupsById: {}, activeIds: [], recentIds: [], selectedGroupId: null, lastSequence: 0 },
      event,
    );
    expect(outcome.kind).toBe("applied");
    expect(outcome.next.activeIds).toEqual(["new"]);
    expect(outcome.lastSequence).toBe(5);
  });

  it("drops stale events whose sequence ≤ lastSequence", () => {
    const event = makeEvent({ sequence: 2 });
    const outcome = reduceEvent(
      { groupsById: {}, activeIds: [], recentIds: [], selectedGroupId: null, lastSequence: 5 },
      event,
    );
    expect(outcome.kind).toBe("stale");
    expect(outcome.next.activeIds).toEqual([]);
  });

  it("drops duplicate events with same state + last_seen_ns", () => {
    const group = makeGroup();
    const event = makeEvent({
      sequence: 3,
      state: group.state,
      last_seen_ns: group.last_seen_ns,
    });
    const outcome = reduceEvent(
      {
        groupsById: { [group.group_id]: group },
        activeIds: [group.group_id],
        recentIds: [],
        selectedGroupId: null,
        lastSequence: 2,
      },
      event,
    );
    expect(outcome.kind).toBe("duplicate");
    expect(outcome.lastSequence).toBe(3);
  });

  it("moves a group from active to recent on terminal transition", () => {
    const group = makeGroup();
    const recovered = makeEvent({
      sequence: 9,
      state: "recovered",
      recovered_ns: group.last_seen_ns + 1,
      last_seen_ns: group.last_seen_ns + 1,
    });
    const outcome = reduceEvent(
      {
        groupsById: { [group.group_id]: group },
        activeIds: [group.group_id],
        recentIds: [],
        selectedGroupId: null,
        lastSequence: 0,
      },
      recovered,
    );
    expect(outcome.kind).toBe("applied");
    expect(outcome.next.activeIds).toEqual([]);
    expect(outcome.next.recentIds).toEqual([group.group_id]);
  });

  it("re-opens a group: moves it back to active when state becomes non-terminal", () => {
    const group = makeGroup({ state: "recovered" });
    const reopened = makeEvent({
      sequence: 11,
      state: "active",
      last_seen_ns: group.last_seen_ns + 100,
    });
    const outcome = reduceEvent(
      {
        groupsById: { [group.group_id]: group },
        activeIds: [],
        recentIds: [group.group_id],
        selectedGroupId: null,
        lastSequence: 5,
      },
      reopened,
    );
    expect(outcome.kind).toBe("applied");
    expect(outcome.next.activeIds).toEqual([group.group_id]);
    expect(outcome.next.recentIds).toEqual([]);
  });
});

describe("BlockingWarningStore — zustand actions", () => {
  beforeEach(() => {
    useBlockingWarningStore.getState().reset();
  });

  it("hydrateSnapshot folds snapshot into state and marks ready", () => {
    useBlockingWarningStore.getState().hydrateSnapshot(makeSnapshot());
    const state = useBlockingWarningStore.getState();
    expect(state.status).toBe("ready");
    expect(state.runtimeId).toBe("rt-1");
    expect(state.activeIds).toEqual(["grp-1"]);
    expect(state.recentIds).toEqual(["grp-2"]);
    expect(state.stats.hydrationsApplied).toBe(1);
  });

  it("applyEventPayload counts duplicates + stales correctly", () => {
    const store = useBlockingWarningStore.getState();
    store.applyEventPayload(makeEvent({ sequence: 5 }));
    store.applyEventPayload(
      makeEvent({ sequence: 5, last_seen_ns: makeGroup().last_seen_ns }),
    );
    store.applyEventPayload(makeEvent({ sequence: 2 }));
    const after = useBlockingWarningStore.getState();
    expect(after.stats.eventsApplied).toBe(1);
    // Duplicate by sequence-equality OR by (state, last_seen_ns) match.
    expect(after.stats.duplicatesDropped + after.stats.staleDropped).toBeGreaterThanOrEqual(2);
  });

  it("setFilterMode rebuilds the filter from the mode", () => {
    useBlockingWarningStore.getState().setFilterMode("freeze-only");
    expect(useBlockingWarningStore.getState().filter.severities).not.toBeNull();
    expect(
      useBlockingWarningStore.getState().filter.severities?.has("FREEZE"),
    ).toBe(true);
  });

  it("countActiveBySeverity counts only active ids", () => {
    useBlockingWarningStore.getState().hydrateSnapshot(makeSnapshot());
    const state = useBlockingWarningStore.getState();
    expect(countActiveBySeverity(state).CRITICAL).toBe(1);
    expect(countActiveBySeverity(state).WARNING).toBe(0);
  });
});

describe("BlockingWarningStore — event-type taxonomy", () => {
  it("exposes one wire type per lifecycle transition", () => {
    expect(BLOCKING_WARNING_EVENT_TYPES).toEqual([
      "runtime.warnings.blocking.opened",
      "runtime.warnings.blocking.escalated",
      "runtime.warnings.blocking.active",
      "runtime.warnings.blocking.recovered",
      "runtime.warnings.blocking.expired",
    ]);
  });
});
