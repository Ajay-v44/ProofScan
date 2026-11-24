import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Invalidation, Report, ReportSignature, Verification
from ..domain import Status
from ..schemas import ReportPayload
from ..services import signer
from ..signing import Signature
from .models import CatalogItem
from .schemas import Category

IDENTIFIERS = re.compile(
    r"https?://\S+|[\w.+-]+@[\w.-]+\.\w+|\b(?:\d[\s().+-]*){7,}\b"
    r"|\b[A-Za-z0-9_-]{24,}\b",
    re.IGNORECASE,
)


def index_title(report: ReportPayload) -> str:
    value = " ".join(part for part in (report.hardware.manufacturer, report.hardware.model) if part)
    value = IDENTIFIERS.sub("", value).strip()
    return value[:120] if len(value) >= 2 else f"{report.platform.capitalize()} device"


def category_for(report: ReportPayload, title: str) -> Category:
    words = title.lower()
    if any(marker in words for marker in ("ipad", "tablet", "galaxy tab", "surface pro")):
        return "tablet"
    if report.platform in {"ios", "android"}:
        return "phone"
    if any(marker in words for marker in ("laptop", "notebook", "macbook", "thinkpad", "latitude")):
        return "laptop"
    return "other"


async def index_shared_report(db: AsyncSession, owner: UUID, report: Report) -> None:
    payload = ReportPayload.model_validate(report.payload)
    if payload.assurance != "COLLECTOR_REPORTED":
        return
    title = index_title(payload)
    details = {
        "memory_gib": payload.hardware.memory_gib,
        "storage_gb": max((drive.capacity_gb for drive in payload.hardware.drives), default=None),
        "battery_health_percent": payload.hardware.battery_health_percent,
        "claim_mismatches": sum(finding.status == "MISMATCH" for finding in payload.findings),
        "exterior_views": len(payload.visual_evidence),
    }
    estimate = payload.price_estimate
    priced = (
        estimate is not None
        and estimate.source == "LOCAL_COMPARABLES"
        and 1 <= estimate.low <= estimate.high <= 100_000_000
        and re.fullmatch(r"[A-Z]{3}", estimate.currency) is not None
    )
    notes = ["Shared signed device report."]
    for name, value in details.items():
        if value is not None:
            notes.append(f"{name.replace('_', ' ')}: {value}.")
    if priced and estimate is not None:
        notes.append(f"Comparable price range: {estimate.currency} {estimate.low}–{estimate.high}.")
    await db.execute(
        insert(CatalogItem)
        .values(
            owner_id=owner,
            report_id=report.id,
            title=title,
            category=category_for(payload, title),
            notes=" ".join(notes),
            facts={**details, "estimated_price": priced},
            price=estimate.high if priced and estimate is not None else None,
            currency=estimate.currency if priced and estimate is not None else None,
        )
        .on_conflict_do_nothing(index_elements=[CatalogItem.report_id])
    )


async def backfill_owner_reports(db: AsyncSession, owner: UUID) -> None:
    rows = await db.execute(
        select(Report, ReportSignature)
        .join(Verification, Verification.id == Report.verification_id)
        .join(ReportSignature, ReportSignature.report_id == Report.id)
        .outerjoin(Invalidation, Invalidation.report_id == Report.id)
        .where(
            Verification.owner_id == owner,
            Verification.status == Status.COMPLETED,
            Invalidation.report_id.is_(None),
            Report.payload["assurance"].astext == "COLLECTOR_REPORTED",
            ~select(CatalogItem.id).where(CatalogItem.report_id == Report.id).exists(),
        )
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(50)
        .with_for_update(of=Report, skip_locked=True)
    )
    for report, stored in rows:
        signature = Signature(stored.digest, stored.value, stored.key_id)
        if signer().verify(report.payload, signature):
            await index_shared_report(db, owner, report)
