import argparse
import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select

from ..config import settings
from ..db import database, session_factory
from .catalog import embedding_model, vector_for, write_vector
from .device import ToolChoice
from .model import decide
from .models import CatalogItem
from .telemetry import AgentTrace


async def reindex() -> int:
    factory = session_factory()
    last: UUID | None = None
    total = 0
    try:
        while True:
            page = (
                select(CatalogItem.id, CatalogItem.title, CatalogItem.notes)
                .order_by(CatalogItem.id)
                .limit(20)
            )
            if last is not None:
                page = page.where(CatalogItem.id > last)
            async with factory() as db:
                items = (await db.execute(page)).all()
            if not items:
                return total
            for item, title, notes in items:
                vector = await vector_for(title + "\n" + notes, query=False)
                async with factory.begin() as db:
                    await write_vector(db, item, vector)
                last = item
                total += 1
    finally:
        await database().dispose()


async def probe(production: bool) -> None:
    config = settings()
    model = config.agent_model if production else config.agent_test_model
    trace = AgentTrace(uuid4(), "probe")
    result = await decide(
        "This is a connection test. Return JSON matching the response_schema. Choose the sole available tool.",
        {"available": ["model_name"], "response_schema": ToolChoice.model_json_schema()},
        ToolChoice,
        trace,
        approved=True,
        model=model,
    )
    if result is None or result.tool != "model_name":
        raise SystemExit(f"{model} did not return the expected tool decision.")
    print(f"{model} returned a valid decision.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the ProofScan device catalog")
    parser.add_argument("action", choices=["warm", "reindex", "probe"])
    parser.add_argument(
        "--production", action="store_true", help="Probe AGENT_MODEL instead of AGENT_TEST_MODEL"
    )
    command = parser.parse_args()
    if command.action == "warm":
        model = embedding_model(settings().agent_embedding_cache, local_only=False)
        next(iter(model.passage_embed(["ProofScan embedding warmup"])))
        print("Embedding model cached.")
    elif command.action == "reindex":
        print(f"Processed {asyncio.run(reindex())} catalog entries.")
    else:
        asyncio.run(probe(command.production))


if __name__ == "__main__":
    main()
