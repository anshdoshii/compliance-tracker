"""Tests for FastAPI dependency functions — get_current_user, require_ca, require_smb."""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from core.auth import create_access_token, create_refresh_token
from core.config import settings
from core.dependencies import get_current_user, require_ca, require_smb
from models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _create_user(db, mobile: str, role: str = "ca", is_active: bool = True) -> User:
    user = User(mobile=mobile, role=role, full_name="Test User", is_active=is_active)
    db.add(user)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# get_current_user — no credentials
# ---------------------------------------------------------------------------

async def test_no_credentials_returns_401(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, db=db_session)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — malformed / bad tokens
# ---------------------------------------------------------------------------

async def test_invalid_jwt_returns_401(db_session):
    creds = _make_creds("not.a.real.token")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_missing_sub_claim_returns_401_not_500(db_session):
    """A JWT without 'sub' must return 401, never 500."""
    token = jwt.encode(
        {"role": "ca", "type": "access", "exp": 9999999999},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_non_uuid_sub_returns_401_not_500(db_session):
    """A JWT with a non-UUID 'sub' must return 401, never 500."""
    token = jwt.encode(
        {"sub": "not-a-uuid", "role": "ca", "type": "access", "exp": 9999999999},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_null_sub_returns_401_not_500(db_session):
    """A JWT with sub=None must return 401, never 500."""
    token = jwt.encode(
        {"sub": None, "role": "ca", "type": "access", "exp": 9999999999},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_refresh_token_rejected_as_access_token(db_session):
    """A refresh token must not authenticate as an access token."""
    token = create_refresh_token("550e8400-e29b-41d4-a716-446655440000")
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_tampered_token_returns_401(db_session):
    token = create_access_token("550e8400-e29b-41d4-a716-446655440000", "ca")
    tampered = token[:-4] + "XXXX"
    creds = _make_creds(tampered)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — user not found / inactive
# ---------------------------------------------------------------------------

async def test_unknown_user_id_returns_401(db_session):
    """Valid JWT but user doesn't exist in DB."""
    token = create_access_token(str(uuid.uuid4()), "ca")
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


async def test_inactive_user_returns_401(db_session):
    """Deactivated users must not authenticate even with a valid token."""
    user = await _create_user(db_session, "9100000011", role="ca", is_active=False)
    token = create_access_token(str(user.id), "ca")
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=db_session)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — success
# ---------------------------------------------------------------------------

async def test_valid_token_returns_user(db_session):
    user = await _create_user(db_session, "9100000012", role="ca")
    token = create_access_token(str(user.id), "ca")
    creds = _make_creds(token)

    result = await get_current_user(credentials=creds, db=db_session)

    assert result.id == user.id
    assert result.role == "ca"
    assert result.is_active is True


async def test_valid_smb_token_returns_smb_user(db_session):
    user = await _create_user(db_session, "9100000013", role="smb")
    token = create_access_token(str(user.id), "smb")
    creds = _make_creds(token)

    result = await get_current_user(credentials=creds, db=db_session)
    assert result.role == "smb"


# ---------------------------------------------------------------------------
# require_ca
# ---------------------------------------------------------------------------

async def test_require_ca_passes_for_ca_user():
    user = User(mobile="9100000020", role="ca", full_name="CA User", is_active=True)
    result = await require_ca(user=user)
    assert result is user


async def test_require_ca_rejects_smb_user():
    user = User(mobile="9100000021", role="smb", full_name="SMB User", is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        await require_ca(user=user)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_smb
# ---------------------------------------------------------------------------

async def test_require_smb_passes_for_smb_user():
    user = User(mobile="9100000022", role="smb", full_name="SMB User", is_active=True)
    result = await require_smb(user=user)
    assert result is user


async def test_require_smb_rejects_ca_user():
    user = User(mobile="9100000023", role="ca", full_name="CA User", is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        await require_smb(user=user)
    assert exc_info.value.status_code == 403
