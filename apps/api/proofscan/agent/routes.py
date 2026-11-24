from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import delete, func, select

from ..auth import DB, Owner
from ..db import User, now
from .catalog import catalog_view, retrieve, store_item
from .models import AgentExecution, CatalogItem
from .recommendations import AgentContext, recommend
from .schemas import CatalogInput, CatalogView, Question, Recommendation
from .telemetry import AgentTrace

router = APIRouter(prefix="/agent", tags=["device advisor"])


@router.get("/catalog", response_model=list[CatalogView])
async def list_catalog(owner: Owner, db: DB, offset: int = 0) -> list[CatalogView]:
    if offset < 0:
        raise HTTPException(422, "Offset must be nonnegative.")
    items = await db.scalars(
        select(CatalogItem)
        .where(CatalogItem.owner_id == owner)
        .order_by(CatalogItem.created_at.desc(), CatalogItem.id.desc())
        .offset(offset)
        .limit(30)
    )
    return [catalog_view(item) for item in items]


@router.post("/catalog", response_model=CatalogView, status_code=201)
async def create_catalog_item(data: CatalogInput, owner: Owner, db: DB) -> CatalogView:
    return await store_item(owner, data, db)


@router.delete("/catalog/{item_id}", status_code=204)
async def delete_catalog_item(item_id: UUID, owner: Owner, db: DB) -> Response:
    removed = await db.scalar(
        delete(CatalogItem)
        .where(CatalogItem.id == item_id, CatalogItem.owner_id == owner)
        .returning(CatalogItem.id)
    )
    if removed is None:
        raise HTTPException(404, "Catalog entry not found.")
    return Response(status_code=204)


@router.post("/ask", response_model=Recommendation)
async def ask(data: Question, owner: Owner, db: DB) -> Recommendation:
    await db.scalar(select(User.id).where(User.id == owner).with_for_update())
    moment = now()
    count = await db.scalar(
        select(func.count())
        .select_from(AgentExecution)
        .where(
            AgentExecution.owner_id == owner,
            AgentExecution.kind == "recommend",
            AgentExecution.created_at > moment - timedelta(days=1),
        )
    )
    if (count or 0) >= 30:
        raise HTTPException(429, "You have reached today's advisor limit.")
    run = AgentExecution(
        owner_id=owner,
        kind="recommend",
        status="running",
        state={},
        expires_at=moment + timedelta(days=2),
        revision=0,
    )
    db.add(run)
    await db.commit()
    trace = AgentTrace(run.id, "recommendation")

    async def search(query: str) -> list[CatalogView]:
        return await retrieve(owner, data, query, db)

    try:
        answer = await recommend(AgentContext(data, search, trace))
    except HTTPException:
        await db.rollback()
        stored = await db.get(AgentExecution, trace.run_id)
        if stored is not None:
            stored.status = "unavailable"
            await db.commit()
        trace.publish("unavailable")
        raise
    run.status = answer.status
    run.state = {"tools": answer.tools, "model_used": answer.model_used, "retrieval": answer.retrieval}
    trace.publish(answer.status)
    return answer
