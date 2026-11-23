from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, or_, select

from .auth import DB, Admin, Owner
from .db import (
    AgentRun,
    AgentStep,
    Audit,
    Evidence,
    Guest,
    Invalidation,
    ModelCall,
    Report,
    ReportSignature,
    Scan,
    Snapshot,
    Verification,
    now,
)
from .domain import TRANSITIONS, Status
from .handoff_models import Asset, Checkpoint, Comparison, ComparisonInvalidation, Handoff
from .schemas import AdminReason, ReportPayload, SignedReport, VerificationResult, VerificationView
from .services import advance, signer
from .signing import Signature, encode
from .verification import view

router = APIRouter(tags=["reports"])
admin_router = APIRouter(prefix="/admin", tags=["operator"])


async def signed_report(db: DB, report_id: UUID) -> tuple[Report, Signature, bool]:
    report = await db.get(Report, report_id)
    signature = await db.get(ReportSignature, report_id)
    if not report or not signature:
        raise HTTPException(404, "Shared report not found.")
    invalidated = await db.get(Invalidation, report_id) is not None
    return report, Signature(signature.digest, signature.value, signature.key_id), invalidated


@router.get("/reports/{report_id}/verify", response_model=VerificationResult)
async def public_verify(report_id: UUID, db: DB) -> VerificationResult:
    comparison = await db.get(Comparison, report_id)
    if comparison:
        payload = comparison.payload
        signature = Signature(comparison.digest, comparison.signature, comparison.key_id)
        invalidated = await db.get(ComparisonInvalidation, report_id) is not None
    else:
        report, signature, invalidated = await signed_report(db, report_id)
        payload = report.payload
    key = signer().public_keys.get(signature.key_id)
    return VerificationResult(
        report_id=report_id,
        valid=not invalidated and signer().verify(payload, signature),
        invalidated=invalidated,
        digest=signature.digest,
        signature=signature.value,
        key_id=signature.key_id,
        public_key=encode(key.public_bytes_raw()) if key else None,
    )


@router.get(
    "/verifications/{verification_id}/report",
    response_model=SignedReport,
    response_model_exclude_unset=True,
)
async def owner_report(verification_id: UUID, user: Owner, db: DB) -> SignedReport:
    verification = await db.get(Verification, verification_id)
    if verification is None or verification.owner_id != user or verification.status != Status.COMPLETED:
        raise HTTPException(404, "Shared report not found.")
    report_id = await db.scalar(select(Report.id).where(Report.verification_id == verification_id))
    if report_id is None:
        raise HTTPException(404, "Shared report not found.")
    report, signature, invalidated = await signed_report(db, report_id)
    return SignedReport(
        payload=ReportPayload.model_validate(report.payload),
        digest=signature.digest,
        signature=signature.value,
        key_id=signature.key_id,
        valid=not invalidated and signer().verify(report.payload, signature),
    )


@admin_router.get("/overview")
async def overview(_: Admin, db: DB) -> dict[str, int]:
    rows = await db.execute(select(Verification.status, func.count()).group_by(Verification.status))
    return {status: count for status, count in rows}


@admin_router.get("/audit")
async def audit_log(_: Admin, db: DB) -> list[dict[str, str]]:
    rows = await db.scalars(select(Audit).order_by(Audit.created_at.desc(), Audit.id).limit(50))
    return [
        {
            "id": str(item.id),
            "actor_id": str(item.actor_id),
            "target_id": str(item.target_id),
            "action": item.action,
            "reason": item.reason,
            "created_at": item.created_at.isoformat(),
        }
        for item in rows
    ]


