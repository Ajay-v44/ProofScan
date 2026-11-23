import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint

from .auth import router as auth
from .capabilities import CAPABILITIES, Capability
from .config import settings
from .db import database
from .domain import InvalidTransition
from .evidence import buyer_photos
from .evidence import router as evidence_router
from .handoff import router as handoffs
from .pricing import pricing_provider
from .reports import admin_router
from .reports import router as reports
from .services import signer
from .suggestions import router as suggestions
from .verification import guest_router, owner_router

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings()
    signer()
    pricing_provider()
    async with database().connect() as connection:
        await connection.execute(text("SELECT 1 FROM verification_requests LIMIT 1"))
    try:
        yield
    finally:
        await database().dispose()


app = FastAPI(title="ProofScan", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def protect_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    started = perf_counter()
    request_id = str(uuid4())
    length = request.headers.get("content-length", "0")
    photo = request.method == "POST" and request.url.path.endswith("/photos")
    limit = 750_000 if photo else 65_536
    if (
        request.headers.get("transfer-encoding")
        or not length.isdigit()
        or len(length) > 8
        or int(length) > limit
    ):
        return JSONResponse({"detail": "Request is too large."}, status_code=413)
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin is not None and origin != settings().web_origin.rstrip("/"):
            return JSONResponse(
                {"detail": "This site cannot submit requests to ProofScan."}, status_code=403
            )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Request-ID"] = request_id
    if request.method != "GET" or response.status_code >= 500:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        log.info(
            json.dumps(
                {
                    "event": "request",
                    "id": request_id,
                    "route": route,
                    "method": request.method,
                    "status": response.status_code,
                    "elapsed_ms": round((perf_counter() - started) * 1000),
                }
            )
        )
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
    async with database().connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/v1/platforms")
async def platforms() -> dict[str, Capability]:
    return CAPABILITIES


for router in (
    auth,
    owner_router,
    guest_router,
    reports,
    admin_router,
    evidence_router,
    buyer_photos,
    suggestions,
    handoffs,
):
    app.include_router(router, prefix="/api/v1")
