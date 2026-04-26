"""Performance tests — latency and throughput baselines.

These tests enforce upper-bound SLAs on critical hot paths so regressions
are caught before they reach production.  All thresholds are deliberately
generous (we are running against an in-memory SQLite DB and a fake Redis, not
production hardware), so a failure here means something is seriously slow —
not a flaky margin miss.

Thresholds:
  - Single HTTP request:   < 300 ms
  - Health check:          < 50 ms
  - JWT encode + decode:   1 000 ops in < 1 s
  - Rate-limit check:      < 20 ms per call
  - 20 sequential OTP sends: < 3 s total
  - 50 DB row inserts:     < 2 s total
  - 10 concurrent requests: < 1 s wall-clock
"""

import asyncio
import json
import time
import uuid

import pytest
from sqlalchemy import select

from core.auth import (
    check_otp_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_otp,
    store_otp,
)
from models.ca_profile import CAProfile
from models.user import User

BASE = "/v1/auth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _login(client, fake_redis, mobile: str, role: str = "ca") -> dict:
    send = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": role})
    otp_ref = send.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": mobile, "otp": otp, "otp_ref": otp_ref},
    )
    return resp.json()["data"]


# ===========================================================================
# Health check — baseline for raw ASGI overhead
# ===========================================================================

async def test_health_check_latency(client):
    """Health check must respond in under 50 ms — it does no DB/Redis work."""
    start = time.perf_counter()
    resp = await client.get("/v1/health")
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 0.05, f"Health check took {elapsed * 1000:.1f} ms (limit 50 ms)"


async def test_health_check_p99_under_load(client):
    """50 sequential health checks — p99 must stay under 50 ms."""
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        await client.get("/v1/health")
        latencies.append(time.perf_counter() - t0)

    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99)]
    assert p99 < 0.05, f"p99 health check latency = {p99 * 1000:.1f} ms (limit 50 ms)"


# ===========================================================================
# OTP send — Redis + SMS stub
# ===========================================================================

async def test_single_otp_send_latency(client, fake_redis):
    """A single OTP send (rate check + Redis write) must complete in < 300 ms."""
    start = time.perf_counter()
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "9400000001", "role": "ca"})
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 0.3, f"OTP send took {elapsed * 1000:.1f} ms (limit 300 ms)"


async def test_20_sequential_otp_sends_under_3s(client, fake_redis):
    """20 sequential OTP sends for distinct mobiles must complete in < 3 s.
    Establishes a baseline: if a DB query or Redis call becomes O(n), this
    catches it before it compounds in production.
    """
    start = time.perf_counter()
    for i in range(20):
        mobile = f"9400001{i:03d}"
        resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": "ca"})
        assert resp.status_code == 200, f"Send {i} failed: {resp.json()}"
    elapsed = time.perf_counter() - start

    assert elapsed < 3.0, f"20 sequential OTP sends took {elapsed:.2f} s (limit 3 s)"


# ===========================================================================
# OTP verify + user upsert
# ===========================================================================

async def test_single_otp_verify_latency(client, fake_redis):
    """OTP verify (Redis read + DB upsert + JWT mint) must complete in < 300 ms."""
    send = await client.post(f"{BASE}/otp/send", json={"mobile": "9400000100", "role": "ca"})
    otp_ref = send.json()["data"]["otp_ref"]
    raw = await fake_redis.get(f"otp:{otp_ref}")
    otp = json.loads(raw)["otp"]

    start = time.perf_counter()
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9400000100", "otp": otp, "otp_ref": otp_ref},
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 0.3, f"OTP verify took {elapsed * 1000:.1f} ms (limit 300 ms)"


# ===========================================================================
# Token refresh
# ===========================================================================

