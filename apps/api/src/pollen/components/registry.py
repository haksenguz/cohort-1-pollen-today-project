"""The single aggregate of every feature component.

`main.py` imports this and nothing else from the feature side, so adding a
component means touching one list here rather than editing the app factory —
which is the file three people are most likely to conflict on.

This is the Python counterpart of the NestJS ComponentsModule.
"""

from __future__ import annotations

from ariadne import SchemaBindable
from beanie import Document

from pollen.components.alerts.resolver import alerts_bindables
from pollen.components.alerts.schemas.alert import AlertDoc
from pollen.components.analytics.resolver import analytics_bindables
from pollen.components.forecast.resolver import forecast_bindables
from pollen.components.jobs.resolver import jobs_bindables
from pollen.components.jobs.schemas.job_run import JobRunDoc


def all_bindables() -> list[SchemaBindable]:
    """Every component's GraphQL resolvers, in one list."""
    return [
        *forecast_bindables(),
        *analytics_bindables(),
        *alerts_bindables(),
        *jobs_bindables(),
    ]


def all_documents() -> list[type[Document]]:
    """Every Beanie document, so init_beanie registers the indexes."""
    return [AlertDoc, JobRunDoc]
