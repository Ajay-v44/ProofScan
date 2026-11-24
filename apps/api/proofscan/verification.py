from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, select, update

from .agent.report_index import index_shared_report
from .auth import DB, Owner, set_cookie
from .config import settings
from .db import (
    AgentRun,
    AgentStep,
    CaptureLink,
    Challenge,
    Claim,
    Consent,
    Evidence,
    ExternalScan,
    FunctionalResult,
    Guest,
    Notification,
    PricingEstimate,
    Report,
    ReportSignature,
    Scan,
    Snapshot,
    Verification,
    now,
)
from .domain import TRANSITIONS, Status
from .inspection import inspect
from .pagination import PAGE_SIZE, before_record
from .pickup import REQUIRED_VIEWS, compare_pickup, valid_baseline
from .pricing import pricing_provider
from .schemas import (
    ConsentIn,
    CreatedVerification,
    CreateVerification,
    Decision,
    FunctionalReading,
    GuestExchange,
    GuestView,
    NotificationView,
    ReportPayload,
    ScanTicket,
    StartScan,
    Submission,
    VerificationView,
)
from .services import (
    GUEST_SCOPE,
    advance,
    claims_view,
    create_challenge,
    create_report,
    fixture_hardware,
    new_token,
    photos_for_scan,
    signer,
    token_hash,
    validate_challenge,
)

owner_router = APIRouter(tags=["buyer"])
guest_router = APIRouter(prefix="/guest/{verification_id}", tags=["guest seller"])
GUEST_COOKIE = "proofscan_guest"


def view(item: Verification) -> VerificationView:
    status = item.status
    if item.expires_at <= now() and Status.EXPIRED in TRANSITIONS.get(Status(status), set()):
        status = Status.EXPIRED
    return VerificationView(
        id=item.id,
        label=item.label,
        status=status,
        created_at=item.created_at,
        expires_at=item.expires_at,
        require_exterior=item.require_exterior,
        is_pickup=item.baseline_report_id is not None,
    )


@owner_router.post("/verifications", response_model=CreatedVerification, status_code=201)
async def create(data: CreateVerification, owner: Owner, db: DB) -> CreatedVerification:
    return await open_request(data, owner, db)


async def open_request(
    data: CreateVerification, owner: UUID, db: DB, *, baseline_report_id: UUID | None = None
) -> CreatedVerification:
    expires = now() + timedelta(days=2)
    item = Verification(
        owner_id=owner,
        label=data.label,
        status=Status.DRAFT,
        expires_at=expires,
        baseline_report_id=baseline_report_id,
    )
    db.add(item)
    await db.flush()
    raw, digest = new_token()
    db.add(Guest(verification_id=item.id, expires_at=expires, token_hash=digest, scope=GUEST_SCOPE))
    db.add(Claim(verification_id=item.id, **data.claims.model_dump()))
    advance(db, item, Status.LINK_CREATED)
    return CreatedVerification(
        **view(item).model_dump(),
        guest_url=f"{settings().web_origin.rstrip('/')}/seller/{item.id}#{raw}",
    )


@owner_router.post(
    "/verifications/{verification_id}/recheck", response_model=CreatedVerification, status_code=201
)
async def create_recheck(verification_id: UUID, owner: Owner, db: DB) -> CreatedVerification:
    report_id = await db.scalar(
        select(Report.id)
        .join(Verification, Verification.id == Report.verification_id)
        .where(Verification.id == verification_id, Verification.owner_id == owner)
    )
    if report_id is None:
        raise HTTPException(404, "Shared report not found.")
    baseline = await valid_baseline(db, owner, report_id)
    claims = claims_view(await db.get(Claim, verification_id))
    data = CreateVerification(label=("Pickup check · " + baseline.label)[:120], claims=claims)
    return await open_request(data, owner, db, baseline_report_id=report_id)


