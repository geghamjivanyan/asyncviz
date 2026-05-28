import { describe, expect, it } from "vitest";
import { KNOWN_ENVELOPE_TYPES, parseEnvelope } from "@/runtime/websocket/protocol";

const options = { expectedProtocolVersion: "1.0" };

describe("parseEnvelope", () => {
  it("accepts a well-formed envelope", () => {
    const raw = JSON.stringify({
      protocol_version: "1.0",
      type: "heartbeat",
      timestamp: 0,
      sequence: null,
      payload: { server_uptime_seconds: 1, connected_clients: 0 },
    });
    const outcome = parseEnvelope(raw, options);
    expect(outcome.kind).toBe("ok");
    if (outcome.kind === "ok") {
      expect(outcome.envelope.type).toBe("heartbeat");
    }
  });

  it("rejects invalid JSON", () => {
    expect(parseEnvelope("{not json", options).kind).toBe("invalid-json");
  });

  it("rejects non-object roots", () => {
    expect(parseEnvelope("[1,2,3]", options).kind).toBe("invalid-shape");
    expect(parseEnvelope("123", options).kind).toBe("invalid-shape");
    expect(parseEnvelope("null", options).kind).toBe("invalid-shape");
  });

  it("rejects missing fields", () => {
    expect(parseEnvelope("{}", options).kind).toBe("invalid-shape");
    expect(
      parseEnvelope(JSON.stringify({ protocol_version: "1.0", type: "heartbeat" }), options).kind,
    ).toBe("invalid-shape");
  });

  it("rejects unknown envelope types", () => {
    const raw = JSON.stringify({
      protocol_version: "1.0",
      type: "wat",
      payload: {},
    });
    const outcome = parseEnvelope(raw, options);
    expect(outcome.kind).toBe("unknown-type");
    if (outcome.kind === "unknown-type") {
      expect(outcome.type).toBe("wat");
    }
  });

  it("flags protocol version mismatches", () => {
    const raw = JSON.stringify({
      protocol_version: "9.9",
      type: "heartbeat",
      payload: {},
    });
    const outcome = parseEnvelope(raw, options);
    expect(outcome.kind).toBe("protocol-mismatch");
    if (outcome.kind === "protocol-mismatch") {
      expect(outcome.received).toBe("9.9");
      expect(outcome.expected).toBe("1.0");
    }
  });

  it("relaxes the version check when allowAnyProtocolVersion is true", () => {
    const raw = JSON.stringify({
      protocol_version: "9.9",
      type: "heartbeat",
      payload: {},
    });
    const outcome = parseEnvelope(raw, { ...options, allowAnyProtocolVersion: true });
    expect(outcome.kind).toBe("ok");
  });

  it("exposes the canonical envelope-type set", () => {
    for (const t of [
      "heartbeat",
      "system_status",
      "runtime_snapshot",
      "runtime_event",
      "metrics_delta",
      "warning_delta",
      "timeline_delta",
      "protocol_error",
    ] as const) {
      expect(KNOWN_ENVELOPE_TYPES.has(t)).toBe(true);
    }
  });
});