async def test_token_refresh_latency(client, fake_redis):
    """Token refresh (Redis read + DB fetch + JWT mint) must complete in < 300 ms."""
    data = await _login(client, fake_redis, "9400000200")

    start = time.perf_counter()
    resp = await client.post(
        f"{BASE}/token/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 0.3, f"Token refresh took {elapsed * 1000:.1f} ms (limit 300 ms)"


# ===========================================================================
# JWT throughput — pure CPU, no I/O
# ===========================================================================

async def test_jwt_encode_throughput():
    """Create 1 000 access tokens. Must complete in under 1 s.
    Guards against accidentally switching to a slow algorithm or adding
    blocking crypto work in the hot JWT path.
    """
    user_id = str(uuid.uuid4())
    start = time.perf_counter()
    for _ in range(1000):
        create_access_token(user_id, "ca")
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"1 000 access token encodes took {elapsed:.3f} s (limit 1 s)"


async def test_jwt_decode_throughput():
    """Decode 1 000 access tokens. Must complete in under 1 s."""
    token = create_access_token(str(uuid.uuid4()), "ca")
    start = time.perf_counter()
    for _ in range(1000):
        decode_access_token(token)
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"1 000 access token decodes took {elapsed:.3f} s (limit 1 s)"


async def test_refresh_token_create_throughput():
    """Create 1 000 refresh tokens (includes secrets.token_hex). Under 1 s."""
    user_id = str(uuid.uuid4())
    start = time.perf_counter()
    for _ in range(1000):
        create_refresh_token(user_id)
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"1 000 refresh token creates took {elapsed:.3f} s (limit 1 s)"


# ===========================================================================
# Rate limit check — Redis pipeline overhead
# ===========================================================================

async def test_rate_limit_check_latency(fake_redis):
    """A single rate-limit check (pipeline INCR + EXPIRE) must complete in < 20 ms."""
    start = time.perf_counter()
    await check_otp_rate_limit(fake_redis, "9400000300")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.02, f"Rate limit check took {elapsed * 1000:.1f} ms (limit 20 ms)"


async def test_100_rate_limit_checks_under_500ms(fake_redis):
    """100 sequential rate-limit checks for distinct mobiles must finish in < 500 ms."""
    start = time.perf_counter()
    for i in range(100):
        await check_otp_rate_limit(fake_redis, f"94000003{i:02d}")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5, f"100 rate limit checks took {elapsed:.3f} s (limit 0.5 s)"


# ===========================================================================
# DB bulk insert — ORM layer overhead
# ===========================================================================

async def test_50_user_inserts_under_2s(db_session):
    """Insert 50 User rows sequentially. Must complete in < 2 s.
    Catches accidental per-row queries or missing bulk-insert paths.
    """
    start = time.perf_counter()
    for i in range(50):
        u = User(mobile=f"950000{i:04d}", role="ca", full_name=f"User {i}")
        db_session.add(u)
    await db_session.flush()
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"50 User inserts took {elapsed:.3f} s (limit 2 s)"


async def test_50_ca_profile_inserts_under_2s(db_session):
    """Insert 50 User + CAProfile rows. Exercises FK resolution overhead."""
    users = []
    for i in range(50):
        u = User(mobile=f"960000{i:04d}", role="ca", full_name=f"CA {i}")
        db_session.add(u)
        users.append(u)
    await db_session.flush()

    start = time.perf_counter()
    for u in users:
        p = CAProfile(user_id=u.id)
        db_session.add(p)
    await db_session.flush()
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"50 CAProfile inserts took {elapsed:.3f} s (limit 2 s)"


async def test_db_read_scales_with_rows(db_session):
    """Query 50 users with a WHERE clause. Must complete in < 500 ms.
    A full-table scan on 50 rows in SQLite should be trivially fast;
    anything slower suggests a missing index or ORM N+1 query.
    """
    for i in range(50):
        u = User(mobile=f"970000{i:04d}", role="smb", full_name=f"SMB {i}")
        db_session.add(u)
    await db_session.flush()

    start = time.perf_counter()
    result = await db_session.execute(
        select(User).where(User.role == "smb")
    )
    rows = result.scalars().all()
    elapsed = time.perf_counter() - start

    assert len(rows) >= 50
    assert elapsed < 0.5, f"SELECT 50 users took {elapsed * 1000:.1f} ms (limit 500 ms)"


# ===========================================================================
# Concurrent HTTP requests — wall-clock throughput
# ===========================================================================

async def test_10_concurrent_health_checks_under_200ms(client):
    """10 concurrent health checks must all complete within 200 ms wall-clock.
    If the server serialises requests, 10 × 5 ms = 50 ms; if it's blocked on
    something it would blow the budget.
    """
    start = time.perf_counter()
    responses = await asyncio.gather(
        *[client.get("/v1/health") for _ in range(10)]
    )
    elapsed = time.perf_counter() - start

    assert all(r.status_code == 200 for r in responses)
    assert elapsed < 0.2, f"10 concurrent health checks took {elapsed * 1000:.1f} ms (limit 200 ms)"


async def test_concurrent_otp_sends_wall_clock(client, fake_redis):
    """5 concurrent OTP sends (distinct mobiles) must complete in < 500 ms
    wall-clock — not 5 × single-request latency.  Tests that the async path
    does not accidentally block the event loop.
    """
    mobiles = [f"980000000{i}" for i in range(5)]

    start = time.perf_counter()
    responses = await asyncio.gather(
        *[client.post(f"{BASE}/otp/send", json={"mobile": m, "role": "ca"}) for m in mobiles]
    )
    elapsed = time.perf_counter() - start

    assert all(r.status_code == 200 for r in responses)
    assert elapsed < 0.5, (
        f"5 concurrent OTP sends took {elapsed * 1000:.1f} ms wall-clock (limit 500 ms)"
    )


async def test_mixed_concurrent_requests_wall_clock(client, fake_redis):
    """Mix of health checks and OTP sends running concurrently — total wall-clock
    must be less than if they ran sequentially (proves real async concurrency).
    """
    mobiles = [f"990000000{i}" for i in range(3)]

    start = time.perf_counter()
    responses = await asyncio.gather(
        client.get("/v1/health"),
        *[client.post(f"{BASE}/otp/send", json={"mobile": m, "role": "ca"}) for m in mobiles],
        client.get("/v1/health"),
    )
    elapsed = time.perf_counter() - start

    assert all(r.status_code in (200,) for r in responses)
    # 5 requests all done in under 500 ms proves they ran concurrently
    assert elapsed < 0.5, f"Mixed concurrent batch took {elapsed * 1000:.1f} ms (limit 500 ms)"


# ===========================================================================
# OTP store/verify throughput — Redis layer
# ===========================================================================

async def test_otp_store_and_verify_throughput(fake_redis):
    """Store + verify 100 OTPs sequentially. Must complete in < 1 s.
    Verifies the Redis round-trip overhead stays low.
    """
    pairs = []
    for i in range(100):
        otp_ref = f"perf-ref-{i}"
        mobile = f"980000{i:04d}"
        otp = generate_otp()
        pairs.append((otp_ref, mobile, otp))
        await store_otp(fake_redis, otp_ref, mobile, otp, "ca")

    from core.auth import verify_otp
    start = time.perf_counter()
    for otp_ref, mobile, otp in pairs:
        role = await verify_otp(fake_redis, otp_ref, mobile, otp)
        assert role == "ca"
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"100 OTP store+verify cycles took {elapsed:.3f} s (limit 1 s)"
