"""Slice C — Alerts & Delivery. Owner: Ismoiljon.

Backs the public alert-history page.
"""

from __future__ import annotations

from typing import Any

from ariadne import QueryType, SchemaBindable

from pollen.components.alerts.dto import PaginatedAlertDTO
from pollen.libs.enums import Region

query = QueryType()


@query.field("alertHistory")
async def resolve_alert_history(
    _: Any,
    info: Any,
    *,
    limit: int,
    offset: int,
    region: Region | None = None,
) -> PaginatedAlertDTO:
    container = info.context["container"]
    return await container.alerts.history(region, limit, offset)


def alerts_bindables() -> list[SchemaBindable]:
    return [query]
