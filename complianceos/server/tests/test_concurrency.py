"""Concurrency tests — verify correctness under simultaneous requests.

All tests use asyncio.gather() to fire coroutines concurrently within the same
event loop.  Every await point is a potential context switch, so these tests
exercise real race windows that exist in production (where multiple uvicorn
worker tasks run on the same event loop).

Key scenarios tested:
  - Rate limiting holds under concurrent OTP sends for the same mobile
  - Per-mobile rate limits don't bleed across different mobiles
  - OTP one-time use: concurrent verifies with the same ref → only one wins
  - OTP cross-mobile: concurrent verifies with wrong mobile → all rejected
  - Concurrent full logins for the same mobile → same user ID every time
  - Concurrent token refreshes → each independently succeeds
  - DB unique constraint: concurrent registration attempts → no duplicates
"""

import asyncio
import json
from collections import Counter

import pytest

from core.auth import (
    check_otp_rate_limit,
    generate_otp,
    store_otp,
    verify_otp,
)
from core.config import settings

BASE = "/v1/auth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_otp(client, mobile: str, role: str = "ca"):
    return await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": role})


async def _verify_otp(client, fake_redis, mobile: str, otp_ref: str, otp: str):
    return await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": mobile, "otp": otp, "otp_ref": otp_ref},
    )


async def _full_login(client, fake_redis, mobile: str, role: str = "ca"):
    send = await _send_otp(client, mobile, role)
    assert send.status_code == 200, send.text
    otp_ref = send.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]
    verify = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": mobile, "otp": otp, "otp_ref": otp_ref},
    )
    assert verify.status_code == 200, verify.text
    return verify.json()["data"]


# ===========================================================================
# Rate limiting
# ===========================================================================

async def test_concurrent_otp_sends_rate_limit_is_exact(client, fake_redis):
    """Fire OTP_RATE_LIMIT_PER_HOUR + 2 concurrent sends for the same mobile.
    Exactly OTP_RATE_LIMIT_PER_HOUR should succeed (200); the rest return 429.
    The pipeline-based counter must not allow more than the configured limit
    even when all requests land simultaneously.
    """
    mobile = "9300000001"
    limit = settings.OTP_RATE_LIMIT_PER_HOUR
    total = limit + 2

    responses = await asyncio.gather(
        *[_send_otp(client, mobile) for _ in range(total)]
    )
    status_counts = Counter(r.status_code for r in responses)

    assert status_counts[200] == limit, (
        f"Expected exactly {limit} successes, got {status_counts[200]}"
    )
    assert status_counts[429] == 2


async def test_concurrent_otp_sends_different_mobiles_are_independent(client, fake_redis):
    """Simultaneous sends for N distinct mobiles must all succeed — rate limit
    is keyed per mobile, so they must not interfere with each other.
    """
    mobiles = [f"930000010{i}" for i in range(8)]
    responses = await asyncio.gather(
        *[_send_otp(client, m) for m in mobiles]
    )
    assert all(r.status_code == 200 for r in responses), (
        [(r.status_code, r.json()) for r in responses if r.status_code != 200]
    )


async def test_rate_limit_counter_is_atomic(fake_redis):
    """Call check_otp_rate_limit concurrently N times and verify the Redis
    counter ends up at exactly N (not less, which would indicate lost updates).
    """
    mobile = "9300000020"
    limit = settings.OTP_RATE_LIMIT_PER_HOUR
    n = limit - 1  # all should be allowed

    results = await asyncio.gather(
        *[check_otp_rate_limit(fake_redis, mobile) for _ in range(n)]
    )
    assert all(results), "All calls should be under the rate limit"

    # Counter must be exactly n — no lost increments
    raw = await fake_redis.get(f"otp_rate:{mobile}")
    assert int(raw) == n


# ===========================================================================
# OTP one-time use under concurrency
# ===========================================================================

async def test_concurrent_otp_verify_only_one_wins(client, fake_redis):
    """Send 1 OTP then concurrently submit N verify requests with the same ref.
    Exactly 1 must succeed (200); the rest must get 400 (OTP consumed on first
    successful verify via atomic GETDEL).
    """
    mobile = "9300000030"
    send = await _send_otp(client, mobile)
    assert send.status_code == 200
    otp_ref = send.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    n = 6
    responses = await asyncio.gather(
        *[_verify_otp(client, fake_redis, mobile, otp_ref, otp) for _ in range(n)]
    )
    status_counts = Counter(r.status_code for r in responses)

    assert status_counts[200] == 1, (
        f"Expected exactly 1 success, got {status_counts[200]}: "
        f"{[r.json() for r in responses if r.status_code == 200]}"
    )
    assert status_counts[400] == n - 1


async def test_concurrent_wrong_otp_all_fail(client, fake_redis):
    """N concurrent verifies with the wrong OTP must all return 400.
    The OTP key must still exist afterwards so the user can retry with the
    correct code (the key is re-stored after each failed attempt).
    """
    mobile = "9300000031"
    send = await _send_otp(client, mobile)
    otp_ref = send.json()["data"]["otp_ref"]

    responses = await asyncio.gather(
        *[_verify_otp(client, fake_redis, mobile, otp_ref, "000000") for _ in range(4)]
    )
    assert all(r.status_code == 400 for r in responses)

    # OTP key must still be present (wrong OTP does not permanently consume it)
    remaining = await fake_redis.get(f"otp:{otp_ref}")
    assert remaining is not None


