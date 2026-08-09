"""Schema assembly and the GraphQL error boundary.

Schema-first: the SDL in ``schema/`` is hand-written and is the contract
(ADR 0004). Nothing here may add a type the SDL does not declare — Ariadne
raises at startup if a resolver binds to a field that does not exist, which is
the check that keeps the two honest.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ariadne import (
    EnumType,
    ScalarType,
    load_schema_from_path,
    make_executable_schema,
)
from graphql import GraphQLError

from pollen.components.registry import all_bindables
from pollen.libs.enums import JobStatus, PollenType, Region, RiskLevel
from pollen.libs.errors import AppError

log = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"

datetime_scalar = ScalarType("DateTime")
object_id_scalar = ScalarType("ObjectId")


@datetime_scalar.serializer
def serialize_datetime(value: datetime) -> str:
    return value.isoformat()


@object_id_scalar.serializer
def serialize_object_id(value: Any) -> str:
    return str(value)


def build_schema() -> Any:
    type_defs = load_schema_from_path(str(SCHEMA_DIR))

    return make_executable_schema(
        type_defs,
        *all_bindables(),
        datetime_scalar,
        object_id_scalar,
        # Enum values are bound so an invalid one is rejected at the edge.
        EnumType("RiskLevel", RiskLevel),
        EnumType("PollenType", PollenType),
        EnumType("Region", Region),
        EnumType("JobStatus", JobStatus),
        # Maps camelCase SDL fields onto snake_case Python attributes, so DTOs
        # stay idiomatic Python without an alias on every field.
        # (Ariadne 0.23 replaced snake_case_fallback_resolvers with this flag.)
        convert_names_case=True,
    )


def format_error(error: GraphQLError, debug: bool = False) -> dict[str, Any]:
    """The single place an exception becomes a client-visible GraphQL error.

    Expected domain errors keep their code and message. Everything else is a
    bug: logged in full on the server, returned opaque, so stack traces and
    Mongo internals never reach a public client.
    """
    original = error.original_error

    if isinstance(original, AppError):
        formatted = error.formatted
        formatted["extensions"] = {"code": str(original.code), **original.details}
        return formatted

    if original is not None:
        log.exception("unhandled resolver error", exc_info=original)
        return {
            "message": "Something went wrong on our side.",
            "locations": error.formatted.get("locations"),
            "path": error.formatted.get("path"),
            "extensions": {"code": "INTERNAL_ERROR"},
        }

    # Validation and parse errors carry no original exception and are safe.
    return error.formatted
