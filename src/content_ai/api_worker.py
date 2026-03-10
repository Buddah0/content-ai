from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import select, update

from content_ai.api.db_models import Job, JobStatus
from content_ai.api.main import database, process_job_task

WORKER_POLL_INTERVAL_S = float(os.getenv("WORKER_POLL_INTERVAL_S", "1.0"))


@asynccontextmanager
async def lifespan():
    await database.connect()
    yield
    await database.disconnect()


def _extract_resolved_settings(settings_json: str | None) -> dict | None:
    if not settings_json:
        return None
    try:
        payload = json.loads(settings_json)
        if isinstance(payload, dict):
            resolved = payload.get("resolved_config")
            if isinstance(resolved, dict):
                return resolved
    except json.JSONDecodeError:
        return None
    return None


async def claim_next_pending_job_id() -> str | None:
    query = select(Job).where(Job.status == JobStatus.PENDING).order_by(Job.createdAt.asc())
    job = await database.fetch_one(query)
    if not job:
        return None

    # Mark as QUEUED before processing so another poll cycle does not pick it again.
    await database.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(status=JobStatus.QUEUED, updatedAt=datetime.now(timezone.utc))
    )
    return job.id


async def run_worker_loop() -> None:
    while True:
        job_id = await claim_next_pending_job_id()
        if not job_id:
            await asyncio.sleep(WORKER_POLL_INTERVAL_S)
            continue

        job_row = await database.fetch_one(select(Job).where(Job.id == job_id))
        settings = _extract_resolved_settings(job_row.settings if job_row else None)
        await process_job_task(job_id, settings)


async def main() -> None:
    async with lifespan():
        await run_worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
