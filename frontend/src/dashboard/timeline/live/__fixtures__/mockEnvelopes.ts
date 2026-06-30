/**
 * Envelope builders for live-engine tests. Mirrors the on-wire shape
 * exactly so the delta processor exercises the real branches.
 */

import type {
  RuntimeEnvelope,
  TimelineDeltaPayload,
  TimelineSegment,
  WarningDeltaPayload,
} from "@/types/runtime";

export function makeTimelineDeltaEnvelope(args: {
  sequence: number;
  taskId: string;
  segmentId?: string;
  kind?: TimelineDeltaPayload["kind"];
  segment?: TimelineSegment;
}): RuntimeEnvelope {
  const payload: TimelineDeltaPayload = {
    kind: args.kind ?? "segment_closed",
    task_id: args.taskId,
    sequence: args.sequence,
    monotonic_ns: args.sequence * 1_000_000,
    wall_seconds: 0,
    closed_a_segment: args.kind === "segment_closed",
    segment: args.segment,
    open_segment:
      args.kind === "segment_opened"
        ? {
            task_id: args.taskId,
            segment_id: args.segmentId ?? `${args.taskId}-active`,
            segment_type: "run",
            sequence_start: args.sequence,
            monotonic_start_ns: args.sequence * 1_000_000,
            wall_start: 0,
            state: "running",
            parent_task_id: null,
            coroutine_name: null,
            task_name: null,
          }
        : undefined,
  };
  return {
    protocol_version: "1",
    type: "timeline_delta",
    timestamp: 0,
    sequence: args.sequence,
    payload: payload as unknown as Record<string, unknown>,
  };
}

export function makeWarningDeltaEnvelope(args: {
  sequence: number;
  warningId: string;
  taskIds: string[];
}): RuntimeEnvelope {
  const payload: WarningDeltaPayload = {
    change: "activated",
    sequence: args.sequence,
    last_sequence: args.sequence,
    warning: {
      warning_id: args.warningId,
      warning_key: args.warningId,
      warning_type: "test",
      severity: "warning",
      message: "warn",
      detector: "test",
      created_sequence: args.sequence,
      created_monotonic_ns: 0,
      created_at_wall: 0,
      last_observed_sequence: args.sequence,
      last_observed_monotonic_ns: 0,
      last_observed_wall: 0,
      occurrence_count: 1,
      resolved: false,
      resolved_sequence: null,
      resolved_monotonic_ns: null,
      resolved_at_wall: null,
      expired: false,
      related_task_ids: args.taskIds,
      lineage_root_id: null,
      metadata: {},
      runtime_id: "rt",
    },
  };
  return {
    protocol_version: "1",
    type: "warning_delta",
    timestamp: 0,
    sequence: args.sequence,
    payload: payload as unknown as Record<string, unknown>,
  };
}

export function makeRuntimeEventEnvelope(sequence: number, taskId: string): RuntimeEnvelope {
  return {
    protocol_version: "1",
    type: "runtime_event",
    timestamp: 0,
    sequence,
    payload: {
      event_id: `evt-${sequence}`,
      event_type: "asyncio.task.started",
      timestamp: 0,
      monotonic_timestamp: 0,
      monotonic_ns: sequence * 1_000_000,
      runtime_id: "rt",
      source: "test",
      payload_version: 1,
      task_id: taskId,
      parent_task_id: null,
      coroutine_name: "fn",
      task_name: null,
      metadata: {},
    },
  };
}

export function makeHeartbeatEnvelope(): RuntimeEnvelope {
  return {
    protocol_version: "1",
    type: "heartbeat",
    timestamp: 0,
    sequence: null,
    payload: { server_uptime_seconds: 1, connected_clients: 1 },
  };
}
