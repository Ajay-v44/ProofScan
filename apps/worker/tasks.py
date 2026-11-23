import asyncio

from celery import Celery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from proofscan.config import settings
from proofscan.db import Evidence, Verification, database, now
from proofscan.domain import TRANSITIONS, Status
from proofscan.handoff_models import Checkpoint
from proofscan.services import advance

celery = Celery("proofscan", broker=settings().redis_url)
celery.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "expire-verifications": {"task": "proofscan.expire_verifications", "schedule": 60.0},
        "expire-evidence": {"task": "proofscan.expire_evidence", "schedule": 3600.0},
    },
)


async def expire_due() -> None:
    factory = async_sessionmaker(database(), expire_on_commit=False)
    try:
        async with factory.begin() as db:
            expirable = [state for state, targets in TRANSITIONS.items() if Status.EXPIRED in targets]
            rows = await db.scalars(
                select(Verification)
                .where(Verification.expires_at <= now(), Verification.status.in_(expirable))
                .order_by(Verification.expires_at)
                .with_for_update(skip_locked=True)
                .limit(250)
            )
            for verification in rows:
                advance(db, verification, Status.EXPIRED, notify=True)
    finally:
        await database().dispose()


@celery.task(name="proofscan.expire_verifications", soft_time_limit=25, time_limit=30)
def expire_verifications() -> None:
    asyncio.run(expire_due())


async def purge_evidence() -> None:
    try:
        async with database().begin() as connection:
            await connection.execute(
                update(Checkpoint)
                .where(Checkpoint.photo_expires_at <= now(), Checkpoint.jpeg.is_not(None))
                .values(jpeg=None)
            )
            await connection.execute(
                update(Evidence)
                .where(Evidence.expires_at <= now(), Evidence.jpeg.is_not(None))
                .values(jpeg=None)
            )
    finally:
        await database().dispose()


@celery.task(name="proofscan.expire_evidence", soft_time_limit=25, time_limit=30)
def expire_evidence() -> None:
    asyncio.run(purge_evidence())
