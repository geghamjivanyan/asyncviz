/**
 * Typed envelope-subscription registry.
 *
 * Components subscribe to one envelope type (``"metrics_delta"``,
 * ``"warning_delta"``, ...) or to the wildcard ``"*"`` for raw access.
 * The registry serves the subscription set per envelope-type so the
 * fast path doesn't iterate over irrelevant listeners on every frame.
 *
 * The contract is intentionally narrow:
 *
 *   * One-shot envelopes — no replay buffering by the registry; the
 *     websocket client owns ordering.
 *   * Exception-safe — a misbehaving listener is logged + skipped;
 *     other listeners still fire.
 */

import type { EnvelopeType, RuntimeEnvelope } from "@/types/runtime";

export type SubscriptionFilter = EnvelopeType | "*";

export type EnvelopeListener = (envelope: RuntimeEnvelope) => void;

export interface Subscription {
  unsubscribe(): void;
}

interface InternalSubscription {
  filter: SubscriptionFilter;
  listener: EnvelopeListener;
}

export class SubscriptionRegistry {
  private _subscriptions = new Set<InternalSubscription>();
  private _byFilter = new Map<SubscriptionFilter, Set<InternalSubscription>>();
  private _errors = 0;

  add(filter: SubscriptionFilter, listener: EnvelopeListener): Subscription {
    const entry: InternalSubscription = { filter, listener };
    this._subscriptions.add(entry);
    let bucket = this._byFilter.get(filter);
    if (bucket === undefined) {
      bucket = new Set<InternalSubscription>();
      this._byFilter.set(filter, bucket);
    }
    bucket.add(entry);
    return {
      unsubscribe: () => {
        if (!this._subscriptions.delete(entry)) return;
        const b = this._byFilter.get(filter);
        b?.delete(entry);
        if (b !== undefined && b.size === 0) {
          this._byFilter.delete(filter);
        }
      },
    };
  }

  /** Fan out one envelope to every matching subscription. */
  emit(envelope: RuntimeEnvelope): void {
    const wildcard = this._byFilter.get("*");
    const typed = this._byFilter.get(envelope.type);
    if (wildcard !== undefined) {
      for (const entry of wildcard) this._invoke(entry.listener, envelope);
    }
    if (typed !== undefined) {
      for (const entry of typed) this._invoke(entry.listener, envelope);
    }
  }

  private _invoke(listener: EnvelopeListener, envelope: RuntimeEnvelope): void {
    try {
      listener(envelope);
    } catch (err) {
      this._errors += 1;
      console.error("subscription listener threw on", envelope.type, err);
    }
  }

  size(): number {
    return this._subscriptions.size;
  }

  sizeFor(filter: SubscriptionFilter): number {
    return this._byFilter.get(filter)?.size ?? 0;
  }

  errors(): number {
    return this._errors;
  }

  clear(): void {
    this._subscriptions.clear();
    this._byFilter.clear();
    this._errors = 0;
  }
}
