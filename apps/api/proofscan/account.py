import hashlib
import secrets
from datetime import datetime
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select, update

from .auth import COOKIE, DB, Owner, password_digest, password_work
from .config import settings
from .db import User
from .schemas import Credentials, Email, Input
from .signing import encode

router = APIRouter(prefix="/auth", tags=["account"])
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Method = Literal["email", "code"]


class Profile(BaseModel):
    email: str | None
    display_name: str | None
    created_at: datetime
    recovery_method: Method
    recovery_code_ready: bool


class UpdateProfile(Input):
    display_name: DisplayName


class Recovery(Input):
    email: Email


class Reset(Credentials):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=43)]


def recovery_method() -> Method:
    return "email" if settings().auth_mode == "supabase" else "code"


def profile_view(user: User, request: Request) -> Profile:
    return Profile(
        email=user.email or getattr(request.state, "account_email", None),
        display_name=user.display_name,
        created_at=user.created_at,
        recovery_method=recovery_method(),
        recovery_code_ready=user.recovery_hash is not None,
    )


@router.get("/profile", response_model=Profile)
async def profile(owner: Owner, request: Request, db: DB) -> Profile:
    return profile_view(await db.get_one(User, owner), request)


@router.post("/profile", response_model=Profile)
async def update_profile(data: UpdateProfile, owner: Owner, request: Request, db: DB) -> Profile:
    user = await db.get_one(User, owner)
    user.display_name = data.display_name or None
    return profile_view(user, request)


def recovery_digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


@router.post("/recovery-code", status_code=201)
async def generate_code(owner: Owner, db: DB) -> dict[str, str]:
    if recovery_method() != "code":
        raise HTTPException(409, "Use email to reset your password.")
    code = secrets.token_urlsafe(32)
    await db.execute(update(User).where(User.id == owner).values(recovery_hash=recovery_digest(code)))
    return {"code": code}


@router.get("/recovery")
async def recovery_options() -> dict[str, Method]:
    return {"method": recovery_method()}


def provider_settings() -> tuple[str, dict[str, str]]:
    config = settings()
    assert config.supabase_publishable_key is not None
    return config.supabase_url.rstrip("/") + "/auth/v1", {
        "apikey": config.supabase_publishable_key.get_secret_value()
    }


@router.post("/recover", status_code=202)
async def request_recovery(data: Recovery) -> dict[str, Method]:
    if recovery_method() == "email":
        origin, headers = provider_settings()
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
                result = await client.post(
                    origin + "/recover", headers=headers, json={"email": data.email}
                )
            if result.status_code >= 500:
                raise HTTPException(503, "Password recovery is temporarily unavailable.")
        except httpx.RequestError as exc:
            raise HTTPException(503, "Password recovery is temporarily unavailable.") from exc
    return {"method": recovery_method()}


def invalid_code() -> HTTPException:
    return HTTPException(400, "That recovery code is invalid, expired, or already used.")


async def reset_hosted(data: Reset) -> None:
    origin, headers = provider_settings()
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            verified = await client.post(
                origin + "/verify",
                headers=headers,
                json={"email": data.email, "token": data.code, "type": "recovery"},
            )
            if verified.status_code >= 500:
                raise HTTPException(503, "Password recovery is temporarily unavailable.")
            if not verified.is_success:
                raise invalid_code()
            token = verified.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise invalid_code()
            changed = await client.put(
                origin + "/user",
                headers={**headers, "Authorization": "Bearer " + token},
                json={"password": data.password},
            )
            if changed.status_code >= 500:
                raise HTTPException(503, "Password recovery is temporarily unavailable.")
            if not changed.is_success:
                raise HTTPException(400, "Use a different password and request a fresh recovery code.")
    except (httpx.RequestError, AttributeError, ValueError) as exc:
        raise HTTPException(503, "Password recovery is temporarily unavailable.") from exc


@router.post("/reset", status_code=204)
async def reset_password(data: Reset, db: DB) -> Response:
    if recovery_method() == "email":
        await reset_hosted(data)
    else:
        if len(data.code) != 43:
            raise invalid_code()
        eligible = (User.email == data.email, User.recovery_hash == recovery_digest(data.code))
        owner = await db.scalar(select(User.id).where(*eligible))
        await db.commit()
        if owner is None:
            raise invalid_code()
        salt = secrets.token_bytes(16)
        digest = await password_work.run(password_digest, data.password, salt)
        changed = await db.scalar(
            update(User)
            .where(User.id == owner, *eligible)
            .values(
                password_hash=f"{encode(salt)}.{digest}",
                recovery_hash=None,
                session_version=User.session_version + 1,
            )
            .returning(User.id)
        )
        if changed is None:
            raise invalid_code()
    response = Response(status_code=204)
    response.delete_cookie(COOKIE)
    return response
