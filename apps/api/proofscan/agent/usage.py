from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import now
from .models import AgentUsage
from .telemetry import AgentTrace


async def record_usage(
    db: AsyncSession, kind: str, *, accepted: bool, trace: AgentTrace | None = None
) -> None:
    events = [event for event in trace.events if event.model is not None] if trace else []
    counts = {
        "requests": 1,
        "accepted": int(accepted),
        "model_calls": len(events),
        "input_tokens": sum(event.input_tokens or 0 for event in events),
        "output_tokens": sum(event.output_tokens or 0 for event in events),
    }
    statement = insert(AgentUsage).values(day=now().date(), kind=kind, **counts)
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[AgentUsage.day, AgentUsage.kind],
            set_={
                field: getattr(AgentUsage, field) + getattr(statement.excluded, field)
                for field in counts
            },
        )
    )


async def usage_totals(db: AsyncSession, since) -> list[dict]:
    rows = await db.execute(
        select(
            AgentUsage.kind,
            func.sum(AgentUsage.requests).label("requests"),
            func.sum(AgentUsage.accepted).label("accepted"),
            func.sum(AgentUsage.model_calls).label("model_calls"),
            func.sum(AgentUsage.input_tokens).label("input_tokens"),
            func.sum(AgentUsage.output_tokens).label("output_tokens"),
        )
        .where(AgentUsage.day >= since)
        .group_by(AgentUsage.kind)
        .order_by(AgentUsage.kind)
    )
    return [dict(row) for row in rows.mappings()]
