import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from jose import JWTError, jwt
from redis.asyncio import Redis

from core.config import settings

logger = logging.getLogger(__name__)

_OTP_KEY_PREFIX = "otp:"
_REFRESH_KEY_PREFIX = "refresh:"
_RATE_KEY_PREFIX = "otp_rate:"


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------

def generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


async def store_otp(redis: Redis, otp_ref: str, mobile: str, otp: str, role: str) -> None:
    payload = json.dumps({"mobile": mobile, "otp": otp, "role": role, "attempts": 0})
    await redis.set(f"{_OTP_KEY_PREFIX}{otp_ref}", payload, ex=settings.OTP_EXPIRY_SECONDS)


async def verify_otp(redis: Redis, otp_ref: str, mobile: str, otp: str) -> str:
    """Verify OTP. Returns role on success. Raises ValueError on failure."""
    raw = await redis.get(f"{_OTP_KEY_PREFIX}{otp_ref}")
    if raw is None:
        raise ValueError("OTP expired or not found")

    data = json.loads(raw)

    if data["mobile"] != mobile:
        raise ValueError("Mobile number mismatch")

    attempts: int = data.get("attempts", 0)
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        await redis.delete(f"{_OTP_KEY_PREFIX}{otp_ref}")
        raise ValueError("Too many incorrect attempts")

    # Constant-time comparison
    if not secrets.compare_digest(data["otp"], otp):
        data["attempts"] = attempts + 1
        await redis.set(
            f"{_OTP_KEY_PREFIX}{otp_ref}",
            json.dumps(data),
            keepttl=True,
        )
        raise ValueError("Incorrect OTP")

    await redis.delete(f"{_OTP_KEY_PREFIX}{otp_ref}")
    return data["role"]


async def check_otp_rate_limit(redis: Redis, mobile: str) -> bool:
    """Returns True if under rate limit, False if exceeded."""
    key = f"{_RATE_KEY_PREFIX}{mobile}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, 3600, nx=True)  # nx=True: only set TTL if key has none (Redis 7+)
        results = await pipe.execute()
    return results[0] <= settings.OTP_RATE_LIMIT_PER_HOUR


async def send_otp_via_msg91(mobile: str, otp: str) -> None:
    """Send OTP via MSG91. In development with no key configured, logs to console instead."""
    if settings.is_development and not settings.MSG91_AUTH_KEY:
        logger.info("[DEV] OTP for %s: %s", mobile, otp)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.msg91.com/api/v5/otp",
            params={
                "authkey": settings.MSG91_AUTH_KEY,
                "template_id": settings.MSG91_TEMPLATE_ID,
                "mobile": f"91{mobile}",
                "otp": otp,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("type") == "error":
            raise RuntimeError(f"MSG91 error: {body.get('message', 'unknown')}")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    expire = _utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = _utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def store_refresh_token(redis: Redis, token: str, user_id: str) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.set(f"{_REFRESH_KEY_PREFIX}{token_hash}", user_id, ex=ttl)


async def invalidate_refresh_token(redis: Redis, token: str) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    await redis.delete(f"{_REFRESH_KEY_PREFIX}{token_hash}")


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


async def decode_refresh_token(redis: Redis, token: str) -> str:
    """Validate refresh token signature + Redis presence. Returns user_id."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user_id = await redis.get(f"{_REFRESH_KEY_PREFIX}{token_hash}")
    if user_id is None:
        raise ValueError("Refresh token revoked or expired")

    return user_id if isinstance(user_id, str) else user_id.decode()
