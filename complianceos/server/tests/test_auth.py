"""Auth router tests — happy path + error path for all 3 endpoints (Section 14, Rule 1)."""

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
