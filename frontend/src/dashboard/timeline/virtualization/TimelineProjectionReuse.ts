/**
 * Projection-reuse helpers.
 *
 * Many consumers project the runtime store into multiple shapes
 * (rows, segments, lifecycle entries). The reuse helpers compute a
 * stable signature for a projection and decide whether a downstream
 * view can reuse its memoized output.
 *
 * Today the helpers wrap simple ``===`` / sequence comparisons; the
 * surface is shaped so future hash-based equivalence (e.g.
 * structural hashes for tiny edits) can land without rewriting
 * callers.
 */

export interface ReusableProjectionSignature {
  /** Number of items in the projection. */
  length: number;
  /** Sequence cursor when the projection was built. */
  sequence: number;
}

export function projectionSignature(length: number, sequence: number): ReusableProjectionSignature {
  return { length, sequence };
}

export function signatureEquals(
  a: ReusableProjectionSignature | null,
  b: ReusableProjectionSignature | null,
): boolean {
  if (a === null || b === null) return false;
  return a.length === b.length && a.sequence === b.sequence;
}
