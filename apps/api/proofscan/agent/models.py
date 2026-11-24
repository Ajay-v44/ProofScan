from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, Created


class CatalogItem(Created, Base):
    __tablename__ = "agent_catalog_items"
    __table_args__ = (
        Index("ix_agent_catalog_owner_filter", "owner_id", "category", "currency", "price"),
        UniqueConstraint("report_id", name="uq_catalog_report"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text)
    price: Mapped[int | None]
    currency: Mapped[str | None] = mapped_column(String(3))
    source_url: Mapped[str | None] = mapped_column(String(600))
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id", name="fk_catalog_report"))
    facts: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))


class AgentUsage(Base):
    __tablename__ = "agent_daily_usage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    requests: Mapped[int] = mapped_column(BigInteger)
    accepted: Mapped[int] = mapped_column(BigInteger)
    model_calls: Mapped[int] = mapped_column(BigInteger)
    input_tokens: Mapped[int] = mapped_column(BigInteger)
    output_tokens: Mapped[int] = mapped_column(BigInteger)


class AgentExecution(Created, Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_agent_executions_owner_created", "owner_id", "created_at"),
        Index("ix_agent_executions_expiry", "expires_at", "id"),
        UniqueConstraint("scan_id"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    scan_id: Mapped[UUID | None] = mapped_column(ForeignKey("scan_sessions.id"))
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24))
    state: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int]
