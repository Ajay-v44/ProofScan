from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlalchemy import select

from .auth import DB, Owner
from .config import settings
from .db import Challenge, Evidence, ExternalScan, Guest, Scan, Verification, now
from .domain import Status
from .schemas import Angle, PhotoView, Ticket
from .services import photo_view, token_hash, validate_challenge
from .verification import GuestSession
from .visual import photo_work, process_photo

router = APIRouter(prefix="/guest/{verification_id}", tags=["scan photos"])
buyer_photos = APIRouter(tags=["scan photos"])


@router.post(
    "/photos",
    response_model=PhotoView,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
async def add_photo(
    request: Request,
    current: GuestSession,
    db: DB,
    angle: Angle,
    challenge: Annotated[Ticket, Header(alias="X-Scan-Challenge")],
) -> PhotoView:
    item, guest = current
    if item.status != Status.SCANNING:
        raise HTTPException(409, "Start a device scan before adding photos.")
    scan = await db.scalar(select(Scan).where(Scan.guest_id == guest.id))
    if scan is None or scan.platform == "simulator":
        raise HTTPException(409, "Start a device scan before adding photos.")
    record = await db.scalar(select(Challenge).where(Challenge.token_hash == token_hash(challenge)))
    try:
        validate_challenge(record, scan, guest, scan.platform)
        photo = await photo_work.run(process_photo, await request.body())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    external = await db.scalar(select(ExternalScan).where(ExternalScan.scan_id == scan.id))
    if external is None:
        external = ExternalScan(scan_id=scan.id)
        db.add(external)
        await db.flush()
    saved = await db.scalar(
        select(Evidence).where(Evidence.external_scan_id == external.id, Evidence.angle == angle)
    )
    if saved is None:
        saved = Evidence(external_scan_id=external.id, angle=angle)
        db.add(saved)
    saved.digest = photo.digest
    saved.width = photo.width
    saved.height = photo.height
    saved.brightness = photo.brightness
    saved.sharpness = photo.sharpness
    saved.jpeg = photo.jpeg
    saved.expires_at = now() + timedelta(days=settings().evidence_retention_days)
    await db.flush()
    return photo_view(saved)


def image_response(jpeg: bytes | None) -> Response:
    if jpeg is None:
        raise HTTPException(404, "This photo is unavailable or has expired.")
    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/photos/{photo_id}", response_class=Response)
async def guest_photo(photo_id: UUID, current: GuestSession, db: DB) -> Response:
    _, guest = current
    jpeg = await db.scalar(
        select(Evidence.jpeg)
        .join(ExternalScan)
        .join(Scan)
        .where(
            Scan.guest_id == guest.id,
            Evidence.id == photo_id,
            Evidence.expires_at > now(),
        )
    )
    return image_response(jpeg)


@buyer_photos.get("/verifications/{verification_id}/photos/{photo_id}", response_class=Response)
async def buyer_photo(verification_id: UUID, photo_id: UUID, owner: Owner, db: DB) -> Response:
    jpeg = await db.scalar(
        select(Evidence.jpeg)
        .join(ExternalScan)
        .join(Scan)
        .join(Guest)
        .join(Verification)
        .where(
            Verification.id == verification_id,
            Verification.owner_id == owner,
            Verification.status == Status.COMPLETED,
            Evidence.id == photo_id,
            Evidence.expires_at > now(),
        )
    )
    return image_response(jpeg)
