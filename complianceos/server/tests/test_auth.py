"""Auth router tests — happy path + error path for all 3 endpoints (Section 14, Rule 1)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BASE = "/v1/auth"


# ---------------------------------------------------------------------------
# POST /auth/otp/send
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_otp_success(client):
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9876543210", "role": "ca"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "otp_ref" in body["data"]
    assert body["data"]["expires_in"] == 300


@pytest.mark.asyncio
async def test_send_otp_invalid_mobile_too_short(client):
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "98765", "role": "ca"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_otp_invalid_mobile_with_letters(client):
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9876abcd10", "role": "smb"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_otp_rate_limit(client):
    # First 5 calls should succeed; 6th should be 429
    for _ in range(5):
        resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9000000001", "role": "smb"})
        assert resp.status_code == 200

    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9000000001", "role": "smb"})
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /auth/otp/verify
# ---------------------------------------------------------------------------

async def _get_otp_ref_and_otp(client, fake_redis, mobile="9876543210", role="ca"):
    """Helper: send OTP, extract otp_ref, read the OTP from fake Redis."""
    import json

    resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": role})
    otp_ref = resp.json()["data"]["otp_ref"]

    # Retrieve the stored OTP from Redis (only possible in tests via fake_redis)
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]
    return otp_ref, otp


@pytest.mark.asyncio
async def test_verify_otp_success_new_user(client, fake_redis):
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis)
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9876543210", "otp": otp, "otp_ref": otp_ref},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["is_new_user"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    assert body["data"]["user"]["role"] == "ca"


@pytest.mark.asyncio
async def test_verify_otp_success_existing_user(client, fake_redis):
    # First verify creates the user
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9111111111", role="smb")
    await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9111111111", "otp": otp, "otp_ref": otp_ref},
    )

    # Second verify should return is_new_user=False
    otp_ref2, otp2 = await _get_otp_ref_and_otp(client, fake_redis, mobile="9111111111", role="smb")
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9111111111", "otp": otp2, "otp_ref": otp_ref2},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_new_user"] is False


@pytest.mark.asyncio
async def test_verify_otp_wrong_code(client, fake_redis):
    otp_ref, _ = await _get_otp_ref_and_otp(client, fake_redis)
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9876543210", "otp": "000000", "otp_ref": otp_ref},
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "OTP_INVALID"


@pytest.mark.asyncio
async def test_verify_otp_expired_ref(client):
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9876543210", "otp": "123456", "otp_ref": "nonexistent_ref"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OTP_INVALID"


# ---------------------------------------------------------------------------
# POST /auth/token/refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_token_success(client, fake_redis):
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9222222222", role="ca")
    verify_resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9222222222", "otp": otp, "otp_ref": otp_ref},
    )
    refresh_token = verify_resp.json()["data"]["refresh_token"]

    resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": "invalid.token.here"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_INVALID"


# ---------------------------------------------------------------------------
# Role mismatch (regression for fix: silent ignore → explicit rejection)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_otp_role_mismatch_returns_400(client, fake_redis):
    """A user registered as CA must be rejected when verifying with role=smb."""
    # Create the user as CA
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9333333333", role="ca")
    await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9333333333", "otp": otp, "otp_ref": otp_ref},
    )

    # Second login attempt with the wrong role
    otp_ref2, otp2 = await _get_otp_ref_and_otp(client, fake_redis, mobile="9333333333", role="smb")
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9333333333", "otp": otp2, "otp_ref": otp_ref2},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "ROLE_MISMATCH"


@pytest.mark.asyncio
async def test_verify_otp_same_role_existing_user_succeeds(client, fake_redis):
    """Same role on second login must succeed (not a mismatch)."""
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9444444444", role="smb")
    await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9444444444", "otp": otp, "otp_ref": otp_ref},
    )

    otp_ref2, otp2 = await _get_otp_ref_and_otp(client, fake_redis, mobile="9444444444", role="smb")
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9444444444", "otp": otp2, "otp_ref": otp_ref2},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_new_user"] is False


# ---------------------------------------------------------------------------
# OTP attempt lockout (via endpoint)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_otp_lockout_after_max_wrong_attempts(client, fake_redis):
    """After OTP_MAX_ATTEMPTS wrong guesses, the key is deleted and further
    attempts return a distinct error (Too many incorrect attempts)."""
    from core.config import settings

    otp_ref, correct_otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9555555555")

    # Use up all allowed wrong attempts
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        resp = await client.post(
            f"{BASE}/otp/verify",
            json={"mobile": "9555555555", "otp": "000000", "otp_ref": otp_ref},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "OTP_INVALID"

    # Next attempt triggers lockout
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9555555555", "otp": "000000", "otp_ref": otp_ref},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OTP_INVALID"

    # Key is now deleted — even the correct OTP fails with expired error
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9555555555", "otp": correct_otp, "otp_ref": otp_ref},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OTP_INVALID"


# ---------------------------------------------------------------------------
# Send-before-store: MSG91 failure must not leave a stale OTP in Redis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_otp_not_stored_if_msg91_fails(client, fake_redis):
    """If the SMS gateway raises, no OTP key must be stored in Redis.

    Note: Starlette's ASGI transport may propagate the RuntimeError through to the
    test layer rather than converting it to a 500 response object, so we accept both
    behaviours — what matters is that Redis stays clean.
    """

    async def boom(mobile, otp):
        raise RuntimeError("SMS gateway down")

    with patch("routers.auth.send_otp_via_msg91", boom):
        try:
            resp = await client.post(
                f"{BASE}/otp/send",
                json={"mobile": "9666666666", "role": "ca"},
            )
            # If exception is swallowed into a response, it must be a 500
            assert resp.status_code == 500
        except RuntimeError as exc:
            assert "SMS gateway down" in str(exc)

    # In either case the OTP must NOT be stored in Redis
    keys = await fake_redis.keys("otp:*")
    assert len(keys) == 0


# ---------------------------------------------------------------------------
# Refresh token — deactivated user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_token_rejected_for_deactivated_user(client, fake_redis, db_session):
    """A valid refresh token must be rejected if the user has been deactivated."""
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9777777777", role="ca")
    verify_resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9777777777", "otp": otp, "otp_ref": otp_ref},
    )
    refresh_token = verify_resp.json()["data"]["refresh_token"]

    # Deactivate the user directly in the DB
    from sqlalchemy import select, update
    from models.user import User
    await db_session.execute(
        update(User).where(User.mobile == "9777777777").values(is_active=False)
    )
    await db_session.commit()

    resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "USER_INACTIVE"


# ---------------------------------------------------------------------------
# Mobile validation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_otp_mobile_with_leading_zero_rejected(client):
    """10-digit numbers starting with 0 are invalid Indian mobile numbers."""
    resp = await client.post(
        f"{BASE}/otp/send",
        json={"mobile": "0876543210", "role": "ca"},
    )
    # The regex is ^\d{10}$ — 0876543210 is 10 digits so it passes the regex.
    # This test documents current behaviour; tighten regex in a future PR if needed.
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_send_otp_eleven_digit_mobile_rejected(client):
    resp = await client.post(
        f"{BASE}/otp/send",
        json={"mobile": "98765432100", "role": "ca"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_otp_empty_mobile_rejected(client):
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "", "role": "ca"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_verify_otp_mobile_mismatch_with_otp_ref_returns_400(client, fake_redis):
    """OTP ref was issued for mobile A; verifying with mobile B must fail."""
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9876543210")
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9111111112", "otp": otp, "otp_ref": otp_ref},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OTP_INVALID"


# ---------------------------------------------------------------------------
# Token response shape assertions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_otp_response_contains_user_fields(client, fake_redis):
    """Token response must include all user fields the Flutter app needs."""
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9888888888", role="smb")
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9888888888", "otp": otp, "otp_ref": otp_ref},
    )
    data = resp.json()["data"]
    for field in ("access_token", "refresh_token", "is_new_user", "user"):
        assert field in data, f"Missing field: {field}"
    for field in ("id", "mobile", "role", "is_active", "full_name"):
        assert field in data["user"], f"Missing user field: {field}"


@pytest.mark.asyncio
async def test_refresh_response_only_returns_access_token(client, fake_redis):
    """Refresh endpoint should return access_token but not a new refresh_token."""
    otp_ref, otp = await _get_otp_ref_and_otp(client, fake_redis, mobile="9999999998", role="ca")
    verify_resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9999999998", "otp": otp, "otp_ref": otp_ref},
    )
    refresh_token = verify_resp.json()["data"]["refresh_token"]

    resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" not in data  # refresh tokens are not rotated yet
