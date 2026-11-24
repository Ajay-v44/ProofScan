import asyncio

import httpx
import pytest
from fastapi import HTTPException
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from proofscan import request_policy
from proofscan.blocking_work import WorkBudget
from proofscan.request_policy import MAX_BODY_BYTES, RequestPolicy


async def echo(request: Request) -> JSONResponse:
    return JSONResponse({"size": len(await request.body())})


@pytest.fixture
async def client():
    app = Starlette(routes=[Route("/body", echo, methods=["POST"])])
    app.add_middleware(RequestPolicy, web_origin=lambda: "https://workspace.example")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_streaming_body_is_replayed_and_measured(client):
    async def body(size: int):
        yield b"a" * MAX_BODY_BYTES
        yield b"b" * size

    valid = await client.post("/body", content=body(0))
    assert valid.json() == {"size": MAX_BODY_BYTES}

    rejected = await client.post("/body", content=body(1))
    assert rejected.status_code == 413
    assert rejected.headers["cache-control"] == "no-store"
    assert rejected.headers["x-request-id"] != valid.headers["x-request-id"]


async def test_size_mismatch_and_cross_origin_are_rejected(client):
    mismatch = await client.post("/body", content=b"body", headers={"Content-Length": "1"})
    assert mismatch.status_code == 400
    denied = await client.post("/body", content=b"body", headers={"Origin": "https://other.example"})
    assert denied.status_code == 403
    assert "x-request-id" in denied.headers


async def test_body_deadline_applies_before_handler(client, monkeypatch):
    async def slow():
        await asyncio.sleep(1)
        yield b"tiny"

    monkeypatch.setattr(request_policy, "BODY_TIMEOUT_SECONDS", 0.01)
    result = await client.post("/body", content=slow())
    assert result.status_code == 408


async def test_blocking_work_rejects_excess_and_releases_capacity():
    from threading import Event

    started = asyncio.Event()
    finish = Event()
    loop = asyncio.get_running_loop()

    def job():
        loop.call_soon_threadsafe(started.set)
        return finish.wait(5)

    budget = WorkBudget(1)
    first = asyncio.create_task(budget.run(job))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        with pytest.raises(HTTPException) as failure:
            await budget.run(lambda: "busy")
        assert failure.value.status_code == 503
    finally:
        finish.set()
        assert await first
    assert await budget.run(lambda: "available") == "available"
