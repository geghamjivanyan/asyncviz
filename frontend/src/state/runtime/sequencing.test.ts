import { describe, expect, it } from "vitest";
import { decideStoreSequence, maxSequence } from "@/state/runtime/sequencing";
import type { RuntimeEnvelope } from "@/types/runtime";

function envelope(sequence: number | null): RuntimeEnvelope {
  return {
    protocol_version: "1.0",
    type: "runtime_event",
    timestamp: 0,
    sequence,
    payload: {},
  };
}

describe("decideStoreSequence", () => {
  it("accepts envelopes one ahead of the cursor", () => {
    expect(decideStoreSequence(envelope(6), 5)).toBe("accept");
  });

  it("flags equal sequences as duplicates", () => {
    expect(decideStoreSequence(envelope(5), 5)).toBe("duplicate");
  });

  it("flags lower sequences as stale", () => {
    expect(decideStoreSequence(envelope(3), 5)).toBe("stale");
  });

  it("flags gaps as out-of-order", () => {
    expect(decideStoreSequence(envelope(10), 5)).toBe("out-of-order");
  });

  it("accepts null sequences (unsequenced)", () => {
    expect(decideStoreSequence(envelope(null), 5)).toBe("accept");
  });
});

describe("maxSequence", () => {
  it("returns the higher of two values", () => {
    expect(maxSequence(3, 7)).toBe(7);
    expect(maxSequence(7, 3)).toBe(7);
  });

  it("treats null/undefined as no-op", () => {
    expect(maxSequence(5, null)).toBe(5);
    expect(maxSequence(5, undefined)).toBe(5);
  });
});
