"""Unit tests for core/auth.py — OTP, rate limiting, JWT, MSG91."""

import hashlib
import json
from datetime import timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis.aioredis import FakeRedis
from jose import jwt

from core.auth import (
    check_otp_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_otp,
    invalidate_refresh_token,
    send_otp_via_msg91,
    store_otp,
    store_refresh_token,
    verify_otp,
    _utc_now,
)
from core.config import settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def redis():
    r = FakeRedis(decode_responses=True)
    yield r
    await r.flushall()
    await r.aclose()


# ---------------------------------------------------------------------------
# generate_otp
# ---------------------------------------------------------------------------

def test_generate_otp_is_six_digits():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_generate_otp_in_valid_range():
    for _ in range(200):
        otp = int(generate_otp())
        assert 100000 <= otp <= 999999


def test_generate_otp_not_always_same():
    """Ensure generate_otp doesn't return a constant (probabilistic)."""
    otps = {generate_otp() for _ in range(20)}
    assert len(otps) > 1


# ---------------------------------------------------------------------------
# store_otp / verify_otp
# ---------------------------------------------------------------------------

async def test_store_and_verify_otp_returns_role(redis):
    await store_otp(redis, "ref1", "9876543210", "123456", "ca")
    role = await verify_otp(redis, "ref1", "9876543210", "123456")
    assert role == "ca"


async def test_verify_otp_deletes_key_on_success(redis):
    await store_otp(redis, "ref2", "9876543210", "654321", "smb")
    await verify_otp(redis, "ref2", "9876543210", "654321")
    assert await redis.get("otp:ref2") is None


async def test_verify_otp_wrong_mobile_raises(redis):
    await store_otp(redis, "ref3", "9876543210", "111111", "ca")
    with pytest.raises(ValueError, match="Mobile number mismatch"):
        await verify_otp(redis, "ref3", "9999999999", "111111")


async def test_verify_otp_expired_ref_raises(redis):
    with pytest.raises(ValueError, match="OTP expired or not found"):
        await verify_otp(redis, "nonexistent_ref", "9876543210", "000000")


async def test_verify_otp_wrong_code_raises(redis):
    await store_otp(redis, "ref4", "9876543210", "999999", "ca")
    with pytest.raises(ValueError, match="Incorrect OTP"):
        await verify_otp(redis, "ref4", "9876543210", "000000")


async def test_verify_otp_wrong_code_increments_attempts(redis):
    await store_otp(redis, "ref5", "9876543210", "999999", "ca")
    with pytest.raises(ValueError, match="Incorrect OTP"):
        await verify_otp(redis, "ref5", "9876543210", "000000")

    data = json.loads(await redis.get("otp:ref5"))
    assert data["attempts"] == 1


async def test_verify_otp_preserves_ttl_on_wrong_code(redis):
    """Wrong-code update must not reset the expiry (keepttl=True)."""
    await store_otp(redis, "ref6", "9876543210", "999999", "ca")
    with pytest.raises(ValueError):
        await verify_otp(redis, "ref6", "9876543210", "000000")
    ttl = await redis.ttl("otp:ref6")
    assert ttl > 0


async def test_verify_otp_lockout_after_max_attempts(redis):
    """After OTP_MAX_ATTEMPTS wrong guesses, the key is deleted and locked out."""
    await store_otp(redis, "ref7", "9876543210", "999999", "ca")

    # Use up all allowed wrong attempts
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        with pytest.raises(ValueError, match="Incorrect OTP"):
            await verify_otp(redis, "ref7", "9876543210", "000000")

    # Next attempt triggers lockout and deletes the key
    with pytest.raises(ValueError, match="Too many incorrect attempts"):
        await verify_otp(redis, "ref7", "9876543210", "000000")

    # Key is gone — subsequent call reports expired, not lockout
    with pytest.raises(ValueError, match="OTP expired or not found"):
        await verify_otp(redis, "ref7", "9876543210", "999999")


async def test_verify_otp_correct_code_after_some_wrong_attempts(redis):
    """Correct OTP should succeed even after some wrong attempts."""
    await store_otp(redis, "ref8", "9876543210", "777777", "smb")
    # Two wrong attempts
    for _ in range(2):
        with pytest.raises(ValueError):
            await verify_otp(redis, "ref8", "9876543210", "000000")
    # Correct attempt should still pass
    role = await verify_otp(redis, "ref8", "9876543210", "777777")
    assert role == "smb"


# ---------------------------------------------------------------------------
# check_otp_rate_limit
# ---------------------------------------------------------------------------

async def test_rate_limit_allows_first_request(redis):
    assert await check_otp_rate_limit(redis, "9800000001") is True


async def test_rate_limit_allows_up_to_limit(redis):
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        result = await check_otp_rate_limit(redis, "9800000002")
        assert result is True


async def test_rate_limit_blocks_over_limit(redis):
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        await check_otp_rate_limit(redis, "9800000003")
    # One over the limit
    assert await check_otp_rate_limit(redis, "9800000003") is False


async def test_rate_limit_sets_ttl_on_first_call(redis):
    """The rate-limit key must have a TTL so it auto-expires after an hour."""
    await check_otp_rate_limit(redis, "9800000004")
    ttl = await redis.ttl(f"otp_rate:9800000004")
    assert ttl > 0


async def test_rate_limit_ttl_not_reset_on_subsequent_calls(redis):
    """NX flag: TTL should only be set once, not on every subsequent call."""
    await check_otp_rate_limit(redis, "9800000005")
    ttl_first = await redis.ttl("otp_rate:9800000005")
    await check_otp_rate_limit(redis, "9800000005")
    ttl_second = await redis.ttl("otp_rate:9800000005")
    # TTL should not increase on second call
    assert ttl_second <= ttl_first


