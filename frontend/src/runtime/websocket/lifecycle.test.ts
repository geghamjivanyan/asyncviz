import { describe, expect, it } from "vitest";
import {
  isConnectingPhase,
  isLivePhase,
  isTerminalPhase,
  phaseRank,
  toConnectionState,
} from "@/runtime/websocket/lifecycle";

describe("ConnectionPhase helpers", () => {
  it("isTerminalPhase distinguishes terminal vs. transient", () => {
    expect(isTerminalPhase("disconnected")).toBe(true);
    expect(isTerminalPhase("failed")).toBe(true);
    expect(isTerminalPhase("live")).toBe(false);
    expect(isTerminalPhase("idle")).toBe(false);
  });

  it("isLivePhase covers live + replaying", () => {
    expect(isLivePhase("live")).toBe(true);
    expect(isLivePhase("replaying")).toBe(true);
    expect(isLivePhase("connecting")).toBe(false);
  });

  it("isConnectingPhase covers hydrating + connecting + reconnecting", () => {
    expect(isConnectingPhase("hydrating")).toBe(true);
    expect(isConnectingPhase("connecting")).toBe(true);
    expect(isConnectingPhase("reconnecting")).toBe(true);
    expect(isConnectingPhase("live")).toBe(false);
  });

  it("phaseRank is monotonic through the happy path", () => {
    const happy = ["idle", "hydrating", "connecting", "replaying", "live"] as const;
    const ranks = happy.map(phaseRank);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
  });

  it("toConnectionState projects every phase to the legacy enum", () => {
    expect(toConnectionState("idle")).toBe("idle");
    expect(toConnectionState("disconnected")).toBe("idle");
    expect(toConnectionState("hydrating")).toBe("connecting");
    expect(toConnectionState("reconnecting")).toBe("connecting");
    expect(toConnectionState("connecting")).toBe("connecting");
    expect(toConnectionState("replaying")).toBe("open");
    expect(toConnectionState("live")).toBe("open");
    expect(toConnectionState("failed")).toBe("error");
  });
});
