import { describe, expect, it } from "vitest";
import {
  projectionSignature,
  signatureEquals,
} from "@/dashboard/timeline/virtualization/TimelineProjectionReuse";

describe("TimelineProjectionReuse", () => {
  it("emits a signature object with length + sequence", () => {
    const sig = projectionSignature(42, 7);
    expect(sig.length).toBe(42);
    expect(sig.sequence).toBe(7);
  });

  it("signatureEquals returns false when either side is null", () => {
    expect(signatureEquals(null, projectionSignature(1, 1))).toBe(false);
    expect(signatureEquals(projectionSignature(1, 1), null)).toBe(false);
  });

  it("signatureEquals returns true on matching length + sequence", () => {
    expect(signatureEquals(projectionSignature(5, 3), projectionSignature(5, 3))).toBe(true);
  });

  it("signatureEquals returns false on mismatched length or sequence", () => {
    expect(signatureEquals(projectionSignature(5, 3), projectionSignature(6, 3))).toBe(false);
    expect(signatureEquals(projectionSignature(5, 3), projectionSignature(5, 4))).toBe(false);
  });
});
