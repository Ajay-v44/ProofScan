import hashlib
import secrets
from datetime import timedelta
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import Challenge, Claim, Evidence, ExternalScan, Guest, Notification, Scan, Verification, now
from .domain import Status, transition
from .schemas import Claims, Finding, FunctionalReading, Hardware, PhotoView, ReportPayload, TestRequest
from .signing import Signer

GUEST_SCOPE = "verification:seller"
POLICY_VERSION = "2026-11-23"


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


@lru_cache
def signer() -> Signer:
    config = settings()
    return Signer(
        config.report_private_key.get_secret_value(), config.report_key_id, config.report_trusted_keys
    )


def advance(
    db: AsyncSession, verification: Verification, state: Status, *, notify: bool = False
) -> None:
    verification.status = transition(verification.status, state)
    if notify:
        db.add(
            Notification(owner_id=verification.owner_id, verification_id=verification.id, event=state)
        )


def validate_challenge(challenge: Challenge | None, scan: Scan, guest: Guest, platform: str) -> None:
    if (
        challenge is None
        or challenge.scan_id != scan.id
        or scan.guest_id != guest.id
        or scan.platform != platform
    ):
        raise ValueError("This challenge does not match the scan.")
    if challenge.consumed_at is not None:
        raise ValueError("This challenge was already used.")
    if challenge.expires_at <= now():
        raise ValueError("This challenge expired. Start a fresh scan.")


def create_challenge(db: AsyncSession, scan: Scan, guest: Guest) -> tuple[str, Challenge]:
    raw, digest = new_token()
    issued = now()
    record = Challenge(
        scan_id=scan.id,
        token_hash=digest,
        created_at=issued,
        expires_at=min(issued + timedelta(minutes=15), guest.expires_at),
    )
    db.add(record)
    return raw, record


def claims_view(claim: Claim | None) -> Claims:
    if claim is None:
        return Claims()
    return Claims(
        memory_gib=claim.memory_gib, storage_gb=claim.storage_gb, battery_percent=claim.battery_percent
    )


def photo_view(item: Evidence) -> PhotoView:
    return PhotoView.model_validate(item, from_attributes=True)


async def photos_for_scan(db: AsyncSession, scan_id: UUID) -> list[PhotoView]:
    rows = await db.scalars(
        select(Evidence)
        .join(ExternalScan)
        .where(ExternalScan.scan_id == scan_id)
        .order_by(Evidence.angle)
    )
    return [photo_view(row) for row in rows]


def create_report(
    verification: Verification,
    scan: Scan,
    hardware: Hardware,
    findings: list[Finding],
    photos: list[PhotoView],
    requests: list[TestRequest],
    functional: list[FunctionalReading],
) -> ReportPayload:
    return ReportPayload.model_validate(
        {
            "schema_version": 2,
            "report_id": uuid4(),
            "verification_id": verification.id,
            "captured_at": now(),
            "label": verification.label,
            "platform": scan.platform,
            "hardware": hardware.model_dump(),
            "assurance": "SIMULATED" if scan.platform == "simulator" else "COLLECTOR_REPORTED",
            "findings": [finding.model_dump() for finding in findings],
            "visual_evidence": photos,
            "inspection_requests": requests,
            "functional": functional,
        }
    )


def fixture_hardware(name: str) -> Hardware:
    verified = name == "verified"
    return Hardware.model_validate(
        {
            "manufacturer": "ProofScan demo",
            "model": "Sample laptop",
            "cpu": ["Sample 8-core CPU"],
            "gpu": ["Sample integrated graphics"],
            "memory_gib": 16 if verified else 8,
            "drives": [{"model": "Sample SSD", "capacity_gb": 1000 if verified else 512}],
            "battery_health_percent": 90 if verified else 69,
        }
    )
