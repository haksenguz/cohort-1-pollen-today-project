"""Job CLI — run a scheduled job now, without waiting for its cron.

    pollen-job daily-alert

Goes through JobRunner exactly as the scheduler does, so a manual run is
recorded and instrumented identically. That matters for Milestone 2: proving
idempotency means re-running the real job, not a special test path.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from pollen.components.alerts.jobs.daily_alert import DAILY_ALERT_JOB
from pollen.container import build_container
from pollen.db import connect

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

JOBS = {DAILY_ALERT_JOB}


async def _run(job_name: str) -> int:
    container = build_container()
    client = await connect(container.settings.mongodb_uri)
    try:
        await container.runner.run(job_name, container.daily_alert.execute)
    finally:
        await client.close()
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(f"usage: pollen-job <job>\navailable: {', '.join(sorted(JOBS))}\n")
        return 2

    job_name = sys.argv[1]
    if job_name not in JOBS:
        sys.stderr.write(f"unknown job: {job_name}\n")
        return 2

    return asyncio.run(_run(job_name))


if __name__ == "__main__":
    raise SystemExit(main())
