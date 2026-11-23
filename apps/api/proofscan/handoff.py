import asyncio
import hmac
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from .auth import DB, Owner
from .config import settings
from .db import Notification, now
from .domain import InvalidTransition
from .handoff_models import Acceptance, Asset, Checkpoint, Comparison, ComparisonInvalidation, Handoff
from .schemas import GuestExchange, Hardware, Input, Label, ScanTicket, Submission
from .services import fixture_hardware, new_token, signer, token_hash
from .signing import Signature
from .visual import process_photo

router = APIRouter(prefix="/handoffs", tags=["handoffs"])
Mode = Literal["windows", "visual", "simulator"]
Condition = Literal["clean", "visible_wear", "damaged"]


class State(StrEnum):
    DRAFT = "DRAFT"
    BASELINE_SCANNING = "BASELINE_SCANNING"
    BASELINE_CREATED = "BASELINE_CREATED"
    ACTIVE_HANDOFF = "ACTIVE_HANDOFF"
    RETURN_SCANNING = "RETURN_SCANNING"
    COMPARING = "COMPARING"
    REPORT_READY = "REPORT_READY"
    CLOSED = "CLOSED"


NEXT = {current: target for current, target in zip(list(State)[:-1], list(State)[1:], strict=True)}


def move(item: Handoff, target: State) -> None:
    if NEXT.get(State(item.status)) != target:
        raise InvalidTransition(f"Cannot move from {item.status} to {target}.")
    item.status = target


class CreateHandoff(Input):
    label: Label
    mode: Mode


class HandoffView(BaseModel):
    id: UUID
    asset_id: UUID
    label: str
    mode: Mode
    status: State
    receiver_accepted: bool
    report_id: UUID | None
    photos: list[str]


class CompleteCheckpoint(Input):
    condition: Condition
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)] = ""
    reading: Submission | None = None


async def load(handoff_id: UUID, owner: UUID, db: DB, *, lock: bool = False) -> Handoff:
    query = select(Handoff).where(Handoff.id == handoff_id, Handoff.owner_id == owner)
    item = await db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise HTTPException(404, "Handoff not found.")
    return item


async def describe(item: Handoff, db: DB) -> HandoffView:
    asset = await db.get(Asset, item.asset_id)
    assert asset is not None
    accepted = await db.scalar(select(Acceptance.accepted_at).where(Acceptance.handoff_id == item.id))
    linked = await db.scalar(select(Comparison.id).where(Comparison.handoff_id == item.id))
    photos = await db.scalars(
        select(Checkpoint.phase).where(
            Checkpoint.handoff_id == item.id,
            Checkpoint.photo_digest.is_not(None),
            Checkpoint.photo_expires_at > now(),
        )
    )
    return HandoffView.model_validate(
        {
            "id": item.id,
            "asset_id": item.asset_id,
            "label": asset.label,
            "mode": item.mode,
            "status": item.status,
            "receiver_accepted": accepted is not None,
            "report_id": linked,
            "photos": list(photos),
        }
    )


@router.get("", response_model=list[HandoffView])
async def list_handoffs(owner: Owner, db: DB) -> list[HandoffView]:
    items = await db.scalars(
        select(Handoff)
        .where(Handoff.owner_id == owner)
        .order_by(Handoff.created_at.desc(), Handoff.id)
        .limit(30)
    )
    return [await describe(item, db) for item in items]


@router.post("", response_model=HandoffView, status_code=201)
async def create_handoff(data: CreateHandoff, owner: Owner, db: DB) -> HandoffView:
    if data.mode == "simulator" and not settings().enable_simulator:
        raise HTTPException(403, "The simulator is disabled.")
    asset = Asset(
        owner_id=owner, label=data.label, category="object" if data.mode == "visual" else "computer"
    )
    db.add(asset)
    await db.flush()
    item = Handoff(owner_id=owner, asset_id=asset.id, mode=data.mode, status=State.DRAFT)
    db.add(item)
    await db.flush()
    return await describe(item, db)


@router.get("/{handoff_id}", response_model=HandoffView)
async def get_handoff(handoff_id: UUID, owner: Owner, db: DB) -> HandoffView:
    return await describe(await load(handoff_id, owner, db), db)


@router.post("/{handoff_id}/start")
async def begin_checkpoint(
    handoff_id: UUID, owner: Owner, db: DB
) -> dict[str, ScanTicket | HandoffView | None]:
    item = await load(handoff_id, owner, db, lock=True)
    if item.status == State.DRAFT:
        move(item, State.BASELINE_SCANNING)
    elif item.status == State.ACTIVE_HANDOFF:
        move(item, State.RETURN_SCANNING)
    checkpoint = await current_checkpoint(item, db, create=True)
    ticket = None
    if item.mode == "windows":
        raw, digest = new_token()
        checkpoint.ticket_digest = digest
        checkpoint.requested_at = now()
        checkpoint.ticket_expires_at = checkpoint.requested_at + timedelta(minutes=15)
        ticket = ScanTicket(
            scan_id=checkpoint.id,
            challenge=raw,
            issued_at=checkpoint.requested_at,
            expires_at=checkpoint.ticket_expires_at,
        )
    return {"ticket": ticket, "handoff": await describe(item, db)}


