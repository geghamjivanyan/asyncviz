/**
 * Typed errors for the runtime store layer.
 */

export class RuntimeStoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RuntimeStoreError";
  }
}

export class HydrationConflictError extends RuntimeStoreError {
  constructor(message: string) {
    super(message);
    this.name = "HydrationConflictError";
  }
}
