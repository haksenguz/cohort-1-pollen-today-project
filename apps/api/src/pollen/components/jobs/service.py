from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pollen.components.jobs.dto import JobRunDTO, SystemStatusDTO
from pollen.components.jobs.schemas.job_run import JobRunDoc
from pollen.libs.enums import JobStatus

#: A daily job that last succeeded more than 26 hours ago has missed a run.
#: 26 rather than 24 so a late start or a slow run does not raise a false alarm.
STALE_AFTER = timedelta(hours=26)


class JobsService:
    async def status(self, now: datetime | None = None) -> SystemStatusDTO:
        """Newest run per job name, plus whether anything has gone stale."""
        now = now or datetime.now(UTC)

        rows = await JobRunDoc.aggregate(
            [
                {"$sort": {"started_at": -1}},
                {"$group": {"_id": "$job_name", "doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$doc"}},
                {"$sort": {"job_name": 1}},
            ]
        ).to_list()

        jobs = [
            JobRunDTO(
                job_name=r["job_name"],
                started_at=r["started_at"],
                finished_at=r.get("finished_at"),
                status=JobStatus(r["status"]),
                rows_affected=r.get("rows_affected"),
                error=r.get("error"),
            )
            for r in rows
        ]

        stale = any(
            j.status is not JobStatus.SUCCESS or now - _as_aware(j.started_at) > STALE_AFTER
            for j in jobs
        )

        return SystemStatusDTO(jobs=jobs, stale=stale)


def _as_aware(value: datetime) -> datetime:
    """Mongo hands back naive UTC datetimes; comparing those to an aware `now` raises."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
