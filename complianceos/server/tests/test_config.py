"""Tests for Settings validation — especially the production secret guard."""

import pytest
from pydantic import ValidationError

from core.config import Settings

_PLACEHOLDER = "change-me-in-production-must-be-at-least-32-chars!!"
_REAL_SECRET = "super-secret-jwt-key-that-is-long-enough-for-production"


# ---------------------------------------------------------------------------
# Production JWT secret guard
# ---------------------------------------------------------------------------

def test_production_rejects_placeholder_secret():
    """Server must refuse to start with the default key in production."""
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY=_PLACEHOLDER)


def test_production_rejects_any_change_me_prefix():
    """Any key that starts with 'change-me' is rejected in production."""
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="change-me-custom-suffix")


def test_production_with_real_secret_passes():
    """A proper secret must not raise."""
    s = Settings(ENVIRONMENT="production", JWT_SECRET_KEY=_REAL_SECRET)
    assert s.is_production is True
    assert s.is_development is False


def test_development_allows_placeholder_secret():
    """Dev mode should never block startup due to the placeholder key."""
    s = Settings(ENVIRONMENT="development", JWT_SECRET_KEY=_PLACEHOLDER)
    assert s.is_development is True


def test_staging_allows_placeholder_secret():
    """Only 'production' triggers the guard; any other env string is unrestricted."""
    s = Settings(ENVIRONMENT="staging", JWT_SECRET_KEY=_PLACEHOLDER)
    assert s.is_production is False
    assert s.is_development is False


# ---------------------------------------------------------------------------
# Environment flags
# ---------------------------------------------------------------------------

def test_is_development_flag():
    s = Settings(ENVIRONMENT="development", JWT_SECRET_KEY=_PLACEHOLDER)
    assert s.is_development is True
    assert s.is_production is False


def test_is_production_flag():
    s = Settings(ENVIRONMENT="production", JWT_SECRET_KEY=_REAL_SECRET)
    assert s.is_production is True
    assert s.is_development is False
