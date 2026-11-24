from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Evidence, Invalidation, Report, ReportSignature, Verification, now
from .domain import Status
from .schemas import Angle, PickupComparison, ReportPayload, VisualFinding
from .services import signer
from .signing import Signature
from .visual import compare_images, photo_work

REQUIRED_VIEWS: tuple[Angle, ...] = ("front", "back")
VIEWS: tuple[Angle, ...] = (*REQUIRED_VIEWS, "left", "right")


async def valid_baseline(db: AsyncSession, owner: UUID, report_id: UUID) -> ReportPayload:
    row = (
        await db.execute(
            select(Report, ReportSignature)
            .join(Verification, Verification.id == Report.verification_id)
            .join(ReportSignature, ReportSignature.report_id == Report.id)
            .outerjoin(Invalidation, Invalidation.report_id == Report.id)
            .where(
                Report.id == report_id,
                Verification.owner_id == owner,
                Verification.status == Status.COMPLETED,
                Invalidation.report_id.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "This signed baseline is unavailable.")
    report, stored = row
    if not signer().verify(report.payload, Signature(stored.digest, stored.value, stored.key_id)):
        raise HTTPException(409, "The baseline signature could not be verified.")
    payload = ReportPayload.model_validate(report.payload)
    if payload.assurance != "COLLECTOR_REPORTED":
        raise HTTPException(409, "A real device report is required for a pickup recheck.")
    return payload


async def compare_pickup(
    db: AsyncSession, baseline: ReportPayload, current: ReportPayload
) -> PickupComparison:
    before, after = baseline.hardware, current.hardware
    fields = {
        "Platform": (baseline.platform, current.platform),
        "Manufacturer": (before.manufacturer, after.manufacturer),
        "Model": (before.model, after.model),
        "Memory": (before.memory_gib, after.memory_gib),
        "Largest drive capacity": (
            max((item.capacity_gb for item in before.drives), default=None),
            max((item.capacity_gb for item in after.drives), default=None),
        ),
    }
    comparable = [
        label for label, values in fields.items() if all(value is not None for value in values)
    ]
    ids = {photo.id for photo in [*baseline.visual_evidence, *current.visual_evidence]}
    rows = await db.execute(
        select(Evidence.id, Evidence.jpeg, Evidence.descriptor).where(
            Evidence.id.in_(ids), Evidence.expires_at > now()
        )
    )
    stored = {row.id: (row.jpeg, row.descriptor) for row in rows}
    left = {photo.angle: stored.get(photo.id, (None, None)) for photo in baseline.visual_evidence}
    right = {photo.angle: stored.get(photo.id, (None, None)) for photo in current.visual_evidence}
    visuals = []
    for angle in VIEWS:
        if angle not in REQUIRED_VIEWS and angle not in left and angle not in right:
            continue
        first, first_descriptor = left.get(angle, (None, None))
        second, second_descriptor = right.get(angle, (None, None))
        status, detail = await photo_work.run(
            compare_images, first, second, first_descriptor, second_descriptor
        )
        visuals.append(VisualFinding(angle=angle, status=status, detail=detail))
    return PickupComparison(
        baseline_report_id=baseline.report_id,
        baseline_verification_id=baseline.verification_id,
        baseline_captured_at=baseline.captured_at,
        changed_hardware=[
            label
            for label in comparable
            if str(fields[label][0]).casefold() != str(fields[label][1]).casefold()
        ],
        compared_hardware=comparable,
        visuals=visuals,
    )
