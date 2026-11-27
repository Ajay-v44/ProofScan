import asyncio
import hashlib
import hmac
import secrets
from datetime import timedelta
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .blocking_work import WorkBudget
from .config import settings
from .db import User, now, session
from .schemas import Credentials
from .signing import decode, encode

DB = Annotated[AsyncSession, Depends(session, scope="function")]
COOKIE = "proofscan_session"
router = APIRouter(prefix="/auth", tags=["authentication"])
password_work = WorkBudget(slots=4)


def password_digest(password: str, salt: bytes) -> str:
    return encode(hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1))


def local_key() -> str:
    key = settings().local_auth_secret
    if key is None:
        raise RuntimeError("Local authentication requires LOCAL_AUTH_SECRET")
    return key.get_secret_value()


@lru_cache
def jwks(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5)


async def session_claims(token: str) -> dict[str, Any]:
    config = settings()
    try:
        if config.auth_mode == "supabase":
            issuer = f"{config.supabase_url.rstrip('/')}/auth/v1"
            key = await asyncio.to_thread(jwks(issuer).get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                issuer=issuer,
                audience="authenticated",
                options={"require": ["sub", "exp", "iat"]},
            )
        else:
            claims = jwt.decode(
                token,
                local_key(),
                algorithms=["HS256"],
                issuer="proofscan-local",
                options={"require": ["sub", "exp", "iat"]},
            )
        UUID(claims["sub"])
        return claims
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Sign-in service is unavailable.") from exc
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise HTTPException(401, "Your session has expired. Sign in again.") from exc


async def subject(token: str) -> UUID:
    return UUID((await session_claims(token))["sub"])


async def current_user(request: Request, db: DB) -> UUID:
    header = request.headers.get("Authorization", "")
    token = (
        header.removeprefix("Bearer ") if header.startswith("Bearer ") else request.cookies.get(COOKIE)
    )
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    claims = await session_claims(token)
    user = UUID(claims["sub"])
    if settings().auth_mode == "local":
        version = await db.scalar(select(User.session_version).where(User.id == user))
        if version is None or claims.get("v", 0) != version:
            raise HTTPException(401, "Sign in again.")
    elif await db.scalar(select(User.id).where(User.id == user)) is None:
        await db.execute(insert(User).values(id=user).on_conflict_do_nothing(index_elements=["id"]))
    if isinstance(claims.get("email"), str):
        request.state.account_email = claims["email"]
    return user


Owner = Annotated[UUID, Depends(current_user)]


async def admin_user(user: Owner) -> UUID:
    if user not in settings().admin_subjects:
        raise HTTPException(403, "Operator access required.")
    return user


Admin = Annotated[UUID, Depends(admin_user)]


def set_cookie(response: Response, name: str, value: str, path: str, ttl: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=ttl,
        path=path,
        httponly=True,
        samesite="strict",
        secure=settings().web_origin.startswith("https://"),
    )


def login(response: Response, user: UUID, version: int = 0) -> dict[str, str]:
    issued = now()
    token = jwt.encode(
        {
            "sub": str(user),
            "iat": issued,
            "exp": issued + timedelta(hours=8),
            "iss": "proofscan-local",
            "v": version,
        },
        local_key(),
        algorithm="HS256",
    )
    set_cookie(response, COOKIE, token, "/", 28_800)
    return {"user_id": str(user)}


async def supabase_login(data: Credentials, response: Response, *, signup: bool) -> dict[str, str]:
    config = settings()
    key = config.supabase_publishable_key
    assert key is not None
    endpoint = "signup" if signup else "token?grant_type=password"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            result = await client.post(
                f"{config.supabase_url.rstrip('/')}/auth/v1/{endpoint}",
                headers={"apikey": key.get_secret_value()},
                json=data.model_dump(),
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, "Sign-in service is unavailable.") from exc
    if result.status_code == 429 or result.status_code >= 500:
        raise HTTPException(503, "Sign-in service is unavailable.")
    if not result.is_success:
        raise HTTPException(
            400 if signup else 401, "Could not create account." if signup else "Invalid sign-in."
        )
    try:
        payload = result.json()
        token = payload.get("access_token")
        if signup and token is None:
            return {"message": "Check your email to confirm your account, then sign in."}
        lifetime = int(payload.get("expires_in", 3600))
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(503, "Sign-in service is unavailable.") from exc
    if not isinstance(token, str) or not token or lifetime <= 0:
        raise HTTPException(503, "Sign-in service is unavailable.")
    user = await subject(token)
    set_cookie(response, COOKIE, token, "/", min(lifetime, 3600))
    return {"user_id": str(user)}


@router.post("/register", status_code=201)
async def register(data: Credentials, response: Response, db: DB) -> dict[str, str]:
    if settings().auth_mode == "supabase":
        return await supabase_login(data, response, signup=True)
    salt = secrets.token_bytes(16)
    digest = await password_work.run(password_digest, data.password, salt)
    insert_user = (
        insert(User)
        .values(email=data.email, password_hash=f"{encode(salt)}.{digest}")
        .on_conflict_do_nothing(index_elements=["email"])
        .returning(User.id)
    )
    user = await db.scalar(insert_user)
    if user is None:
        raise HTTPException(409, "An account with that email already exists.")
    return login(response, user)


@router.post("/login")
async def authenticate(data: Credentials, response: Response, db: DB) -> dict[str, str]:
    if settings().auth_mode == "supabase":
        return await supabase_login(data, response, signup=False)
    user = await db.scalar(select(User).where(User.email == data.email))
    salt, expected = (user.password_hash or ".").split(".") if user else ("", "")
    digest = await password_work.run(password_digest, data.password, decode(salt) if salt else bytes(16))
    if not user or not hmac.compare_digest(digest, expected):
        raise HTTPException(401, "Invalid email or password.")
    return login(response, user.id, user.session_version)


@router.get("/session")
async def identity(user: Owner) -> dict[str, str | bool]:
    return {
        "user_id": str(user),
        "admin": user in settings().admin_subjects,
        "listing_assistance": bool(settings().kimi_api_key),
        "simulator_enabled": settings().enable_simulator,
    }


@router.post("/logout", status_code=204)
async def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(COOKIE)
    return response
