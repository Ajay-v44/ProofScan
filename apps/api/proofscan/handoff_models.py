from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Created


class Asset(Created, Base):
    __tablename__ = "assets"

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(16))


class Handoff(Created, Base):
    __tablename__ = "handoffs"
    __table_args__ = (Index("ix_handoff_owner_created", "owner_id", "created_at", "id"),)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), unique=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24))


class Checkpoint(Created, Base):
    __tablename__ = "handoff_checkpoints"
    __table_args__ = (
        UniqueConstraint("handoff_id", "phase"),
        Index(
            "ix_checkpoint_pending_purge",
            "photo_expires_at",
            "id",
            postgresql_where=text("jpeg IS NOT NULL"),
        ),
    )

    handoff_id: Mapped[UUID] = mapped_column(ForeignKey("handoffs.id"))
    phase: Mapped[str] = mapped_column(String(12))
    hardware: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    condition: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(String(400))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    photo_digest: Mapped[str | None] = mapped_column(String(64))
    jpeg: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    photo_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ticket_digest: Mapped[str | None] = mapped_column(String(64))
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Acceptance(Created, Base):
    __tablename__ = "handoff_acceptances"

    handoff_id: Mapped[UUID] = mapped_column(ForeignKey("handoffs.id"), unique=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckpointPhoto(Created, Base):
    __tablename__ = "handoff_checkpoint_photos"
    __table_args__ = (UniqueConstraint("checkpoint_id", "angle"),)

    checkpoint_id: Mapped[UUID] = mapped_column(ForeignKey("handoff_checkpoints.id"))
    angle: Mapped[str] = mapped_column(String(8))
    digest: Mapped[str] = mapped_column(String(64))
    jpeg: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    descriptor: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), deferred=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Comparison(Created, Base):
    __tablename__ = "comparison_results"

    handoff_id: Mapped[UUID] = mapped_column(ForeignKey("handoffs.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(100))
    key_id: Mapped[str] = mapped_column(String(64))


class ComparisonInvalidation(Base):
    __tablename__ = "comparison_invalidations"

    report_id: Mapped[UUID] = mapped_column(ForeignKey("comparison_results.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
