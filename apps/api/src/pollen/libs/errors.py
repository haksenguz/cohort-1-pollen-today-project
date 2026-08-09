"""Domain errors.

Every error this application raises on purpose carries a stable machine-readable
``code``. Clients switch on the code; the message is for humans and may change.

Anything that is NOT an ``AppError`` is a bug, and the GraphQL error formatter
hides its detail rather than leaking internals to a public client.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    BAD_INPUT = "BAD_INPUT"
    NOT_FOUND = "NOT_FOUND"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    DUPLICATE_DELIVERY = "DUPLICATE_DELIVERY"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


class AppError(Exception):
    """Base class for every deliberate failure. Safe to show a user."""

    code: ErrorCode

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BadInputError(AppError):
    code = ErrorCode.BAD_INPUT


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class UpstreamUnavailableError(AppError):
    """KMA is down, or Telegram rejected the send. Not our bug, not the user's."""

    code = ErrorCode.UPSTREAM_UNAVAILABLE


class DuplicateDeliveryError(AppError):
    """The unique index refused a duplicate. Normal on a re-run — see ADR 0003."""

    code = ErrorCode.DUPLICATE_DELIVERY


class ContractViolationError(AppError):
    """External data failed its Pydantic model. Always a bug somewhere."""

    code = ErrorCode.CONTRACT_VIOLATION
