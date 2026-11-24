import asyncio
from datetime import datetime
from time import monotonic

from celery import Celery
from sqlalchemy import SQLColumnExpression, Update, delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from proofscan.agent.models import AgentExecution
from proofscan.config import settings
from proofscan.db import Evidence, Verification, database, now
from proofscan.domain import TRANSITIONS, Status
from proofscan.handoff_models import Checkpoint
from proofscan.services import advance

celery = Celery("proofscan", broker=settings().redis_url)
BATCH_SIZE = 250
MAX_BATCHES = 20
RUN_WINDOW_SECONDS = 20
EXPIRABLE = tuple(state for state, targets in TRANSITIONS.items() if Status.EXPIRED in targets)

celery.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "expire-verifications": {
            "task": "proofscan.expire_verifications",
            "schedule": 60.0,
            "options": {"expires": 60},
        },
        "expire-evidence": {
            "task": "proofscan.expire_evidence",
            "schedule": 3600.0,
            "options": {"expires": 3600},
        },
        "expire-agent-executions": {
            "task": "proofscan.expire_agent_executions",
            "schedule": 3600.0,
            "options": {"expires": 3600},
        },
    },
)


async def expire_due() -> int:
    engine = database()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cutoff = now()
    deadline = monotonic() + RUN_WINDOW_SECONDS
    total = 0
    try:
        for _ in range(MAX_BATCHES):
            async with factory.begin() as db:
                rows = (
                    await db.scalars(
                        select(Verification)
                        .where(Verification.expires_at <= cutoff, Verification.status.in_(EXPIRABLE))
                        .order_by(Verification.expires_at, Verification.id)
                        .with_for_update(skip_locked=True)
                        .limit(BATCH_SIZE)
                    )
                ).all()
                for verification in rows:
                    advance(db, verification, Status.EXPIRED, notify=True)
            total += len(rows)
            if len(rows) < BATCH_SIZE or monotonic() >= deadline:
                break
    finally:
        await engine.dispose()
    return total


@celery.task(name="proofscan.expire_verifications", soft_time_limit=25, time_limit=30)
def expire_verifications() -> int:
    return asyncio.run(expire_due())


def photo_purge_batch(
    model: type[Evidence] | type[Checkpoint],
    expiry: SQLColumnExpression[datetime | None],
    cutoff: datetime,
) -> Update:
    due = (
        select(model.id)
        .where(expiry <= cutoff, model.jpeg.is_not(None))
        .order_by(expiry, model.id)
        .with_for_update(skip_locked=True)
        .limit(BATCH_SIZE)
        .cte()
    )
    return update(model).where(model.id.in_(select(due.c.id))).values(jpeg=None)


async def purge_evidence() -> int:
    engine = database()
    cutoff = now()
    deadline = monotonic() + RUN_WINDOW_SECONDS
    total = 0
    try:
        for _ in range(MAX_BATCHES):
            async with engine.begin() as connection:
                checkpoints = await connection.execute(
                    photo_purge_batch(Checkpoint, Checkpoint.photo_expires_at, cutoff)
                )
                evidence = await connection.execute(
                    photo_purge_batch(Evidence, Evidence.expires_at, cutoff)
                )
            total += checkpoints.rowcount + evidence.rowcount
            if max(checkpoints.rowcount, evidence.rowcount) < BATCH_SIZE or monotonic() >= deadline:
                break
    finally:
        await engine.dispose()
    return total


@celery.task(name="proofscan.expire_evidence", soft_time_limit=25, time_limit=30)
def expire_evidence() -> int:
    return asyncio.run(purge_evidence())


async def purge_agent_executions() -> int:
    engine = database()
    cutoff = now()
    deadline = monotonic() + RUN_WINDOW_SECONDS
    removed = 0
    due = (
        select(AgentExecution.id)
        .where(AgentExecution.expires_at <= cutoff)
        .order_by(AgentExecution.expires_at, AgentExecution.id)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
        .cte()
    )
    try:
        for _ in range(MAX_BATCHES):
            async with engine.begin() as conn:
                batch = await conn.execute(
                    delete(AgentExecution).where(AgentExecution.id.in_(select(due.c.id)))
                )
            removed += batch.rowcount
            if batch.rowcount < BATCH_SIZE or monotonic() >= deadline:
                break
    finally:
        await engine.dispose()
    return removed


@celery.task(name="proofscan.expire_agent_executions", soft_time_limit=25, time_limit=30)
def expire_agent_executions() -> int:
    return asyncio.run(purge_agent_executions())
