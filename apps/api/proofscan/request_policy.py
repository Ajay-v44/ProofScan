import asyncio
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .visual import MAX_PHOTO_BYTES

log = logging.getLogger("uvicorn.error")
MAX_BODY_BYTES = 65_536
BODY_TIMEOUT_SECONDS = 15
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def response_headers(headers: MutableHeaders, request_id: str) -> None:
    headers["Cache-Control"] = "no-store"
    headers["Referrer-Policy"] = "no-referrer"
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Request-ID"] = request_id


class InvalidBody(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status


async def read_body(receive: Receive, headers: Headers, limit: int) -> bytes | None:
    lengths = headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and headers.get("transfer-encoding")):
        raise InvalidBody(400, "Invalid request body length.")
    expected = None
    if lengths:
        value = lengths[0]
        if not value.isascii() or not value.isdecimal() or len(value) > 8:
            raise InvalidBody(400, "Invalid request body length.")
        expected = int(value)
        if expected > limit:
            raise InvalidBody(413, "Request is too large.")

    body = bytearray()
    try:
        async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return None
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > limit:
                    raise InvalidBody(413, "Request is too large.")
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
    except TimeoutError as exc:
        raise InvalidBody(408, "Request body took too long to arrive.") from exc
    if expected is not None and expected != len(body):
        raise InvalidBody(400, "Invalid request body length.")
    return bytes(body)


class RequestPolicy:
    def __init__(self, app: ASGIApp, web_origin: Callable[[], str]):
        self.app = app
        self.web_origin = web_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        method = scope["method"]
        request_headers = Headers(scope=scope)
        status = None

        async def respond(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers(MutableHeaders(scope=message), request_id)
            await send(message)

        try:
            origin = request_headers.get("origin")
            if method in WRITE_METHODS and origin is not None and origin != self.web_origin():
                raise InvalidBody(403, "This site cannot submit requests to ProofScan.")
            photo = method == "POST" and scope["path"].rstrip("/").endswith("/photos")
            body = await read_body(
                receive, request_headers, MAX_PHOTO_BYTES if photo else MAX_BODY_BYTES
            )
            if body is None:
                return

            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay, respond)
        except InvalidBody as exc:
            await JSONResponse({"detail": str(exc)}, status_code=exc.status)(scope, receive, respond)
        except Exception:
            if status is None:
                status = 500
            raise
        finally:
            if status is not None and (method != "GET" or status >= 400):
                log.info(
                    json.dumps(
                        {
                            "event": "request",
                            "id": request_id,
                            "route": getattr(scope.get("route"), "path", "unmatched"),
                            "method": method,
                            "status": status,
                            "elapsed_ms": round((perf_counter() - started) * 1000),
                        }
                    )
                )
