import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from ..blocking_work import WorkBudget
from ..config import settings
from ..db import User
from .models import CatalogItem
from .schemas import CatalogInput, CatalogView, Question, RetrievalMode

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_SIZE = 384
CATALOG_LIMIT = 2_000
SEARCH_LIMIT = 6
embedding_work = WorkBudget(slots=2)
log = logging.getLogger(__name__)
STOP_WORDS = {"the", "for", "and", "best", "what", "which", "recommend", "consider", "from", "should"}
MEASUREMENTS = (
    ({"battery"}, "battery_health_percent", "battery health"),
    ({"memory", "ram"}, "memory_gib", "memory"),
    ({"storage", "disk", "ssd"}, "storage_gb", "storage capacity"),
)


class VectorUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogSearch:
    items: list[CatalogView]
    mode: RetrievalMode


def requested_measurement(question: Question) -> tuple[str, str] | None:
    for text_value in (question.question, question.previous_question or ""):
        terms = set(re.findall(r"[a-z]+", text_value.lower()))
        for keywords, field, label in MEASUREMENTS:
            if keywords & terms:
                return field, label
    return None


@lru_cache(maxsize=2)
def embedding_model(cache: Path, *, local_only: bool):
    from fastembed import TextEmbedding  # type: ignore[import-not-found]

    return TextEmbedding(
        model_name=EMBEDDING_MODEL, cache_dir=str(cache), threads=2, local_files_only=local_only
    )


def encode(text_value: str, *, query: bool) -> str:
    model = embedding_model(settings().agent_embedding_cache, local_only=True)
    embeddings = model.query_embed(text_value) if query else model.passage_embed([text_value])
    values = next(iter(embeddings))
    if len(values) != EMBEDDING_SIZE:
        raise ValueError("Unexpected embedding dimension")
    return "[" + ",".join(format(float(value), ".8g") for value in values) + "]"


async def vector_for(text_value: str, *, query: bool) -> str:
    try:
        return await embedding_work.run(encode, text_value, query=query)
    except (ImportError, RuntimeError, OSError, ValueError) as exc:
        raise VectorUnavailable("The local embedding model is unavailable") from exc


def catalog_view(item: CatalogItem) -> CatalogView:
    return CatalogView.model_validate(item, from_attributes=True)


async def store_item(owner: UUID, data: CatalogInput, db: AsyncSession) -> CatalogView:
    await db.commit()
    vector = None
    if settings().agent_vector_enabled:
        try:
            vector = await vector_for(data.title + "\n" + data.notes, query=False)
        except VectorUnavailable:
            log.info("Saved listing will be available through text search")
    await db.scalar(select(User.id).where(User.id == owner).with_for_update())
    count = await db.scalar(
        select(func.count())
        .select_from(CatalogItem)
        .where(CatalogItem.owner_id == owner, CatalogItem.report_id.is_(None))
    )
    if (count or 0) >= CATALOG_LIMIT:
        raise HTTPException(409, "Your device catalog is full. Remove an item first.")
    item = CatalogItem(owner_id=owner, **data.model_dump())
    db.add(item)
    await db.flush()
    if vector is not None:
        try:
            async with db.begin_nested():
                await write_vector(db, item.id, vector)
        except ProgrammingError:
            log.info("Saved listing vector was deferred")
    return catalog_view(item)


async def write_vector(db: AsyncSession, item_id: UUID, embedding: str) -> None:
    await db.execute(
        text("""
                INSERT INTO agent_catalog_vectors (item_id, embedding, model)
                SELECT id, CAST(CAST(:embedding AS text) AS public.vector), :model
                FROM agent_catalog_items WHERE id = :item
                ON CONFLICT (item_id) DO UPDATE
                SET embedding = EXCLUDED.embedding, model = EXCLUDED.model
        """),
        {"item": item_id, "embedding": embedding, "model": EMBEDDING_MODEL},
    )


