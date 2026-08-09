"""Job instrumentation. Owner: Ismoiljon (Slice C)."""

from __future__ import annotations

from typing import Any

from ariadne import QueryType, SchemaBindable

from pollen.components.jobs.dto import SystemStatusDTO

query = QueryType()


@query.field("systemStatus")
async def resolve_system_status(_: Any, info: Any) -> SystemStatusDTO:
    container = info.context["container"]
    return await container.jobs.status()


def jobs_bindables() -> list[SchemaBindable]:
    return [query]
