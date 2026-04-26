"""Tests for CORS policy and validation-error sanitisation in main.py."""

import pytest

BASE_AUTH = "/v1/auth"


# ---------------------------------------------------------------------------
# Validation error sanitisation
# ---------------------------------------------------------------------------

async def test_validation_error_does_not_leak_raw_otp(client):
    """422 responses must not expose submitted field values (e.g. an OTP string)."""
    resp = await client.post(
        f"{BASE_AUTH}/otp/send",
        json={"mobile": "SHORT", "role": "ca"},
    )
    assert resp.status_code == 422
    body = resp.json()

    # Must use our standard envelope
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    # The raw submitted value ("SHORT") must NOT appear anywhere in the error detail
    import json
    raw_text = json.dumps(body["error"]["message"])
    assert "SHORT" not in raw_text


async def test_validation_error_does_not_leak_mobile_number(client):
    """Submitted mobile number must not appear in 422 error bodies."""
    resp = await client.post(
        f"{BASE_AUTH}/otp/send",
        json={"mobile": "12345ABCDE", "role": "ca"},
    )
    assert resp.status_code == 422
    import json
    raw_text = json.dumps(resp.json())
    assert "12345ABCDE" not in raw_text


async def test_validation_error_envelope_shape(client):
    """422 must use the standard {success, data, meta, error} envelope."""
    resp = await client.post(f"{BASE_AUTH}/otp/send", json={"mobile": "bad"})
    assert resp.status_code == 422
    body = resp.json()
    assert "success" in body
    assert "data" in body
    assert "meta" in body
    assert "error" in body
    assert body["data"] is None
    assert body["meta"] is None


async def test_validation_error_message_contains_loc(client):
    """Error message should still include the field location so clients know what to fix."""
    resp = await client.post(
        f"{BASE_AUTH}/otp/send",
        json={"mobile": "bad", "role": "ca"},
    )
    assert resp.status_code == 422
    errors = resp.json()["error"]["message"]
    assert isinstance(errors, list)
    assert len(errors) > 0
    # Each error item must have loc and msg but NOT input
    for err in errors:
        assert "loc" in err
        assert "msg" in err
        assert "input" not in err


async def test_missing_required_field_returns_422(client):
    """Missing 'role' field must return 422, not 500."""
    resp = await client.post(f"{BASE_AUTH}/otp/send", json={"mobile": "9876543210"})
    assert resp.status_code == 422


async def test_invalid_role_value_returns_422(client):
    """Role must be 'ca' or 'smb' — anything else is a 422."""
    resp = await client.post(
        f"{BASE_AUTH}/otp/send",
        json={"mobile": "9876543210", "role": "admin"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

async def test_cors_allows_localhost_3000(client):
    """Dev mode must accept requests from localhost:3000."""
    resp = await client.get(
        "/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_cors_allows_localhost_8080(client):
    resp = await client.get(
        "/v1/health",
        headers={"Origin": "http://localhost:8080"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:8080"


async def test_cors_allows_localhost_5173(client):
    """Vite dev server port."""
    resp = await client.get(
        "/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_cors_blocks_unknown_origin(client):
    """Unknown origins must not receive the ACAO header."""
    resp = await client.get(
        "/v1/health",
        headers={"Origin": "http://evil.com"},
    )
    assert resp.status_code == 200  # request still succeeds
    assert "access-control-allow-origin" not in resp.headers


async def test_cors_blocks_wildcard_is_not_set(client):
    """Wildcard '*' must never appear as the allowed origin."""
    resp = await client.get(
        "/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )
    acao = resp.headers.get("access-control-allow-origin", "")
    assert acao != "*"


async def test_cors_preflight_localhost(client):
    """OPTIONS preflight from localhost must be accepted."""
    resp = await client.options(
        "/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