@owner_router.get("/verifications", response_model=list[VerificationView])
async def verifications(
    owner: Owner,
    db: DB,
    offset: Annotated[int, Query(ge=0)] = 0,
    before: UUID | None = None,
) -> list[VerificationView]:
    page = select(Verification).where(Verification.owner_id == owner)
    if before is not None:
        page = page.where(before_record(Verification, owner, before))
    rows = await db.scalars(
        page.order_by(Verification.created_at.desc(), Verification.id.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    return [view(item) for item in rows]


@owner_router.get("/notifications", response_model=list[NotificationView])
async def notifications(
    owner: Owner,
    db: DB,
    offset: Annotated[int, Query(ge=0)] = 0,
    before: UUID | None = None,
) -> list[NotificationView]:
    page = select(Notification).where(Notification.owner_id == owner)
    if before is not None:
        page = page.where(before_record(Notification, owner, before))
    rows = await db.scalars(
        page.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    return [NotificationView.model_validate(row) for row in rows]


async def guest_credential(
    verification_id: UUID, raw: str | None, db: DB, *, lock: bool = True
) -> tuple[Verification, Guest]:
    if raw is None or len(raw) != 43:
        raise HTTPException(404, "This seller link is unavailable.")
    credential = (
        Guest.verification_id == verification_id,
        Guest.token_hash == token_hash(raw),
        Guest.scope == GUEST_SCOPE,
    )
    if lock:
        # Keep the write lock order used by revocation, then recheck the guest after it is acquired.
        item = await db.scalar(
            select(Verification)
            .where(
                Verification.id == verification_id,
                select(Guest.id).where(*credential, Guest.revoked_at.is_(None)).exists(),
            )
            .with_for_update()
        )
        guest = await db.scalar(select(Guest).where(*credential)) if item is not None else None
    else:
        row = (
            await db.execute(select(Verification, Guest).join(Guest).where(*credential))
        ).one_or_none()
        item, guest = row if row is not None else (None, None)
    if (
        item is None
        or guest is None
        or guest.revoked_at
        or guest.expires_at <= now()
        or item.status == Status.CANCELLED
    ):
        raise HTTPException(404, "This seller link expired or was revoked.")
    return item, guest


async def guest_session(verification_id: UUID, request: Request, db: DB) -> tuple[Verification, Guest]:
    token = request.headers.get("X-Guest-Token") or request.cookies.get(GUEST_COOKIE)
    return await guest_credential(verification_id, token, db, lock=request.method != "GET")


GuestSession = Annotated[tuple[Verification, Guest], Depends(guest_session)]


async def guest_view(item: Verification, guest: Guest, db: DB) -> GuestView:
    claims = claims_view(await db.get(Claim, item.id))
    result = GuestView(
        verification=view(item),
        claims=claims,
        simulator_enabled=settings().enable_simulator and item.baseline_report_id is None,
    )
    if item.status in {Status.SCANNING, Status.SELLER_REVIEW}:
        scan_id = await db.scalar(select(Scan.id).where(Scan.guest_id == guest.id))
        if scan_id:
            result.photos = await photos_for_scan(db, scan_id)
    if item.status in {Status.SELLER_REVIEW, Status.COMPLETED}:
        report = await db.scalar(select(Report).where(Report.verification_id == item.id))
        if report:
            result.preview = ReportPayload.model_validate(report.payload)
            result.report_id = report.id if item.status == Status.COMPLETED else None
    return result


@guest_router.post("/exchange", response_model=GuestView)
async def exchange(verification_id: UUID, data: GuestExchange, response: Response, db: DB) -> GuestView:
    item, guest = await guest_credential(verification_id, data.token, db)
    if item.status == Status.LINK_CREATED:
        advance(db, item, Status.SELLER_OPENED, notify=True)
    set_cookie(
        response,
        GUEST_COOKIE,
        data.token,
        f"/api/v1/guest/{verification_id}",
        max(1, int((guest.expires_at - now()).total_seconds())),
    )
    return await guest_view(item, guest, db)


@guest_router.get("", response_model=GuestView)
async def seller(current: GuestSession, db: DB) -> GuestView:
    return await guest_view(*current, db)


@guest_router.post("/consent", response_model=GuestView)
async def consent(data: ConsentIn, current: GuestSession, db: DB) -> GuestView:
    item, guest = current
    recorded = await db.scalar(select(Consent).where(Consent.guest_id == guest.id))
    if recorded is None:
        advance(db, item, Status.CONSENTED)
        db.add(Consent(guest_id=guest.id, policy_version=data.policy_version))
    return await guest_view(item, guest, db)


@guest_router.post("/scan", response_model=ScanTicket)
async def start_scan(data: StartScan, current: GuestSession, db: DB) -> ScanTicket:
    item, guest = current
    if data.platform == "simulator" and (
        not settings().enable_simulator or item.baseline_report_id is not None
    ):
        raise HTTPException(403, "The simulator is disabled.")
    scan = await db.scalar(select(Scan).where(Scan.guest_id == guest.id))
    if item.status != Status.SCANNING:
        advance(db, item, Status.SCANNING, notify=True)
    if scan is None:
        scan = Scan(guest_id=guest.id, platform=data.platform)
        db.add(scan)
        await db.flush()
    else:
        if scan.platform != data.platform:
            await db.execute(delete(CaptureLink).where(CaptureLink.scan_id == scan.id))
            external = await db.scalar(select(ExternalScan.id).where(ExternalScan.scan_id == scan.id))
            if external is not None:
                await db.execute(delete(Evidence).where(Evidence.external_scan_id == external))
        scan.platform = data.platform
        await db.execute(
            update(Challenge)
            .where(Challenge.scan_id == scan.id, Challenge.consumed_at.is_(None))
            .values(consumed_at=now())
        )
    raw, record = create_challenge(db, scan, guest)
    return ScanTicket(
        scan_id=scan.id, challenge=raw, issued_at=record.created_at, expires_at=record.expires_at
    )


@guest_router.post("/submit", response_model=GuestView)
async def submit(data: Submission, current: GuestSession, db: DB) -> GuestView:
    item, guest = current
    scan = await db.scalar(select(Scan).where(Scan.id == data.scan_id, Scan.guest_id == guest.id))
    if scan is None:
        raise HTTPException(404, "Scan not found.")
    challenge = await db.scalar(
        select(Challenge).where(Challenge.token_hash == token_hash(data.challenge))
    )
    try:
        validate_challenge(challenge, scan, guest, data.platform)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if data.platform == "simulator":
        if (
            not settings().enable_simulator
            or data.fixture is None
            or data.hardware is not None
            or data.functional
        ):
            raise HTTPException(422, "Choose an enabled simulator fixture.")
        hardware = fixture_hardware(data.fixture)
        functional = [
            FunctionalReading(test="display", result="PASS", source="SIMULATED"),
            FunctionalReading(test="keyboard", result="PASS", source="SIMULATED"),
            FunctionalReading(test="speakers", result="PASS", source="SIMULATED"),
        ]
    else:
        if (
            data.hardware is None
            or data.fixture is not None
            or not (
                data.hardware.cpu
                or data.hardware.memory_gib
                or data.hardware.drives
                or data.hardware.model
            )
        ):
            raise HTTPException(422, "Submit available hardware readings from this device.")
        hardware = data.hardware
        if len({reading.test for reading in data.functional}) != len(data.functional):
            raise HTTPException(422, "Record each functional check once.")
        functional = [
            FunctionalReading(test=check.test, result=check.result, source="SELLER_OBSERVATION")
            for check in data.functional
        ]
    photos = await photos_for_scan(db, scan.id)
    if item.require_exterior and data.platform != "simulator":
        missing = set(REQUIRED_VIEWS) - {photo.angle for photo in photos}
        if missing:
            raise HTTPException(
                422,
                "Add clear exterior photos of the " + " and ".join(sorted(missing)) + " before preview.",
            )
        if len({photo.digest for photo in photos if photo.angle in REQUIRED_VIEWS}) < len(
            REQUIRED_VIEWS
        ):
            raise HTTPException(422, "Take separate photos of the front and back.")
    advance(db, item, Status.REPORT_READY, notify=True)
    advance(db, item, Status.SELLER_REVIEW)
    assert challenge is not None
    challenge.consumed_at = now()
    db.add(Snapshot(scan_id=scan.id, platform_data=hardware.model_dump(mode="json")))
    inspection = inspect(
        data.platform, hardware, claims_view(await db.get(Claim, item.id)), [p.angle for p in photos]
    )
    findings = inspection["findings"]
    requests = inspection["requests"]
    run = AgentRun(scan_id=scan.id, engine="langgraph")
    db.add(run)
    await db.flush()
    db.add_all(
        [
            AgentStep(
                run_id=run.id,
                position=1,
                action="analyze_claims",
                output={"findings": [f.model_dump() for f in findings]},
            ),
            AgentStep(
                run_id=run.id,
                position=2,
                action="determine_missing_evidence",
                output={"requests": [r.model_dump() for r in requests]},
            ),
        ]
    )
    db.add_all([FunctionalResult(scan_id=scan.id, **reading.model_dump()) for reading in functional])
    report = create_report(item, scan, hardware, findings, photos, requests, functional)
    price = pricing_provider().estimate(hardware, data.platform)
    if price:
        report.pricing = "AVAILABLE"
        report.price_estimate = price
    if item.baseline_report_id is not None:
        baseline = await valid_baseline(db, item.owner_id, item.baseline_report_id)
        report.pickup = await compare_pickup(db, baseline, report)
        report.schema_version = 3
    exclude = {"pickup"} if report.pickup is None else None
    db.add(
        Report(
            id=report.report_id,
            verification_id=item.id,
            payload=report.model_dump(mode="json", exclude=exclude),
        )
    )
    await db.flush()
    if price:
        db.add(PricingEstimate(report_id=report.report_id, **price.model_dump()))
    return await guest_view(item, guest, db)


@guest_router.post("/decision", response_model=GuestView)
async def decide(data: Decision, current: GuestSession, db: DB) -> GuestView:
    item, guest = current
    if (data.decision == "share" and item.status == Status.COMPLETED) or (
        data.decision == "decline" and item.status == Status.DECLINED
    ):
        return await guest_view(item, guest, db)
    if data.decision == "decline":
        advance(db, item, Status.DECLINED, notify=True)
    else:
        advance(db, item, Status.SHARED, notify=True)
        report = await db.scalar(select(Report).where(Report.verification_id == item.id))
        if report is None:
            raise HTTPException(409, "The report is not ready.")
        if item.baseline_report_id is not None:
            await valid_baseline(db, item.owner_id, item.baseline_report_id)
        if item.require_exterior and report.payload.get("assurance") == "COLLECTOR_REPORTED":
            payload = ReportPayload.model_validate(report.payload)
            required_ids = {
                photo.id for photo in payload.visual_evidence if photo.angle in REQUIRED_VIEWS
            }
            available = set(
                await db.scalars(
                    select(Evidence.id).where(
                        Evidence.id.in_(required_ids),
                        Evidence.expires_at > now(),
                        Evidence.jpeg.is_not(None),
                    )
                )
            )
            if len(required_ids) != len(REQUIRED_VIEWS) or available != required_ids:
                raise HTTPException(
                    409, "The required exterior photos are unavailable. Request a fresh seller link."
                )
        signature = signer().sign(report.payload)
        db.add(
            ReportSignature(
                report_id=report.id,
                digest=signature.digest,
                value=signature.value,
                key_id=signature.key_id,
            )
        )
        advance(db, item, Status.COMPLETED)
        await index_shared_report(db, item.owner_id, report)
    return await guest_view(item, guest, db)