async def current_checkpoint(item: Handoff, db: DB, *, create: bool = False) -> Checkpoint:
    phases = {State.BASELINE_SCANNING: "baseline", State.RETURN_SCANNING: "return"}
    phase = phases.get(State(item.status))
    if phase is None:
        raise HTTPException(409, "A baseline or return checkpoint must be in progress.")
    checkpoint = await db.scalar(
        select(Checkpoint).where(
            Checkpoint.handoff_id == item.id,
            Checkpoint.phase == phase,
        )
    )
    if checkpoint is None:
        if not create:
            raise HTTPException(409, "Start the checkpoint first.")
        checkpoint = Checkpoint(handoff_id=item.id, phase=phase)
        db.add(checkpoint)
        await db.flush()
    return checkpoint


@router.post("/{handoff_id}/photos", response_model=HandoffView)
async def save_checkpoint_photo(handoff_id: UUID, request: Request, owner: Owner, db: DB) -> HandoffView:
    item = await load(handoff_id, owner, db, lock=True)
    if item.mode == "simulator":
        raise HTTPException(422, "The simulator uses its own visual condition.")
    checkpoint = await current_checkpoint(item, db)
    try:
        photo = await asyncio.to_thread(process_photo, await request.body())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    checkpoint.jpeg = photo.jpeg
    checkpoint.photo_digest = photo.digest
    checkpoint.photo_expires_at = now() + timedelta(days=settings().evidence_retention_days)
    return await describe(item, db)


@router.get("/{handoff_id}/photos/{phase}", response_class=Response)
async def checkpoint_photo(
    handoff_id: UUID, phase: Literal["baseline", "return"], owner: Owner, db: DB
) -> Response:
    await load(handoff_id, owner, db)
    jpeg = await db.scalar(
        select(Checkpoint.jpeg).where(
            Checkpoint.handoff_id == handoff_id,
            Checkpoint.phase == phase,
            Checkpoint.photo_expires_at > now(),
        )
    )
    if jpeg is None:
        raise HTTPException(404, "This photo is unavailable or has expired.")
    return Response(content=jpeg, media_type="image/jpeg")


def exercise_reading(item: Handoff, checkpoint: Checkpoint, data: CompleteCheckpoint) -> Hardware | None:
    if item.mode == "simulator":
        if not settings().enable_simulator:
            raise HTTPException(403, "The simulator is disabled.")
        return fixture_hardware("verified" if checkpoint.phase == "baseline" else "misrepresented")
    if item.mode == "visual":
        if checkpoint.photo_digest is None:
            raise HTTPException(422, "Add a checkpoint photo first.")
        if data.reading:
            raise HTTPException(422, "This checkpoint uses a photo and an owner condition record.")
        return None
    reading = data.reading
    if (
        not reading
        or reading.platform != "windows"
        or reading.scan_id != checkpoint.id
        or not checkpoint.ticket_digest
        or not checkpoint.ticket_expires_at
        or checkpoint.ticket_expires_at <= now()
        or not hmac.compare_digest(token_hash(reading.challenge), checkpoint.ticket_digest)
        or not reading.hardware
        or not (reading.hardware.cpu or reading.hardware.memory_gib or reading.hardware.drives)
    ):
        raise HTTPException(422, "Import readings from the current Windows checkpoint ticket.")
    return reading.hardware


def compare(before: Checkpoint, after: Checkpoint) -> list[dict]:
    def material(snapshot: dict) -> dict:
        return {
            "Memory (GiB)": snapshot.get("memory_gib"),
            "Largest drive (GB)": max(
                (item["capacity_gb"] for item in snapshot.get("drives", [])), default=None
            ),
            "Battery health (%)": snapshot.get("battery_health_percent"),
            "Processor": ", ".join(snapshot.get("cpu", [])) or None,
            "Graphics": ", ".join(snapshot.get("gpu", [])) or None,
        }

    left = material(before.hardware or {})
    right = material(after.hardware or {})
    result: list[dict] = []
    for metric, value in left.items():
        compared = right[metric]
        if value is None and compared is None:
            continue
        status = (
            "UNAVAILABLE"
            if value is None or compared is None
            else "MATCH"
            if value == compared
            else "MISMATCH"
        )
        result.append({"metric": metric, "before": value, "after": compared, "status": status})
    result.append(
        {
            "metric": "Recorded exterior condition",
            "before": before.condition,
            "after": after.condition,
            "status": "MATCH" if before.condition == after.condition else "MISMATCH",
        }
    )
    return result


