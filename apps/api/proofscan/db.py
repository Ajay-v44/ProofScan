from collections.abc import AsyncIterator
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Created:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Created, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(180))


class Verification(Created, Base):
    __tablename__ = "verification_requests"
    __table_args__ = (Index("ix_verification_owner_created", "owner_id", "created_at"),)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Claim(Base):
    __tablename__ = "listing_claims"

    verification_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_requests.id"), primary_key=True
    )
    memory_gib: Mapped[int | None]
    storage_gb: Mapped[int | None]
    battery_percent: Mapped[int | None]


class Guest(Created, Base):
    __tablename__ = "guest_sessions"

    verification_id: Mapped[UUID] = mapped_column(ForeignKey("verification_requests.id"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scope: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Consent(Created, Base):
    __tablename__ = "seller_consents"

    guest_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), unique=True)
    policy_version: Mapped[str] = mapped_column(String(30))


class Scan(Created, Base):
    __tablename__ = "scan_sessions"

    guest_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), unique=True)
    platform: Mapped[str] = mapped_column(String(20))


class Challenge(Created, Base):
    __tablename__ = "scan_challenges"

    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scan_sessions.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Snapshot(Created, Base):
    __tablename__ = "hardware_snapshots"

    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scan_sessions.id"), unique=True)
    platform_data: Mapped[dict] = mapped_column(JSONB)


class ExternalScan(Created, Base):
    __tablename__ = "external_scan_sessions"

    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scan_sessions.id"), unique=True)


class FunctionalResult(Created, Base):
    __tablename__ = "functional_test_results"
    __table_args__ = (UniqueConstraint("scan_id", "test"),)

    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scan_sessions.id"))
    test: Mapped[str] = mapped_column(String(16))
    result: Mapped[str] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(24))


class Evidence(Created, Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("external_scan_id", "angle"),)

    external_scan_id: Mapped[UUID] = mapped_column(ForeignKey("external_scan_sessions.id"))
    angle: Mapped[str] = mapped_column(String(8))
    digest: Mapped[str] = mapped_column(String(64))
    width: Mapped[int]
    height: Mapped[int]
    brightness: Mapped[int]
    sharpness: Mapped[int]
    jpeg: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AgentRun(Created, Base):
    __tablename__ = "agent_runs"

    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scan_sessions.id"), unique=True)
    engine: Mapped[str] = mapped_column(String(24))


class AgentStep(Created, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("run_id", "position"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"))
    position: Mapped[int]
    action: Mapped[str] = mapped_column(String(32))
    output: Mapped[dict] = mapped_column(JSONB)


class ModelCall(Created, Base):
    __tablename__ = "model_calls"
    __table_args__ = (Index("ix_model_calls_owner_created", "owner_id", "created_at"),)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    accepted: Mapped[bool]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]


class Report(Created, Base):
    __tablename__ = "reports"

    verification_id: Mapped[UUID] = mapped_column(ForeignKey("verification_requests.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class ReportSignature(Base):
    __tablename__ = "report_signatures"

    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(100))
    key_id: Mapped[str] = mapped_column(String(64))


class PricingEstimate(Created, Base):
    __tablename__ = "pricing_estimates"

    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), unique=True)
    source: Mapped[str] = mapped_column(String(24))
    currency: Mapped[str] = mapped_column(String(3))
    low: Mapped[int]
    high: Mapped[int]
    sample_size: Mapped[int]


class Invalidation(Base):
    __tablename__ = "report_invalidations"

    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Created, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_owner_created", "owner_id", "created_at"),
        CheckConstraint(
            "(verification_id IS NOT NULL) <> (handoff_id IS NOT NULL)", name="ck_notification_target"
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    verification_id: Mapped[UUID | None] = mapped_column(ForeignKey("verification_requests.id"))
    handoff_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("handoffs.id", name="fk_notifications_handoff")
    )
    event: Mapped[str] = mapped_column(String(24))


class Audit(Created, Base):
    __tablename__ = "admin_audit_logs"

    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    reason: Mapped[str] = mapped_column(String(280))


@lru_cache
def database():
    return create_async_engine(settings().database_url, pool_pre_ping=True, hide_parameters=True)


async def session() -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(database(), expire_on_commit=False)
    async with factory() as db, db.begin():
        yield db
