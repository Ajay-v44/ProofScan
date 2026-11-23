from datetime import timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import StringConstraints
from sqlalchemy import func, select

from .auth import DB, Owner
from .db import ModelCall, User, now
from .providers import model_provider
from .schemas import Claims, Input

router = APIRouter(tags=["listing assistance"])


class Listing(Input):
    listing: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2400)]


@router.post("/claims/suggest", response_model=Claims)
async def suggest(data: Listing, user: Owner, db: DB) -> Claims | JSONResponse:
    provider = model_provider()
    if provider is None:
        raise HTTPException(503, "Listing assistance is unavailable. Enter the claims manually.")

    await db.scalar(select(User.id).where(User.id == user).with_for_update())
    count = await db.scalar(
        select(func.count())
        .select_from(ModelCall)
        .where(
            ModelCall.owner_id == user,
            ModelCall.created_at > now() - timedelta(days=1),
        )
    )
    if (count or 0) >= 10:
        raise HTTPException(429, "You have reached today's listing assistance limit.")
    try:
        result = await provider.suggest(data.listing)
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError, OverflowError):
        db.add(ModelCall(owner_id=user, accepted=False))
        return JSONResponse(
            {"detail": "Listing assistance is unavailable. Enter the claims manually."}, status_code=503
        )
    db.add(
        ModelCall(
            owner_id=user,
            accepted=True,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    )
    return result.claims