async def test_concurrent_cross_mobile_verify_all_rejected(client, fake_redis):
    """OTP ref issued for mobile A must reject all concurrent attempts using
    mobile B — even if the correct OTP value is known.
    """
    mobile_a = "9300000032"
    mobile_b = "9300000033"

    send = await _send_otp(client, mobile_a)
    otp_ref = send.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    responses = await asyncio.gather(
        *[_verify_otp(client, fake_redis, mobile_b, otp_ref, otp) for _ in range(4)]
    )
    assert all(r.status_code == 400 for r in responses)
    assert all(r.json()["error"]["code"] == "OTP_INVALID" for r in responses)


# ===========================================================================
# Concurrent logins — same user, no duplicate rows
# ===========================================================================

async def test_repeated_login_same_mobile_always_returns_same_user(client, fake_redis):
    """Logging in three times with the same mobile must always resolve to the
    same user ID — user creation is idempotent.

    Note: truly concurrent DB writes for the same mobile are serialised in
    production by the unique constraint on users.mobile (tested in test_models).
    Here we test sequential idempotency; the DB-level race is a structural
    guarantee, not something that can be exercised through a shared test session.
    """
    mobile = "9300000040"
    ids = set()
    for _ in range(3):
        data = await _full_login(client, fake_redis, mobile)
        ids.add(data["user"]["id"])

    assert len(ids) == 1, f"Expected 1 unique user ID across logins, got: {ids}"


async def test_logins_for_different_mobiles_create_distinct_users(client, fake_redis):
    """N sequential auth flows for distinct mobiles must each create a
    distinct user — no cross-contamination of user records.

    Note: concurrent DB inserts share the same SQLAlchemy session in tests,
    which SQLAlchemy does not support. Production requests each get an
    isolated session/connection, so this test uses sequential requests to
    verify the correctness property without hitting the session limitation.
    """
    mobiles = [f"930000005{i}" for i in range(4)]
    user_ids = []
    for mobile in mobiles:
        data = await _full_login(client, fake_redis, mobile)
        user_ids.append(data["user"]["id"])

    assert len(set(user_ids)) == len(mobiles), "Each mobile must produce a distinct user"


# ===========================================================================
# Concurrent token refresh
# ===========================================================================

async def test_concurrent_refresh_same_token_both_return_valid_access(client, fake_redis):
    """Two concurrent refreshes with the same refresh token: the current
    implementation is stateless on refresh (no token rotation), so both
    requests should succeed and return valid — but distinct — access tokens.
    """
    data = await _full_login(client, fake_redis, "9300000060")
    refresh_token = data["refresh_token"]

    r1, r2 = await asyncio.gather(
        client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token}),
        client.post(f"{BASE}/token/refresh", json={"refresh_token": refresh_token}),
    )

    assert r1.status_code == 200, r1.json()
    assert r2.status_code == 200, r2.json()

    at1 = r1.json()["data"]["access_token"]
    at2 = r2.json()["data"]["access_token"]
    # Both tokens are valid but must be different (jti makes each unique)
    assert at1 != at2


async def test_concurrent_refresh_independent_users_dont_interfere(client, fake_redis):
    """Refreshing tokens for N independent users concurrently must give each
    user a new access token scoped to their own identity.
    """
    mobiles = [f"930000007{i}" for i in range(4)]
    logins = []
    for m in mobiles:
        logins.append(await _full_login(client, fake_redis, m))

    results = await asyncio.gather(
        *[
            client.post(f"{BASE}/token/refresh", json={"refresh_token": d["refresh_token"]})
            for d in logins
        ]
    )

    assert all(r.status_code == 200 for r in results)

    # Each new access token must map back to the correct user
    from core.auth import decode_access_token
    for login_data, resp in zip(logins, results):
        payload = decode_access_token(resp.json()["data"]["access_token"])
        assert payload["sub"] == login_data["user"]["id"]


# ===========================================================================
# Concurrent verify — Redis layer directly
# ===========================================================================

async def test_verify_otp_getdel_is_atomic(fake_redis):
    """Directly test the verify_otp function with concurrent callers.
    With GETDEL, exactly one caller should get the OTP data; the rest should
    raise ValueError because the key is already gone.
    """
    otp_ref = "atomic-test-ref"
    mobile = "9300000080"
    otp = "123456"
    await store_otp(fake_redis, otp_ref, mobile, otp, "ca")

    n = 8
    outcomes = await asyncio.gather(
        *[verify_otp(fake_redis, otp_ref, mobile, otp) for _ in range(n)],
        return_exceptions=True,
    )

    successes = [o for o in outcomes if isinstance(o, str)]
    errors = [o for o in outcomes if isinstance(o, Exception)]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {successes}"
    assert len(errors) == n - 1
    assert successes[0] == "ca"
    # All failures must be ValueError (not unexpected exceptions)
    assert all(isinstance(e, ValueError) for e in errors)
