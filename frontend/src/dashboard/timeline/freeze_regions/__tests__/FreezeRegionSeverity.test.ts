import { describe, expect, it } from "vitest";
import {
  compareFreezeKeys,
  intentForFreeze,
  isTerminalState,
  lifecycleForState,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionSeverity";

describe("severity helpers", () => {
  it("isTerminalState identifies terminal states", () => {
    expect(isTerminalState("recovered")).toBe(true);
    expect(isTerminalState("expired")).toBe(true);
    expect(isTerminalState("active")).toBe(false);
    expect(isTerminalState("opened")).toBe(false);
    expect(isTerminalState("escalating")).toBe(false);
  });

  it("lifecycleForState collapses terminal → recovered, else active", () => {
    expect(lifecycleForState("recovered")).toBe("recovered");
    expect(lifecycleForState("expired")).toBe("recovered");
    expect(lifecycleForState("opened")).toBe("active");
    expect(lifecycleForState("active")).toBe("active");
    expect(lifecycleForState("escalating")).toBe("active");
  });

  it("intentForFreeze folds terminal states to resolved", () => {
    expect(intentForFreeze("FREEZE", "recovered")).toBe("resolved");
    expect(intentForFreeze("CRITICAL", "expired")).toBe("resolved");
  });

  it("intentForFreeze maps severity to intent for open states", () => {
    expect(intentForFreeze("FREEZE", "active")).toBe("freeze");
    expect(intentForFreeze("CRITICAL", "active")).toBe("critical");
    expect(intentForFreeze("WARNING", "active")).toBe("warning");
    expect(intentForFreeze("NONE", "active")).toBe("warning");
  });
});

describe("compareFreezeKeys", () => {
  it("orders active before recovered", () => {
    const result = compareFreezeKeys(
      { lifecycle: "active", severity: "WARNING", firstSeenNs: 5 },
      { lifecycle: "recovered", severity: "FREEZE", firstSeenNs: 1 },
    );
    expect(result).toBeLessThan(0);
  });

  it("orders higher severity first within the same bucket", () => {
    const result = compareFreezeKeys(
      { lifecycle: "active", severity: "WARNING", firstSeenNs: 5 },
      { lifecycle: "active", severity: "FREEZE", firstSeenNs: 5 },
    );
    expect(result).toBeGreaterThan(0);
  });

  it("breaks ties on firstSeenNs (ascending)", () => {
    const result = compareFreezeKeys(
      { lifecycle: "active", severity: "FREEZE", firstSeenNs: 10 },
      { lifecycle: "active", severity: "FREEZE", firstSeenNs: 20 },
    );
    expect(result).toBeLessThan(0);
  });
});
