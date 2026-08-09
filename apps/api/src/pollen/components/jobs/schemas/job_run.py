"""Persistence model for scheduled job runs.

Deliberately separate from the GraphQL types — the shape we store and the shape
we expose are allowed to diverge, and coupling them makes both harder to change.
"""

from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document

from pollen.libs.enums import JobStatus


class JobRunDoc(Document):
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: JobStatus
    rows_affected: int | None = None
    error: str | None = None

    class Settings:
        name = "job_runs"
        indexes = [
            pymongo.IndexModel(
                [("job_name", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)],
                name="job_name_started_at",
            ),
        ]
