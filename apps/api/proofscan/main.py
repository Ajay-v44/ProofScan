import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .account import router as account
from .account_deletion import router as account_deletion
from .agent.device import router as device_agent
from .agent.routes import router as advisor
from .agent.telemetry import flush_telemetry
from .auth import router as auth
from .capabilities import CAPABILITIES, Capability
from .config import settings
from .db import database
from .domain import InvalidTransition
from .evidence import buyer_photos, capture
from .evidence import router as evidence_router
from .handoff import router as handoffs
from .pricing import pricing_provider
from .reports import admin_router
from .reports import router as reports
from .request_policy import RequestPolicy, response_headers
from .services import signer
from .suggestions import router as suggestions
from .verification import guest_router, owner_router


@lru_cache(maxsize=1)
def migration_heads() -> frozenset[str]:
    return frozenset(
        ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads()
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings()
    signer()
    pricing_provider()
    migration_heads()
    try:
        yield
    finally:
        await database().dispose()
        await asyncio.to_thread(flush_telemetry)


app = FastAPI(title="ProofScan", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestPolicy, web_origin=lambda: settings().web_origin.rstrip("/"))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, _: Exception) -> JSONResponse:
    response = JSONResponse({"detail": "ProofScan could not complete that request."}, status_code=500)
    response_headers(response.headers, getattr(request.state, "request_id", None) or str(uuid4()))
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = [".".join(str(part) for part in issue["loc"][1:]) for issue in exc.errors()]
    return JSONResponse({"detail": "Check the submitted fields.", "fields": problems}, status_code=422)


@app.exception_handler(InvalidTransition)
async def invalid_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        async with asyncio.timeout(3), database().connect() as connection:
            versions = frozenset(
                await connection.scalars(text("SELECT version_num FROM alembic_version"))
            )
    except (SQLAlchemyError, TimeoutError, OSError) as exc:
        raise HTTPException(503, "Database readiness check failed.") from exc
    if versions != migration_heads():
        raise HTTPException(503, "Database schema does not match this release.")
    return {"status": "ok"}


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/platforms")
async def platforms() -> dict[str, Capability]:
    return CAPABILITIES


for router in (
    auth,
    account,
    account_deletion,
    owner_router,
    guest_router,
    reports,
    admin_router,
    evidence_router,
    capture,
    buyer_photos,
    suggestions,
    handoffs,
    advisor,
    device_agent,
):
    app.include_router(router, prefix="/api/v1")