async def test_rate_limit_per_mobile_isolation(redis):
    """Different mobile numbers have independent rate limit counters."""
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        await check_otp_rate_limit(redis, "9800000006")
    # A different mobile should not be affected
    assert await check_otp_rate_limit(redis, "9800000007") is True


# ---------------------------------------------------------------------------
# send_otp_via_msg91
# ---------------------------------------------------------------------------

async def test_send_otp_dev_mode_no_key_skips_http():
    """In dev with no MSG91 key, function returns without making HTTP requests."""
    # settings.is_development=True and settings.MSG91_AUTH_KEY="" by default in tests
    # No exception means it returned early (just logged)
    await send_otp_via_msg91("9876543210", "123456")


async def test_send_otp_dev_mode_with_key_makes_http_call(monkeypatch):
    """With MSG91_AUTH_KEY set (even in dev), the HTTP call is made."""
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "test-auth-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"type": "success", "message": "3"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.auth.httpx.AsyncClient", return_value=mock_client):
        await send_otp_via_msg91("9876543210", "123456")

    mock_client.post.assert_awaited_once()


async def test_send_otp_http_error_raises(monkeypatch):
    """HTTP-level errors (4xx/5xx) must propagate."""
    import httpx

    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=MagicMock()
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.auth.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception):
            await send_otp_via_msg91("9876543210", "123456")


async def test_send_otp_msg91_api_level_error_raises(monkeypatch):
    """MSG91 returns HTTP 200 but with type='error' — must raise RuntimeError."""
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"type": "error", "message": "Invalid auth key"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.auth.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="MSG91 error"):
            await send_otp_via_msg91("9876543210", "123456")


async def test_send_otp_msg91_success_response_does_not_raise(monkeypatch):
    """type='success' must not raise."""
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"type": "success", "message": "3"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.auth.httpx.AsyncClient", return_value=mock_client):
        await send_otp_via_msg91("9876543210", "123456")  # must not raise


# ---------------------------------------------------------------------------
# JWT — access tokens
# ---------------------------------------------------------------------------

def test_create_and_decode_access_token():
    token = create_access_token("user-123", "ca")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "ca"
    assert payload["type"] == "access"


def test_decode_access_token_rejects_refresh_token():
    """A refresh token must not be accepted where an access token is expected."""
    refresh = create_refresh_token("user-123")
    from jose import JWTError
    with pytest.raises(JWTError):
        decode_access_token(refresh)


def test_decode_access_token_rejects_tampered_signature():
    from jose import JWTError
    token = create_access_token("user-123", "ca")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(JWTError):
        decode_access_token(tampered)


def test_decode_access_token_rejects_expired():
    from jose import JWTError
    from datetime import datetime
    expired_payload = {
        "sub": "user-123",
        "role": "ca",
        "type": "access",
        "exp": datetime(2000, 1, 1, tzinfo=timezone.utc),
    }
    token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_access_token_includes_expiry():
    token = create_access_token("user-abc", "smb")
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert "exp" in payload
    expected_exp = _utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    assert abs(payload["exp"] - expected_exp.timestamp()) < 5  # within 5 seconds


# ---------------------------------------------------------------------------
# JWT — refresh tokens
# ---------------------------------------------------------------------------

async def test_create_store_and_decode_refresh_token(redis):
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_refresh_token(user_id)
    await store_refresh_token(redis, token, user_id)

    result = await decode_refresh_token(redis, token)
    assert result == user_id


async def test_decode_refresh_token_rejects_access_token(redis):
    """An access token must not pass as a refresh token."""
    token = create_access_token("user-123", "ca")
    with pytest.raises(ValueError, match="Not a refresh token"):
        await decode_refresh_token(redis, token)


async def test_decode_refresh_token_rejects_invalid_signature(redis):
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await decode_refresh_token(redis, "bad.token.here")


async def test_decode_refresh_token_revoked_raises(redis):
    """Token not present in Redis (revoked or expired) must raise."""
    user_id = "550e8400-e29b-41d4-a716-446655440001"
    token = create_refresh_token(user_id)
    # Deliberately do NOT store it in Redis
    with pytest.raises(ValueError, match="Refresh token revoked or expired"):
        await decode_refresh_token(redis, token)


async def test_invalidate_refresh_token_removes_from_redis(redis):
    user_id = "550e8400-e29b-41d4-a716-446655440002"
    token = create_refresh_token(user_id)
    await store_refresh_token(redis, token, user_id)

    await invalidate_refresh_token(redis, token)

    with pytest.raises(ValueError, match="Refresh token revoked or expired"):
        await decode_refresh_token(redis, token)


async def test_refresh_tokens_stored_as_sha256_hash(redis):
    """Verify the raw token is never stored in Redis — only its SHA-256 hash."""
    user_id = "550e8400-e29b-41d4-a716-446655440003"
    token = create_refresh_token(user_id)
    await store_refresh_token(redis, token, user_id)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # The hash key should exist
    assert await redis.get(f"refresh:{token_hash}") == user_id
    # The raw token must NOT be stored as a key anywhere
    all_keys = await redis.keys("*")
    assert token not in all_keys


async def test_two_refresh_tokens_for_same_user_are_independent(redis):
    """Each token has its own Redis entry; invalidating one doesn't affect the other."""
    user_id = "550e8400-e29b-41d4-a716-446655440004"
    token_a = create_refresh_token(user_id)
    token_b = create_refresh_token(user_id)

    await store_refresh_token(redis, token_a, user_id)
    await store_refresh_token(redis, token_b, user_id)

    await invalidate_refresh_token(redis, token_a)

    # token_b must still be valid
    result = await decode_refresh_token(redis, token_b)
    assert result == user_id
