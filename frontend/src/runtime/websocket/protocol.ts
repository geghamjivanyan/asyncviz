/**
 * Wire-frame validation + type discrimination.
 *
 * Lives one layer above the raw JSON parse so the transport stays
 * dumb. The validator answers two questions per frame:
 *
 *   1. Is this a well-formed :class:`RuntimeEnvelope`?
 *   2. If so, does its protocol version match what the client speaks?
 *
 * Mismatches are surfaced with structured information so the client
 * can record a counter + emit a debug trace.
 */

import type { EnvelopeType, RuntimeEnvelope } from "@/types/runtime";

export const KNOWN_ENVELOPE_TYPES: ReadonlySet<EnvelopeType> = new Set<EnvelopeType>([
  "heartbeat",
  "system_status",
  "runtime_snapshot",
  "runtime_event",
  "metrics_delta",
  "warning_delta",
  "timeline_delta",
  "protocol_error",
  "replay_status",
]);

export type ParseOutcome =
  | { kind: "ok"; envelope: RuntimeEnvelope }
  | { kind: "invalid-json"; message: string }
  | { kind: "invalid-shape"; message: string }
  | { kind: "unknown-type"; type: string }
  | { kind: "protocol-mismatch"; received: string; expected: string };

export interface ProtocolOptions {
  /** Frontend's expected protocol version. */
  expectedProtocolVersion: string;
  /** Whether to relax the version check (test harness override). */
  allowAnyProtocolVersion?: boolean;
}

export function parseEnvelope(raw: string, options: ProtocolOptions): ParseOutcome {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return { kind: "invalid-json", message: (err as Error).message };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { kind: "invalid-shape", message: "envelope must be a JSON object" };
  }
  const candidate = parsed as Record<string, unknown>;
  const type = candidate.type;
  const payload = candidate.payload;
  const protocolVersion = candidate.protocol_version;
  if (typeof type !== "string") {
    return { kind: "invalid-shape", message: "missing or invalid 'type' field" };
  }
  if (payload === undefined || payload === null || typeof payload !== "object") {
    return { kind: "invalid-shape", message: "missing or invalid 'payload' field" };
  }
  if (typeof protocolVersion !== "string") {
    return { kind: "invalid-shape", message: "missing or invalid 'protocol_version' field" };
  }
  if (!KNOWN_ENVELOPE_TYPES.has(type as EnvelopeType)) {
    return { kind: "unknown-type", type };
  }
  if (
    options.allowAnyProtocolVersion !== true &&
    protocolVersion !== options.expectedProtocolVersion
  ) {
    return {
      kind: "protocol-mismatch",
      received: protocolVersion,
      expected: options.expectedProtocolVersion,
    };
  }
  return { kind: "ok", envelope: parsed as RuntimeEnvelope };
}
