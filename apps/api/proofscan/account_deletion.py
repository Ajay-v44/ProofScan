import asyncio
import hmac
import logging
from datetime import timedelta
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import StringConstraints
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .agent.models import AgentExecution, CatalogItem
from .auth import COOKIE, DB, Owner, password_digest, password_work, supabase_login
from .config import settings
from .db import (
    AgentRun,
    AgentStep,
    CaptureLink,
    Challenge,
    Claim,
    Consent,
    DeletedAccount,
    Evidence,
    ExternalScan,
    FunctionalResult,
    Guest,
    Invalidation,
    ModelCall,
    Notification,
    PricingEstimate,
    Report,
    ReportSignature,
    Scan,
    Snapshot,
    User,
    Verification,
    now,
)
from .handoff_models import (
    Acceptance,
    Asset,
    Checkpoint,
    CheckpointPhoto,
    Comparison,
    ComparisonInvalidation,
    Handoff,
)
from .schemas import Credentials, Input
from .signing import decode

router = APIRouter(prefix="/auth", tags=["account"])
log = logging.getLogger(__name__)


class DeleteAccount(Input):
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


async def purge_workspace(db: AsyncSession, owner: UUID) -> None:
    # Lock parent records before removing children so guest uploads and operator
    # actions finish first or see the committed deletion.
    verifications = select(Verification.id).where(Verification.owner_id == owner)
    handoffs = select(Handoff.id).where(Handoff.owner_id == owner)
    reports = select(Report.id).where(Report.verification_id.in_(verifications))
    comparisons = select(Comparison.id).where(Comparison.handoff_id.in_(handoffs))
    for parents in (verifications, handoffs, reports, comparisons):
        await db.execute(parents.order_by(parents.selected_columns[0]).with_for_update())

    guests = select(Guest.id).where(Guest.verification_id.in_(verifications))
    scans = select(Scan.id).where(Scan.guest_id.in_(guests))
    external = select(ExternalScan.id).where(ExternalScan.scan_id.in_(scans))
    runs = select(AgentRun.id).where(AgentRun.scan_id.in_(scans))
    checkpoints = select(Checkpoint.id).where(Checkpoint.handoff_id.in_(handoffs))

    await db.execute(
        update(Verification)
        .where(Verification.owner_id == owner, Verification.baseline_report_id.is_not(None))
        .values(baseline_report_id=None)
    )
    # Delete from leaves to roots. Vector rows follow their catalog item by FK cascade.
    for statement in (
        delete(Notification).where(Notification.owner_id == owner),
        delete(ModelCall).where(ModelCall.owner_id == owner),
        delete(AgentExecution).where(AgentExecution.owner_id == owner),
        delete(CatalogItem).where(CatalogItem.owner_id == owner),
        delete(Invalidation).where(Invalidation.report_id.in_(reports)),
        delete(ReportSignature).where(ReportSignature.report_id.in_(reports)),
        delete(PricingEstimate).where(PricingEstimate.report_id.in_(reports)),
        delete(Report).where(Report.verification_id.in_(verifications)),
        delete(AgentStep).where(AgentStep.run_id.in_(runs)),
        delete(AgentRun).where(AgentRun.scan_id.in_(scans)),
        delete(Evidence).where(Evidence.external_scan_id.in_(external)),
        delete(ExternalScan).where(ExternalScan.scan_id.in_(scans)),
        delete(FunctionalResult).where(FunctionalResult.scan_id.in_(scans)),
        delete(Snapshot).where(Snapshot.scan_id.in_(scans)),
        delete(Challenge).where(Challenge.scan_id.in_(scans)),
        delete(CaptureLink).where(CaptureLink.scan_id.in_(scans)),
        delete(Scan).where(Scan.guest_id.in_(guests)),
        delete(Consent).where(Consent.guest_id.in_(guests)),
        delete(Guest).where(Guest.verification_id.in_(verifications)),
        delete(Claim).where(Claim.verification_id.in_(verifications)),
        delete(Verification).where(Verification.owner_id == owner),
        delete(ComparisonInvalidation).where(ComparisonInvalidation.report_id.in_(comparisons)),
        delete(Comparison).where(Comparison.handoff_id.in_(handoffs)),
        delete(CheckpointPhoto).where(CheckpointPhoto.checkpoint_id.in_(checkpoints)),
        delete(Checkpoint).where(Checkpoint.handoff_id.in_(handoffs)),
        delete(Acceptance).where(Acceptance.handoff_id.in_(handoffs)),
        delete(Handoff).where(Handoff.owner_id == owner),
        delete(Asset).where(Asset.owner_id == owner),
        delete(User).where(User.id == owner),
    ):
        await db.execute(statement)


@router.post("/delete-account", status_code=202)
async def delete_account(
    data: DeleteAccount, request: Request, response: Response, owner: Owner, db: DB
) -> dict[str, bool]:
    config = settings()
    hosted = config.auth_mode == "supabase"
    if hosted:
        if not config.supabase_secret_key:
            raise HTTPException(503, "Account deletion is temporarily unavailable.")
        email = getattr(request.state, "account_email", None)
        if not email:
            raise HTTPException(401, "Sign in with your email and password to delete this account.")
        confirmed = await supabase_login(
            Credentials(email=email, password=data.password), Response(), db, signup=False
        )
        if confirmed.get("user_id") != str(owner):
            raise HTTPException(401, "Invalid sign-in.")

    user = await db.get(User, owner, with_for_update=True)
    if user is None:
        raise HTTPException(401, "Sign in again.")
    if not hosted:
        salt, expected = (user.password_hash or ".").split(".")
        digest = await password_work.run(
            password_digest, data.password, decode(salt) if salt else bytes(16)
        )
        if not hmac.compare_digest(digest, expected):
            raise HTTPException(401, "Invalid password.")

    db.add(DeletedAccount(id=owner, provider_retry_at=now() if hosted else None))
    await db.flush()
    await purge_workspace(db, owner)
    response.delete_cookie(COOKIE)
    return {"provider_pending": hosted}


async def remove_hosted_identity(client: httpx.AsyncClient, owner: UUID) -> bool:
    config = settings()
    key = config.supabase_secret_key
    if not key:
        return False
    secret = key.get_secret_value()
    headers = {"apikey": secret}
    if not secret.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + secret
    try:
        async with asyncio.timeout(4):
            result = await client.delete(
                f"{config.supabase_url.rstrip('/')}/auth/v1/admin/users/{owner}", headers=headers
            )
        if result.is_success:
            return True
        payload = result.json() if result.status_code == 404 else None
        return (
            isinstance(payload, dict)
            and (payload.get("error_code") or payload.get("code")) == "user_not_found"
        )
    except (httpx.RequestError, TimeoutError, ValueError):
        return False


async def finish_hosted_deletions(engine: AsyncEngine) -> int:
    if settings().auth_mode != "supabase" or not settings().supabase_secret_key:
        return 0
    factory = async_sessionmaker(engine)
    completed = 0
    async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
        for _ in range(5):
            async with factory.begin() as db:
                job = await db.scalar(
                    select(DeletedAccount)
                    .where(DeletedAccount.provider_retry_at <= now())
                    .order_by(DeletedAccount.provider_retry_at, DeletedAccount.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if job is None:
                    break
                removed = await remove_hosted_identity(client, job.id)
                job.provider_retry_at = None if removed else now() + timedelta(minutes=5)
                if not removed:
                    log.warning("Hosted account deletion will retry.")
                completed += int(removed)
    return completed
