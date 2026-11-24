import re
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
from .schemas import CatalogInput, CatalogView, Question

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_SIZE = 384
CATALOG_LIMIT = 2_000
SEARCH_LIMIT = 6
embedding_work = WorkBudget(slots=2)
STOP_WORDS = {"the", "for", "and", "best", "what", "which", "recommend", "consider", "from", "should"}


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
        raise HTTPException(503, "The local semantic index is unavailable.") from exc


def catalog_view(item: CatalogItem) -> CatalogView:
    return CatalogView.model_validate(item, from_attributes=True)


async def store_item(owner: UUID, data: CatalogInput, db: AsyncSession) -> CatalogView:
    await db.commit()
    vector = (
        await vector_for(data.title + "\n" + data.notes, query=False)
        if settings().agent_vector_enabled
        else None
    )
    await db.scalar(select(User.id).where(User.id == owner).with_for_update())
    count = await db.scalar(
        select(func.count()).select_from(CatalogItem).where(CatalogItem.owner_id == owner)
    )
    if (count or 0) >= CATALOG_LIMIT:
        raise HTTPException(409, "Your device catalog is full. Remove an item first.")
    item = CatalogItem(owner_id=owner, **data.model_dump())
    db.add(item)
    await db.flush()
    if vector is not None:
        await write_vector(db, item.id, vector)
    return catalog_view(item)


async def write_vector(db: AsyncSession, item_id: UUID, embedding: str) -> None:
    try:
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
    except ProgrammingError as exc:
        raise HTTPException(503, "The PostgreSQL vector index has not been provisioned.") from exc


async def retrieve(
    owner: UUID, question: Question, search_text: str, db: AsyncSession
) -> list[CatalogView]:
    terms = [term for term in re.findall(r"[^\W_]{2,32}", search_text.lower()) if term not in STOP_WORDS]
    terms = list(dict.fromkeys(terms))[:20]
    metadata = {
        "owner": owner,
        "category": question.category,
        "currency": question.currency,
        "budget": question.budget,
        "terms": " | ".join(terms),
        "limit": SEARCH_LIMIT,
    }
    filters = """
        item.owner_id = :owner AND item.category = :category
        AND (CAST(:budget AS integer) IS NULL OR (item.currency = :currency AND item.price <= :budget))
    """
    order = """
        ts_rank_cd(to_tsvector('simple', item.title || ' ' || item.notes),
            to_tsquery('simple', NULLIF(:terms, ''))) DESC NULLS LAST
    """
    if settings().agent_vector_enabled:
        metadata["embedding"] = await vector_for(search_text, query=True)
        metadata["model"] = EMBEDDING_MODEL
        # Filter by owner and budget before similarity scoring. No public or cross-owner fallback.
        statement = text(f"""
            WITH eligible AS MATERIALIZED (
                SELECT item.id, item.category, item.title, item.notes, item.price,
                       item.currency, item.source_url, item.created_at, vectors.embedding
                FROM agent_catalog_items item
                LEFT JOIN agent_catalog_vectors vectors
                    ON vectors.item_id = item.id AND vectors.model = :model
                WHERE {filters}
            )
            SELECT item.id, item.category, item.title, item.notes, item.price, item.currency, item.source_url
            FROM eligible item
            ORDER BY COALESCE(1 - (item.embedding OPERATOR(public.<=>)
                CAST(CAST(:embedding AS text) AS public.vector)), 0)
                + CASE WHEN to_tsvector('simple', item.title || ' ' || item.notes)
                    @@ to_tsquery('simple', NULLIF(:terms, '')) THEN 0.25 ELSE 0 END DESC,
                item.created_at DESC, item.id DESC
            LIMIT :limit
        """)
    else:
        statement = text(f"""
            SELECT item.id, item.category, item.title, item.notes, item.price, item.currency, item.source_url
            FROM agent_catalog_items item
            WHERE {filters}
            ORDER BY {order}, item.created_at DESC, item.id DESC
            LIMIT :limit
        """)
    try:
        rows = (await db.execute(statement, metadata)).mappings().all()
    except ProgrammingError as exc:
        if settings().agent_vector_enabled:
            raise HTTPException(503, "The PostgreSQL vector index has not been provisioned.") from exc
        raise
    await db.commit()
    return [CatalogView.model_validate(row) for row in rows]