async def retrieve(owner: UUID, question: Question, search_text: str, db: AsyncSession) -> CatalogSearch:
    terms = [term for term in re.findall(r"[^\W_]{2,32}", search_text.lower()) if term not in STOP_WORDS]
    terms = list(dict.fromkeys(terms))[:20]
    measurement = requested_measurement(question)
    metadata: dict[str, object] = {
        "owner": owner,
        "category": question.category,
        "currency": question.currency,
        "budget": question.budget,
        "terms": " | ".join(terms),
        "limit": SEARCH_LIMIT,
        "metric": measurement[0] if measurement else None,
        "reports_only": question.reports_only,
    }
    if settings().agent_vector_enabled:
        try:
            return CatalogSearch(await semantic_search(db, search_text, metadata), "pgvector")
        except (VectorUnavailable, ProgrammingError):
            await db.rollback()
            log.warning("Semantic search unavailable. Using catalog text search")
    statement = text(f"""
        SELECT item.id, item.category, item.title, item.notes, item.price, item.currency, item.source_url,
               verification.id AS verification_id, item.facts
        FROM agent_catalog_items item
        {REPORT_JOINS}
        WHERE {ELIGIBLE}
        ORDER BY {NUMERIC_ORDER}, ts_rank_cd(to_tsvector('simple', item.title || ' ' || item.notes),
            to_tsquery('simple', NULLIF(:terms, ''))) DESC NULLS LAST,
            item.created_at DESC, item.id DESC
        LIMIT :limit
    """)
    rows = (await db.execute(statement, metadata)).mappings().all()
    await db.commit()
    return CatalogSearch([CatalogView.model_validate(row) for row in rows], "lexical")


ELIGIBLE = """
        item.owner_id = :owner AND (CAST(:category AS text) IS NULL OR item.category = :category)
        AND (CAST(:budget AS integer) IS NULL OR (item.currency = :currency AND item.price <= :budget))
        AND (NOT CAST(:reports_only AS boolean) OR item.report_id IS NOT NULL)
        AND (item.report_id IS NULL OR (
            verification.owner_id = :owner AND verification.status = 'COMPLETED'
            AND signature.report_id IS NOT NULL AND invalidation.report_id IS NULL
        ))
"""
REPORT_JOINS = """
        LEFT JOIN reports report ON report.id = item.report_id
        LEFT JOIN verification_requests verification ON verification.id = report.verification_id
        LEFT JOIN report_signatures signature ON signature.report_id = report.id
        LEFT JOIN report_invalidations invalidation ON invalidation.report_id = report.id
"""
NUMERIC_ORDER = "CAST(item.facts ->> CAST(:metric AS text) AS integer) DESC NULLS LAST"


async def semantic_search(
    db: AsyncSession, search_text: str, metadata: dict[str, object]
) -> list[CatalogView]:
    if await db.scalar(text("SELECT to_regclass('agent_catalog_vectors')")) is None:
        raise VectorUnavailable("The PostgreSQL vector table is missing")
    metadata = {**metadata, "model": EMBEDDING_MODEL}
    pending = (
        await db.execute(
            text(f"""
            SELECT item.id, item.title, item.notes
            FROM agent_catalog_items item
            {REPORT_JOINS}
            LEFT JOIN agent_catalog_vectors vectors ON vectors.item_id = item.id AND vectors.model = :model
            WHERE {ELIGIBLE} AND vectors.item_id IS NULL
            ORDER BY item.created_at DESC, item.id DESC LIMIT 2
            """),
            metadata,
        )
    ).all()
    await db.commit()
    for item_id, title, notes in pending:
        embedding = await vector_for(title + "\n" + notes, query=False)
        await write_vector(db, item_id, embedding)
        await db.commit()
    metadata["embedding"] = await vector_for(search_text, query=True)
    # The materialized result contains only records that already passed the access and budget checks.
    statement = text(f"""
            WITH eligible AS MATERIALIZED (
                SELECT item.id, item.category, item.title, item.notes, item.price,
                       item.currency, item.source_url, item.created_at, vectors.embedding,
                       verification.id AS verification_id, item.facts
                FROM agent_catalog_items item
                {REPORT_JOINS}
                LEFT JOIN agent_catalog_vectors vectors
                    ON vectors.item_id = item.id AND vectors.model = :model
                WHERE {ELIGIBLE}
            )
            SELECT item.id, item.category, item.title, item.notes, item.price, item.currency, item.source_url,
                   item.verification_id, item.facts
            FROM eligible item
            ORDER BY {NUMERIC_ORDER}, COALESCE(1 - (item.embedding OPERATOR(public.<=>)
                CAST(CAST(:embedding AS text) AS public.vector)), 0)
                + CASE WHEN to_tsvector('simple', item.title || ' ' || item.notes)
                    @@ to_tsquery('simple', NULLIF(:terms, '')) THEN 0.25 ELSE 0 END DESC,
                item.created_at DESC, item.id DESC
            LIMIT :limit
        """)
    rows = (await db.execute(statement, metadata)).mappings().all()
    await db.commit()
    return [CatalogView.model_validate(row) for row in rows]