@admin_router.get("/metrics")
async def metrics(_: Admin, db: DB) -> dict:
    handoffs = await db.execute(select(Handoff.status, func.count()).group_by(Handoff.status))
    scans = await db.execute(
        select(Scan.platform, func.count(Scan.id), func.count(Snapshot.id))
        .outerjoin(Snapshot)
        .group_by(Scan.platform)
    )
    model = (
        await db.execute(
            select(
                func.count(ModelCall.id),
                func.count(ModelCall.id).filter(ModelCall.accepted),
                func.coalesce(func.sum(ModelCall.input_tokens), 0),
                func.coalesce(func.sum(ModelCall.output_tokens), 0),
            )
        )
    ).one()
    evidence_bytes = await db.scalar(
        select(func.coalesce(func.sum(func.octet_length(Evidence.jpeg)), 0))
    )
    checkpoint_bytes = await db.scalar(
        select(func.coalesce(func.sum(func.octet_length(Checkpoint.jpeg)), 0))
    )
    mismatches = await db.scalar(
        select(func.count())
        .select_from(AgentStep)
        .join(AgentRun)
        .join(Scan)
        .where(
            Scan.platform != "simulator",
            AgentStep.action == "analyze_claims",
            AgentStep.output["findings"].contains([{"status": "MISMATCH"}]),
        )
    )
    return {
        "handoffs": dict(handoffs.tuples().all()),
        "scans": [
            {"platform": platform, "started": started, "submitted": submitted}
            for platform, started, submitted in scans
        ],
        "agent_runs": await db.scalar(select(func.count(AgentRun.id))),
        "listing_mismatch_scans": mismatches,
        "evidence_bytes": (evidence_bytes or 0) + (checkpoint_bytes or 0),
        "model": {
            "requests": model[0],
            "accepted": model[1],
            "input_tokens": model[2],
            "output_tokens": model[3],
        },
    }


@admin_router.get("/handoffs/search/{identifier}")
async def search_handoffs(identifier: UUID, _: Admin, db: DB) -> list[dict[str, str]]:
    rows = await db.execute(
        select(Handoff.id, Asset.id, Asset.label, Handoff.status)
        .join(Asset)
        .outerjoin(Comparison)
        .where(
            or_(
                Handoff.id == identifier,
                Asset.id == identifier,
                Handoff.owner_id == identifier,
                Comparison.id == identifier,
            )
        )
        .limit(30)
    )
    return [
        {"id": str(id_), "asset_id": str(asset), "label": label, "status": status}
        for id_, asset, label, status in rows
    ]


@admin_router.get("/search/{identifier}", response_model=list[VerificationView])
async def search(identifier: UUID, _: Admin, db: DB) -> list[VerificationView]:
    rows = await db.scalars(
        select(Verification)
        .outerjoin(Report, Verification.id == Report.verification_id)
        .where(
            or_(
                Verification.id == identifier,
                Verification.owner_id == identifier,
                Report.id == identifier,
            )
        )
        .order_by(Verification.created_at.desc())
        .limit(30)
    )
    return [view(row) for row in rows]


@admin_router.post("/reports/{report_id}/invalidate", status_code=204, response_class=Response)
async def invalidate(report_id: UUID, data: AdminReason, admin: Admin, db: DB) -> None:
    comparison = await db.scalar(
        select(Comparison.id).where(Comparison.id == report_id).with_for_update()
    )
    if comparison:
        if await db.get(ComparisonInvalidation, report_id) is None:
            db.add(ComparisonInvalidation(report_id=report_id, created_at=now()))
            db.add(
                Audit(
                    actor_id=admin, action="invalidate_report", target_id=report_id, reason=data.reason
                )
            )
        return
    await db.scalar(select(Report.id).where(Report.id == report_id).with_for_update())
    _, _, invalidated = await signed_report(db, report_id)
    if not invalidated:
        db.add(Invalidation(report_id=report_id))
        db.add(
            Audit(actor_id=admin, action="invalidate_report", target_id=report_id, reason=data.reason)
        )


@admin_router.post("/verifications/{verification_id}/revoke", status_code=204, response_class=Response)
async def revoke(verification_id: UUID, data: AdminReason, admin: Admin, db: DB) -> None:
    verification = await db.scalar(
        select(Verification).where(Verification.id == verification_id).with_for_update()
    )
    guest = await db.scalar(select(Guest).where(Guest.verification_id == verification_id))
    if verification is None or guest is None:
        raise HTTPException(404, "Guest session not found.")
    if guest.revoked_at is None:
        guest.revoked_at = now()
        if Status.CANCELLED in TRANSITIONS.get(Status(verification.status), set()):
            advance(db, verification, Status.CANCELLED, notify=True)
        db.add(Audit(actor_id=admin, action="revoke_guest", target_id=guest.id, reason=data.reason))
