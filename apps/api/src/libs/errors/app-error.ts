/**
 * Domain errors.
 *
 * Every error this application raises on purpose carries a stable machine
 * -readable `code`. Clients switch on the code; the message is for humans and
 * may change. Anything that is *not* an AppError is a bug, and the error filter
 * deliberately hides its detail rather than leaking internals to the client.
 */

export const ERROR_CODES = {
  BAD_INPUT: "BAD_INPUT",
  NOT_FOUND: "NOT_FOUND",
  UPSTREAM_UNAVAILABLE: "UPSTREAM_UNAVAILABLE",
  DUPLICATE_DELIVERY: "DUPLICATE_DELIVERY",
  CONTRACT_VIOLATION: "CONTRACT_VIOLATION",
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

export abstract class AppError extends Error {
  abstract readonly code: ErrorCode;
  /** Safe to show a user. Bugs are never safe. */
  readonly expected = true;

  constructor(
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = new.target.name;
    Error.captureStackTrace?.(this, new.target);
  }
}

export class BadInputError extends AppError {
  readonly code = ERROR_CODES.BAD_INPUT;
}

export class NotFoundError extends AppError {
  readonly code = ERROR_CODES.NOT_FOUND;

  constructor(what: string, id?: string) {
    super(id ? `${what} not found: ${id}` : `${what} not found`, { what, id });
  }
}

/** KMA is down, or Telegram rejected the send. Not our bug, not the user's. */
export class UpstreamUnavailableError extends AppError {
  readonly code = ERROR_CODES.UPSTREAM_UNAVAILABLE;
}

/** The unique index refused a duplicate. Normal on a re-run — see ADR 0003. */
export class DuplicateDeliveryError extends AppError {
  readonly code = ERROR_CODES.DUPLICATE_DELIVERY;
}

/** Data crossed a boundary and failed its Zod schema. Always a bug somewhere. */
export class ContractViolationError extends AppError {
  readonly code = ERROR_CODES.CONTRACT_VIOLATION;
}

export function isAppError(err: unknown): err is AppError {
  return err instanceof AppError;
}
