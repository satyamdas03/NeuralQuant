import pytest
from fastapi import HTTPException

from nq_api.auth import deps

# Obvious low-entropy placeholder (not a real secret; keeps gitleaks quiet).
SECRET = "x" * 24


@pytest.fixture
def test_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")


def test_bypass_inactive_when_unset(monkeypatch, test_env):
    monkeypatch.delenv("SMOKE_TEST_SECRET", raising=False)
    assert deps._smoke_bypass_ok("anything") is False


def test_bypass_inactive_when_secret_too_short(monkeypatch, test_env):
    monkeypatch.setenv("SMOKE_TEST_SECRET", "short")
    assert deps._smoke_bypass_ok("short") is False


def test_bypass_active_when_strong_and_matches(monkeypatch, test_env):
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)
    assert deps._smoke_bypass_ok(SECRET) is True
    assert deps._smoke_bypass_ok("wrong") is False


@pytest.mark.parametrize("env", ["production", "development", "staging", ""])
def test_bypass_refused_outside_test_env(monkeypatch, env):
    monkeypatch.setenv("ENVIRONMENT", env)
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)
    assert deps._smoke_bypass_ok(SECRET) is False


def test_bypass_refused_when_environment_unset(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)
    assert deps._smoke_bypass_ok(SECRET) is False


def test_production_matching_smoke_header_does_not_authenticate(monkeypatch):
    """ENVIRONMENT=production + matching X-Smoke-Secret must not yield a user."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)

    with pytest.raises(HTTPException) as exc:
        deps.get_current_user_smoke(x_smoke_secret=SECRET, authorization=None)
    assert exc.value.status_code == 401

    assert deps.get_current_user_optional(x_smoke_secret=SECRET, authorization=None) is None


def test_test_env_matching_smoke_header_authenticates(monkeypatch, test_env):
    """ENVIRONMENT=test + matching X-Smoke-Secret still returns the smoke user."""
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)

    user = deps.get_current_user_smoke(x_smoke_secret=SECRET, authorization=None)
    assert user.email == "smoke-test@neuralquant.internal"

    user_opt = deps.get_current_user_optional(x_smoke_secret=SECRET, authorization=None)
    assert user_opt is not None and user_opt.email == "smoke-test@neuralquant.internal"


def test_bypass_does_not_log_secret(monkeypatch, caplog):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SMOKE_TEST_SECRET", SECRET)
    with caplog.at_level("DEBUG"):
        deps._smoke_bypass_ok(SECRET)
        deps.get_current_user_optional(x_smoke_secret=SECRET, authorization=None)
    assert SECRET not in caplog.text
