import re
import uuid as uuid_module
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import (
    check_otp_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_otp,
    send_otp_via_msg91,
    store_otp,
    store_refresh_token,
    verify_otp,
)
from core.config import settings
from core.database import get_db
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

_MOBILE_RE = re.compile(r"^\d{10}$")


def _success(data: dict) -> dict:
    return {"success": True, "data": data, "meta": None, "error": None}


def _error(code: str, message: str) -> dict:
    return {"success": False, "data": None, "meta": None, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class OTPSendRequest(BaseModel):
    mobile: str
    role: Literal["ca", "smb"]

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not _MOBILE_RE.match(v):
            raise ValueError("mobile must be exactly 10 digits")
        return v


class OTPVerifyRequest(BaseModel):
    mobile: str
    otp: str
    otp_ref: str

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not _MOBILE_RE.match(v):
            raise ValueError("mobile must be exactly 10 digits")
        return v


class TokenRefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/otp/send")
async def send_otp(body: OTPSendRequest, request: Request):
    redis = request.app.state.redis

    under_limit = await check_otp_rate_limit(redis, body.mobile)
    if not under_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error("OTP_RATE_LIMIT", "Too many OTP requests. Try again after 1 hour."),
        )

    otp = generate_otp()
    otp_ref = uuid_module.uuid4().hex

    await send_otp_via_msg91(body.mobile, otp)
    await store_otp(redis, otp_ref, body.mobile, otp, body.role)

    return _success({"otp_ref": otp_ref, "expires_in": settings.OTP_EXPIRY_SECONDS})


@router.post("/otp/verify")
async def verify_otp_endpoint(
    body: OTPVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    redis = request.app.state.redis

    try:
        role = await verify_otp(redis, body.otp_ref, body.mobile, body.otp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("OTP_INVALID", str(exc)),
        )

    # Upsert user
    result = await db.execute(select(User).where(User.mobile == body.mobile))
    user = result.scalar_one_or_none()
    is_new_user = user is None

    if is_new_user:
        user = User(mobile=body.mobile, role=role, full_name="")
        db.add(user)
        await db.flush()  # populate user.id before token creation
    elif user.role != role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("ROLE_MISMATCH", "This account is registered under a different role"),
        )

    user_id = str(user.id)
    access_token = create_access_token(user_id, user.role)
    refresh_token = create_refresh_token(user_id)
    await store_refresh_token(redis, refresh_token, user_id)

    return _success(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user_id,
                "mobile": user.mobile,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
            },
            "is_new_user": is_new_user,
        }
    )


@router.post("/token/refresh")
async def refresh_token(
    body: TokenRefreshRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    redis = request.app.state.redis

    try:
        user_id = await decode_refresh_token(redis, body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("TOKEN_INVALID", str(exc)),
        )

    # Load user to get current role — refresh tokens are long-lived, role may have changed
    result = await db.execute(select(User).where(User.id == uuid_module.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("USER_INACTIVE", "User not found or deactivated"),
        )

    access_token = create_access_token(str(user.id), user.role)
    return _success({"access_token": access_token})
