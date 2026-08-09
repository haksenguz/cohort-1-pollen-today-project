"""Slice A — Forecast Engine. Owner: Jamshid.

Resolvers stay thin: args in, one service call, DTO out. All logic lives in the
service so it is testable without a GraphQL context.

Argument names are snake_case here even though the SDL declares them camelCase:
``convert_names_case=True`` on the schema converts both field AND argument names.
"""

from __future__ import annotations

from typing import Any

from ariadne import QueryType, SchemaBindable

from pollen.components.forecast.dto import ForecastDTO
from pollen.libs.enums import PollenType, Region

query = QueryType()


@query.field("forecast")
def resolve_forecast(_: Any, info: Any, *, region: Region, pollen_type: PollenType) -> ForecastDTO:
    # Ariadne's EnumType binding means these arrive as enum members already.
    container = info.context["container"]
    return container.forecast.three_day(region, pollen_type)


def forecast_bindables() -> list[SchemaBindable]:
    return [query]
