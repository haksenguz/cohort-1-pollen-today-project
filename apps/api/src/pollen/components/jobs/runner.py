"""Instrumentation wrapper for every scheduled job.

A job that is not recorded is a job nobody can prove ran. Each execution writes
one JobRun document: RUNNING on entry, then SUCCESS or FAILED with the row count
or the error. The status page reads the newest row per job name, and a job that
has not succeeded in 26 hours shows red.

Jobs are deliberately NOT allowed to raise past this boundary — a scheduler that
dies on an unhandled exception stops running every other job too.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pollen.components.jobs.ops_notifier import OpsNotifier
from pollen.components.jobs.schemas.job_run import JobRunDoc
from pollen.libs.enums import JobStatus

log = logging.getLogger(__name__)

#: A job body returns the number of rows it wrote or messages it sent.
JobBody = Callable[[], Awaitable[int]]


class JobRunner:
    def __init__(self, ops: OpsNotifier) -> None:
        self._ops = ops

    async def run(self, job_name: str, body: JobBody) -> None:
        run = JobRunDoc(
            job_name=job_name,
            started_at=datetime.now(UTC),
            status=JobStatus.RUNNING,
        )
        await run.insert()

        try:
            rows = await body()
        except Exception as err:  # noqa: BLE001 — the boundary must swallow everything
            run.finished_at = datetime.now(UTC)
            run.status = JobStatus.FAILED
            run.error = str(err)
            await run.save()

            log.exception("%s: failed", job_name)

            # Failing to tell anyone is worse than the failure. Never let the
            # notifier's own error mask the job's.
            try:
                await self._ops.job_failed(job_name, str(err))
            except Exception:  # noqa: BLE001
                log.exception("ops notify failed for %s", job_name)
            return

        run.finished_at = datetime.now(UTC)
        run.status = JobStatus.SUCCESS
        run.rows_affected = rows
        await run.save()
        log.info("%s: ok, %d rows", job_name, rows)
