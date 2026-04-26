"""End-to-end auth flow integration tests.

These tests exercise the full request lifecycle:
  send OTP → verify OTP → receive tokens → use access token → refresh

No mocking of internal functions — everything runs through the real HTTP stack,
real Redis (fake), and real SQLite DB. This is the closest you get to a
real user session without a frontend.
"""

import json

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from core.auth import create_access_token, decode_access_token
from core.config import settings
from core.dependencies import get_current_user
from models.user import User

BASE = "/v1/auth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _full_login(client, fake_redis, mobile: str, role: str = "ca"):
    """Helper: send OTP → verify → return full token payload."""
    send_resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": role})
    assert send_resp.status_code == 200, send_resp.text
    otp_ref = send_resp.json()["data"]["otp_ref"]

    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    verify_resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": mobile, "otp": otp, "otp_ref": otp_ref},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    return verify_resp.json()["data"]


# ---------------------------------------------------------------------------
# Full end-to-end auth flow
# ---------------------------------------------------------------------------

async def test_full_auth_flow_ca(client, fake_redis):
    """CA: send OTP → verify → get tokens → refresh → new access token."""
    data = await _full_login(client, fake_redis, "9200000001", "ca")

    assert data["is_new_user"] is True
    assert data["user"]["role"] == "ca"
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Access token is a valid JWT with correct claims
    payload = decode_access_token(access_token)
    assert payload["type"] == "access"
    assert payload["role"] == "ca"
    assert "sub" in payload

    # Refresh yields a new access token
    refresh_resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["data"]["access_token"]
    assert new_access != access_token  # new token (different exp / jti)

    # New access token is also valid
    new_payload = decode_access_token(new_access)
    assert new_payload["sub"] == payload["sub"]
    assert new_payload["role"] == "ca"


async def test_full_auth_flow_smb(client, fake_redis):
    """SMB: identical flow, role is preserved throughout."""
    data = await _full_login(client, fake_redis, "9200000002", "smb")
    access_token = data["access_token"]

    payload = decode_access_token(access_token)
    assert payload["role"] == "smb"
    assert data["user"]["role"] == "smb"


async def test_second_login_returns_same_user_id(client, fake_redis):
    """Logging in twice with the same mobile must return the same user ID."""
    data1 = await _full_login(client, fake_redis, "9200000003", "ca")
    data2 = await _full_login(client, fake_redis, "9200000003", "ca")

    assert data1["user"]["id"] == data2["user"]["id"]
    assert data2["is_new_user"] is False


async def test_access_token_authenticates_via_dependency(client, fake_redis, db_session):
    """Access token returned by login must authenticate successfully in get_current_user."""
    data = await _full_login(client, fake_redis, "9200000004", "ca")
    access_token = data["access_token"]

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
    user = await get_current_user(credentials=creds, db=db_session)

    assert str(user.id) == data["user"]["id"]
    assert user.role == "ca"
    assert user.is_active is True


async def test_refresh_token_produces_valid_access_token(client, fake_redis, db_session):
    """The access token from a refresh must also pass get_current_user."""
    data = await _full_login(client, fake_redis, "9200000005", "ca")
    refresh_resp = await client.post(
        f"{BASE}/token/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    new_access = refresh_resp.json()["data"]["access_token"]

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=new_access)
    user = await get_current_user(credentials=creds, db=db_session)
    assert str(user.id) == data["user"]["id"]


# ---------------------------------------------------------------------------
# Token isolation between users
# ---------------------------------------------------------------------------

async def test_two_users_tokens_are_independent(client, fake_redis, db_session):
    """User A's access token must not authenticate as User B."""
    data_a = await _full_login(client, fake_redis, "9200000010", "ca")
    data_b = await _full_login(client, fake_redis, "9200000011", "smb")

    # A's token resolves to A
    creds_a = HTTPAuthorizationCredentials(scheme="Bearer", credentials=data_a["access_token"])
    user_a = await get_current_user(credentials=creds_a, db=db_session)
    assert user_a.mobile == "9200000010"

    # B's token resolves to B
    creds_b = HTTPAuthorizationCredentials(scheme="Bearer", credentials=data_b["access_token"])
    user_b = await get_current_user(credentials=creds_b, db=db_session)
    assert user_b.mobile == "9200000011"

    # They are different users
    assert user_a.id != user_b.id


