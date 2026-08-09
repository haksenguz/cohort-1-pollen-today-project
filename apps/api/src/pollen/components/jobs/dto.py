"""Job instrumentation read types. Source of truth: schema/jobs.graphql."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from pollen.libs.enums import JobStatus


class JobRunDTO(BaseModel):
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: JobStatus
    rows_affected: int | None = None
    error: str | None = None


class SystemStatusDTO(BaseModel):
    jobs: list[JobRunDTO]
    stale: bool