@router.post("/{handoff_id}/record", response_model=HandoffView)
async def complete_checkpoint(
    handoff_id: UUID, data: CompleteCheckpoint, owner: Owner, db: DB
) -> HandoffView:
    item = await load(handoff_id, owner, db, lock=True)
    record = await current_checkpoint(item, db)
    hardware = exercise_reading(item, record, data)
    record.hardware = hardware.model_dump(mode="json") if hardware else None
    record.condition = (
        ("clean" if record.phase == "baseline" else "visible_wear")
        if item.mode == "simulator"
        else data.condition
    )
    record.note = (
        ("Baseline exterior" if record.phase == "baseline" else "New scratch")
        if item.mode == "simulator"
        else data.note
    )
    record.recorded_at = now()
    record.ticket_digest = None
    if record.phase == "baseline":
        move(item, State.BASELINE_CREATED)
    else:
        move(item, State.COMPARING)
        before = await db.scalar(
            select(Checkpoint).where(Checkpoint.handoff_id == item.id, Checkpoint.phase == "baseline")
        )
        assert before and before.recorded_at
        asset = await db.get(Asset, item.asset_id)
        assert asset
        report_id = uuid4()
        differences = compare(before, record)
        if item.mode == "simulator":
            differences.append(
                {
                    "metric": "Memory module (simulated)",
                    "before": "Samsung 16 GiB",
                    "after": "Crucial 8 GiB",
                    "status": "MISMATCH",
                }
            )
        payload = {
            "schema_version": 1,
            "kind": "handoff",
            "report_id": str(report_id),
            "handoff_id": str(item.id),
            "asset_id": str(asset.id),
            "label": asset.label,
            "mode": item.mode,
            "identity_confidence": "UNAVAILABLE",
            "differences": differences,
            "baseline": {
                "recorded_at": before.recorded_at.isoformat(),
                "note": before.note,
                "photo_digest": before.photo_digest,
            },
            "return": {
                "recorded_at": record.recorded_at.isoformat(),
                "note": record.note,
                "photo_digest": record.photo_digest,
            },
        }
        signature = signer().sign(payload)
        db.add(
            Comparison(
                id=report_id,
                handoff_id=item.id,
                payload=payload,
                digest=signature.digest,
                signature=signature.value,
                key_id=signature.key_id,
            )
        )
        db.add(Notification(owner_id=owner, handoff_id=item.id, event="HANDOFF_REPORT_READY"))
        move(item, State.REPORT_READY)
    return await describe(item, db)


@router.post("/{handoff_id}/activate", response_model=HandoffView)
async def activate(handoff_id: UUID, owner: Owner, db: DB) -> HandoffView:
    item = await load(handoff_id, owner, db, lock=True)
    move(item, State.ACTIVE_HANDOFF)
    return await describe(item, db)


@router.post("/{handoff_id}/close", response_model=HandoffView)
async def close(handoff_id: UUID, owner: Owner, db: DB) -> HandoffView:
    item = await load(handoff_id, owner, db, lock=True)
    move(item, State.CLOSED)
    return await describe(item, db)


@router.get("/{handoff_id}/report")
async def handoff_report(handoff_id: UUID, owner: Owner, db: DB) -> dict:
    item = await load(handoff_id, owner, db)
    report = await db.scalar(select(Comparison).where(Comparison.handoff_id == item.id))
    if report is None:
        raise HTTPException(404, "Comparison is not ready.")
    signature = Signature(report.digest, report.signature, report.key_id)
    invalidated = await db.get(ComparisonInvalidation, report.id) is not None
    return {
        "payload": report.payload,
        "digest": report.digest,
        "signature": report.signature,
        "key_id": report.key_id,
        "valid": not invalidated and signer().verify(report.payload, signature),
    }


@router.post("/{handoff_id}/invite")
async def invite(handoff_id: UUID, owner: Owner, db: DB) -> dict[str, str]:
    item = await load(handoff_id, owner, db, lock=True)
    if item.status not in {State.BASELINE_CREATED, State.ACTIVE_HANDOFF}:
        raise HTTPException(409, "Create a baseline before inviting the receiver.")
    invite = await db.scalar(select(Acceptance).where(Acceptance.handoff_id == item.id))
    if invite and invite.accepted_at:
        raise HTTPException(409, "The receiver already accepted.")
    raw, digest = new_token()
    if invite is None:
        invite = Acceptance(handoff_id=item.id)
        db.add(invite)
    invite.token_digest = digest
    invite.expires_at = now() + timedelta(days=2)
    return {"url": f"{settings().web_origin.rstrip('/')}/accept/{item.id}#{raw}"}


@router.post("/{handoff_id}/accept")
async def accept(handoff_id: UUID, data: GuestExchange, db: DB) -> dict[str, datetime]:
    item = await db.scalar(select(Handoff).where(Handoff.id == handoff_id).with_for_update())
    if item is None or item.status not in {State.BASELINE_CREATED, State.ACTIVE_HANDOFF}:
        raise HTTPException(404, "This handoff invitation is unavailable.")
    invite = await db.scalar(
        select(Acceptance).where(
            Acceptance.handoff_id == item.id,
            Acceptance.token_digest == token_hash(data.token),
            Acceptance.expires_at > now(),
        )
    )
    if invite is None:
        raise HTTPException(404, "This handoff invitation is unavailable.")
    if invite.accepted_at is None:
        invite.accepted_at = now()
    return {"accepted_at": invite.accepted_at}
