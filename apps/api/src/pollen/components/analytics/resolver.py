"""Slice B — Season Analytics. Owner: Giyos.

Giyos replaces the service body; the SDL and this resolver stay frozen.
"""

from __future__ import annotations

from typing import Any

from ariadne import QueryType, SchemaBindable

from pollen.components.analytics.dto import SeasonTimingDTO
from pollen.libs.enums import PollenType, Region

query = QueryType()


@query.field("seasonTiming")
def resolve_season_timing(
    _: Any, info: Any, *, region: Region, pollen_type: PollenType
) -> SeasonTimingDTO:
    container = info.context["container"]
    return container.analytics.season_timing(region, pollen_type)


def analytics_bindables() -> list[SchemaBindable]:
    return [query]