async def test_refresh_tokens_for_two_users_are_independent(client, fake_redis):
    """Refreshing User A's token must not affect User B's session."""
    data_a = await _full_login(client, fake_redis, "9200000012", "ca")
    data_b = await _full_login(client, fake_redis, "9200000013", "smb")

    # Refresh A
    resp_a = await client.post(f"{BASE}/token/refresh", json={"refresh_token": data_a["refresh_token"]})
    assert resp_a.status_code == 200

    # B's refresh should still work independently
    resp_b = await client.post(f"{BASE}/token/refresh", json={"refresh_token": data_b["refresh_token"]})
    assert resp_b.status_code == 200


# ---------------------------------------------------------------------------
# Multiple sessions (same user, different devices)
# ---------------------------------------------------------------------------

async def test_same_user_two_sessions_independent(client, fake_redis, db_session):
    """Same user logged in on two devices gets two independent refresh tokens.
    Refreshing one session leaves the other intact.
    """
    # Session 1
    data1 = await _full_login(client, fake_redis, "9200000020", "ca")
    # Session 2 (simulate second device — re-login)
    data2 = await _full_login(client, fake_redis, "9200000020", "ca")

    token1 = data1["refresh_token"]
    token2 = data2["refresh_token"]

    # Both must be different tokens (jti makes them unique)
    assert token1 != token2

    # Both refresh tokens must work independently
    r1 = await client.post(f"{BASE}/token/refresh", json={"refresh_token": token1})
    r2 = await client.post(f"{BASE}/token/refresh", json={"refresh_token": token2})
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting across the full flow
# ---------------------------------------------------------------------------

async def test_rate_limit_blocks_after_5_requests(client, fake_redis):
    """5 OTP sends allowed; 6th returns 429."""
    mobile = "9200000030"
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": "ca"})
        assert resp.status_code == 200

    resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": "ca"})
    assert resp.status_code == 429


async def test_rate_limit_is_per_mobile(client, fake_redis):
    """Rate limit on mobile A must not affect mobile B."""
    mobile_a = "9200000031"
    mobile_b = "9200000032"

    # Exhaust A's limit
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        await client.post(f"{BASE}/otp/send", json={"mobile": mobile_a, "role": "ca"})

    # A is blocked
    resp_a = await client.post(f"{BASE}/otp/send", json={"mobile": mobile_a, "role": "ca"})
    assert resp_a.status_code == 429

    # B is unaffected
    resp_b = await client.post(f"{BASE}/otp/send", json={"mobile": mobile_b, "role": "ca"})
    assert resp_b.status_code == 200


# ---------------------------------------------------------------------------
# OTP one-time use
# ---------------------------------------------------------------------------

async def test_otp_cannot_be_reused(client, fake_redis):
    """Once an OTP is verified, it must be deleted — reusing it must fail."""
    send_resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9200000040", "role": "ca"})
    otp_ref = send_resp.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    # First verify succeeds
    r1 = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9200000040", "otp": otp, "otp_ref": otp_ref},
    )
    assert r1.status_code == 200

    # Second verify with same ref must fail — key was deleted
    r2 = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9200000040", "otp": otp, "otp_ref": otp_ref},
    )
    assert r2.status_code == 400


async def test_otp_ref_cross_contamination_prevented(client, fake_redis):
    """OTP ref issued for mobile A must not verify mobile B."""
    send_resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9200000041", "role": "ca"})
    otp_ref = send_resp.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    # Try to use A's OTP ref with mobile B
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9200000042", "otp": otp, "otp_ref": otp_ref},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OTP_INVALID"


# ---------------------------------------------------------------------------
# Response envelope consistency
# ---------------------------------------------------------------------------

async def test_all_auth_endpoints_return_standard_envelope(client, fake_redis):
    """Every auth response must follow {success, data, meta, error} shape."""
    endpoints_and_bodies = [
        (f"{BASE}/otp/send", {"mobile": "9200000050", "role": "ca"}),
        (f"{BASE}/token/refresh", {"refresh_token": "bad.token"}),
    ]
    for path, body in endpoints_and_bodies:
        resp = await client.post(path, json=body)
        r = resp.json()
        for key in ("success", "data", "meta", "error"):
            assert key in r, f"Missing '{key}' in response from {path}: {r}"


async def test_success_response_has_null_error(client, fake_redis):
    """Successful responses must have error=null."""
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9200000051", "role": "ca"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None


async def test_error_response_has_null_data(client, fake_redis):
    """Error responses must have data=null."""
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9200000052", "otp": "000000", "otp_ref": "nonexistent"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] is not None
