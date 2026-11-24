from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .agent.usage import record_usage
from .auth import DB, Owner
from .config import settings
from .db import CaptureLink, Challenge, Evidence, ExternalScan, Guest, Scan, Verification, now
from .domain import Status
from .schemas import Angle, CaptureLinkView, CaptureProgress, PhotoView, Ticket
from .services import new_token, photo_view, photos_for_scan, token_hash, validate_challenge
from .verification import GuestSession
from .visual import photo_work, process_photo

router = APIRouter(prefix="/guest/{verification_id}", tags=["scan photos"])
buyer_photos = APIRouter(tags=["scan photos"])
capture = APIRouter(prefix="/capture/{verification_id}", tags=["camera assistance"])
PhotoToken = Annotated[Ticket, Header(alias="X-Photo-Token")]


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
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await store_photo(request, db, scan.id, angle)


@router.post("/photo-link", response_model=CaptureLinkView, status_code=201)
async def issue_photo_link(current: GuestSession, db: DB) -> CaptureLinkView:
    item, guest = current
    scan_id = await db.scalar(
        select(Scan.id).where(Scan.guest_id == guest.id, Scan.platform != "simulator")
    )
    if scan_id is None or item.status != Status.SCANNING:
        raise HTTPException(409, "Start a device scan before creating a camera link.")
    token, digest = new_token()
    expiry = min(now() + timedelta(minutes=15), guest.expires_at, item.expires_at)
    upsert = insert(CaptureLink).values(scan_id=scan_id, token_hash=digest, expires_at=expiry)
    await db.execute(
        upsert.on_conflict_do_update(
            index_elements=[CaptureLink.scan_id],
            set_={"token_hash": digest, "expires_at": expiry},
        )
    )
    return CaptureLinkView(url=f"{settings().web_origin}/capture/{item.id}#{token}", expires_at=expiry)


async def capture_scan(verification_id: UUID, token: str, db: DB, *, lock: bool = False) -> UUID:
    query = (
        select(Scan.id)
        .join(CaptureLink, CaptureLink.scan_id == Scan.id)
        .join(Guest, Guest.id == Scan.guest_id)
        .join(Verification, Verification.id == Guest.verification_id)
        .where(
            Verification.id == verification_id,
            Verification.status == Status.SCANNING,
            Verification.expires_at > func.clock_timestamp(),
            Guest.revoked_at.is_(None),
            Guest.expires_at > func.clock_timestamp(),
            Scan.platform != "simulator",
            CaptureLink.token_hash == token_hash(token),
            CaptureLink.expires_at > func.clock_timestamp(),
        )
    )
    scan_id = await db.scalar(query)
    if scan_id is not None and lock:
        await db.scalar(
            select(Verification.id).where(Verification.id == verification_id).with_for_update()
        )
        # The seller can expire or rotate this link while an upload waits for the lock.
        scan_id = await db.scalar(query)
    if scan_id is None:
        raise HTTPException(404, "This camera link is unavailable. Ask for a fresh link.")
    return scan_id


@capture.get("", response_model=CaptureProgress)
async def camera_progress(verification_id: UUID, token: PhotoToken, db: DB) -> CaptureProgress:
    scan_id = await capture_scan(verification_id, token, db)
    return CaptureProgress(views=[photo.angle for photo in await photos_for_scan(db, scan_id)])


@capture.post("/photos", response_model=PhotoView, status_code=201)
async def add_camera_photo(
    verification_id: UUID, token: PhotoToken, request: Request, db: DB, angle: Angle
) -> PhotoView:
    scan_id = await capture_scan(verification_id, token, db, lock=True)
    return await store_photo(request, db, scan_id, angle)


async def store_photo(request: Request, db: DB, scan_id: UUID, angle: Angle) -> PhotoView:
    try:
        photo = await photo_work.run(process_photo, await request.body())
    except ValueError as exc:
        await record_usage(db, "purchase_visual", accepted=False)
        await db.commit()
        raise HTTPException(422, str(exc)) from exc

    external = await db.scalar(select(ExternalScan).where(ExternalScan.scan_id == scan_id))
    if external is None:
        external = ExternalScan(scan_id=scan_id)
        db.add(external)
        await db.flush()
    saved = await db.scalar(
        select(Evidence).where(Evidence.external_scan_id == external.id, Evidence.angle == angle)
    )
    repeated = await db.scalar(
        select(Evidence.id).where(
            Evidence.external_scan_id == external.id,
            Evidence.angle != angle,
            Evidence.digest == photo.digest,
            Evidence.expires_at > now(),
        )
    )
    if repeated is not None:
        await record_usage(db, "purchase_visual", accepted=False)
        await db.commit()
        raise HTTPException(422, "Take a separate photo of this side.")
    if saved is None:
        saved = Evidence(external_scan_id=external.id, angle=angle)
        db.add(saved)
    saved.digest = photo.digest
    saved.width = photo.width
    saved.height = photo.height
    saved.brightness = photo.brightness
    saved.sharpness = photo.sharpness
    saved.jpeg = photo.jpeg
    saved.descriptor = photo.descriptor
    saved.expires_at = now() + timedelta(days=settings().evidence_retention_days)
    await record_usage(db, "purchase_visual", accepted=True)
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
