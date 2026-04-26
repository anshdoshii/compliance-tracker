"""Tests for the three exception handlers registered in main.py.

Every error path in the API must return the standard envelope:
  {success: false, data: null, meta: null, error: {code, message}}

This ensures the Flutter client never receives an unexpected response shape.
"""

import pytest

BASE = "/v1/auth"


# ---------------------------------------------------------------------------
# Health check (sanity)
# ---------------------------------------------------------------------------

async def test_health_check_returns_ok(client):
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["error"] is None


# ---------------------------------------------------------------------------
# 404 — unknown routes
# ---------------------------------------------------------------------------

async def test_unknown_route_returns_404_in_envelope(client):
    resp = await client.get("/v1/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] is not None


async def test_wrong_method_returns_405_in_envelope(client):
    """GET on a POST-only endpoint must return 405 in the standard envelope."""
    resp = await client.get(f"{BASE}/otp/send")
    assert resp.status_code == 405
    body = resp.json()
    assert body["success"] is False


async def test_unknown_nested_route_returns_404(client):
    resp = await client.post("/v1/auth/nonexistent", json={})
    assert resp.status_code == 404 or resp.status_code == 405
    body = resp.json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# 422 — RequestValidationError handler
# ---------------------------------------------------------------------------

async def test_validation_error_returns_422_in_envelope(client):
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "bad"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["data"] is None
    assert body["meta"] is None


async def test_validation_error_message_is_list(client):
    """Error message should be a list of field errors, not a raw string."""
    resp = await client.post(f"{BASE}/otp/send", json={"mobile": "bad", "role": "ca"})
    body = resp.json()
    assert isinstance(body["error"]["message"], list)


async def test_completely_empty_body_returns_422(client):
    resp = await client.post(f"{BASE}/otp/send", json={})
    assert resp.status_code == 422
    assert resp.json()["success"] is False


async def test_null_body_returns_422_not_500(client):
    """Sending no body at all must not cause a 500."""
    resp = await client.post(
        f"{BASE}/otp/send",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 400 / 401 — HTTP exceptions raised by routers
# ---------------------------------------------------------------------------

async def test_invalid_otp_returns_400_in_envelope(client):
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9876543210", "otp": "000000", "otp_ref": "no-such-ref"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "OTP_INVALID"
    assert body["data"] is None


async def test_invalid_refresh_token_returns_401_in_envelope(client):
    resp = await client.post(f"{BASE}/token/refresh", json={"refresh_token": "bad.token.here"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TOKEN_INVALID"
    assert body["data"] is None


async def test_rate_limited_returns_429_in_envelope(client):
    """Rate-limit responses must also use the standard envelope."""
    mobile = "9876540099"
    from core.config import settings
    for _ in range(settings.OTP_RATE_LIMIT_PER_HOUR):
        await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": "ca"})

    resp = await client.post(f"{BASE}/otp/send", json={"mobile": mobile, "role": "ca"})
    assert resp.status_code == 429
    body = resp.json()
    assert body["success"] is False


# ---------------------------------------------------------------------------
# Every error response has consistent shape
# ---------------------------------------------------------------------------

async def test_all_error_codes_follow_envelope_shape(client):
    """Spot-check several error scenarios — all must have the standard shape."""
    scenarios = [
        # (path, json_body, expected_status)
        (f"{BASE}/otp/send", {"mobile": "bad"}, 422),
        (f"{BASE}/otp/verify", {"mobile": "9999999999", "otp": "000000", "otp_ref": "x"}, 400),
        (f"{BASE}/token/refresh", {"refresh_token": "junk"}, 401),
        ("/v1/nonexistent", None, 404),
    ]
    for path, body, expected_status in scenarios:
        if body is not None:
            resp = await client.post(path, json=body)
        else:
            resp = await client.get(path)
        assert resp.status_code == expected_status, f"Unexpected status on {path}"
        r = resp.json()
        assert r["success"] is False, f"success should be False on {path}"
        assert r["data"] is None, f"data should be None on {path}"
        assert r["error"] is not None, f"error should not be None on {path}"


async def test_no_error_response_exposes_raw_python_exception(client):
    """Error messages must never contain Python traceback strings."""
    resp = await client.post(
        f"{BASE}/otp/verify",
        json={"mobile": "9876543210", "otp": "000000", "otp_ref": "nonexistent"},
    )
    raw = resp.text
    for forbidden in ("Traceback", "File \"", "line ", "AttributeError", "KeyError", "TypeError"):
        assert forbidden not in raw, f"Traceback leaked in response: {raw[:200]}"
