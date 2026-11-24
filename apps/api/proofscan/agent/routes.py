from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import delete, func, select

from ..auth import DB, Owner
from ..db import User, now
from .catalog import CatalogSearch, catalog_view, retrieve, store_item
from .chat import REFUSAL, build_chat, wants_lowest
from .guardrails import sensitive_request
from .models import AgentExecution, CatalogItem
from .recommendations import AgentContext, recommend
from .report_index import backfill_owner_reports
from .schemas import CatalogInput, CatalogView, ChatRequest, ChatResponse, Question, Recommendation
from .telemetry import AgentTrace
from .usage import record_usage

router = APIRouter(prefix="/agent", tags=["device advisor"])


@router.get("/catalog", response_model=list[CatalogView])
async def list_catalog(owner: Owner, db: DB, offset: int = 0) -> list[CatalogView]:
    if offset < 0:
        raise HTTPException(422, "Offset must be nonnegative.")
    items = await db.scalars(
        select(CatalogItem)
        .where(CatalogItem.owner_id == owner, CatalogItem.report_id.is_(None))
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
        .where(CatalogItem.id == item_id, CatalogItem.owner_id == owner, CatalogItem.report_id.is_(None))
        .returning(CatalogItem.id)
    )
    if removed is None:
        raise HTTPException(404, "Catalog entry not found.")
    return Response(status_code=204)


async def start_run(owner: UUID, db: DB) -> AgentTrace:
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
        raise HTTPException(429, "You have reached today's chat limit.")
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
    return AgentTrace(run.id, "recommendation")


async def available_sources(owner: UUID, db: DB, ids: set[UUID]) -> bool:
    if not ids:
        return True
    available = await db.scalars(
        select(CatalogItem.id).where(CatalogItem.owner_id == owner, CatalogItem.id.in_(ids))
    )
    return set(available) == ids


async def finish_run(db: DB, trace: AgentTrace, status: str, state: dict) -> None:
    run = await db.get_one(AgentExecution, trace.run_id)
    run.status = status
    run.state = state
    await record_usage(db, "buyer_chat", accepted=status == "answer", trace=trace)
    await db.commit()
    trace.publish(status)


@router.post("/chat", response_model=ChatResponse)
async def chat(data: ChatRequest, owner: Owner, db: DB) -> ChatResponse:
    trace = await start_run(owner, db)

    async def search(query: Question, terms: str) -> CatalogSearch:
        await backfill_owner_reports(db, owner)
        await db.commit()
        return await retrieve(owner, query, terms, db, lowest_first=wants_lowest(query))

    async def still_owned(ids: set[UUID]) -> bool:
        return await available_sources(owner, db, ids)

    try:
        answer = await build_chat(data, trace, search, still_owned)
    except HTTPException:
        await db.rollback()
        await finish_run(db, trace, "unavailable", {})
        raise
    await finish_run(
        db, trace, answer.status, {"workflow": "chat", "steps": [event.name for event in trace.events]}
    )
    return answer


@router.post("/ask", response_model=Recommendation)
async def ask(data: Question, owner: Owner, db: DB) -> Recommendation:
    trace = await start_run(owner, db)
    if sensitive_request(data.question):
        await finish_run(db, trace, "needs_input", {})
        return Recommendation(
            status="needs_input", message=REFUSAL, retrieval="lexical", model_used=False
        )
    if data.previous_question and sensitive_request(data.previous_question):
        data = data.model_copy(update={"previous_question": None})
    await backfill_owner_reports(db, owner)
    await db.commit()

    async def search(query: str) -> CatalogSearch:
        return await retrieve(owner, data, query, db)

    try:
        answer = await recommend(AgentContext(data, search, trace))
    except HTTPException:
        await db.rollback()
        await finish_run(db, trace, "unavailable", {})
        raise
    if answer.sources:
        source_ids = {source.id for source in answer.sources}
        if not await available_sources(owner, db, source_ids):
            answer = Recommendation(
                status="needs_input",
                message="Your available evidence changed during this comparison. Ask again to use the latest reports.",
                tools=answer.tools,
                retrieval=answer.retrieval,
                model_used=answer.model_used,
            )
    await finish_run(
        db,
        trace,
        answer.status,
        {"tools": answer.tools, "model_used": answer.model_used, "retrieval": answer.retrieval},
    )
    return answer
