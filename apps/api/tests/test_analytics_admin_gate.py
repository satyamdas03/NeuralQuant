import pytest
from fastapi import HTTPException
from nq_api.routes import analytics
from nq_api.auth.models import User


def _user(email):
    return User(id="U1", email=email, tier="pro", paypal_subscription_id=None,
                subscription_status="active", referral_bonus_queries=0)


def test_non_admin_pro_user_denied(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@neuralquant.co")
    with pytest.raises(HTTPException) as exc:
        analytics._require_admin(_user("randompro@example.com"))
    assert exc.value.status_code == 403


def test_admin_email_allowed(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@neuralquant.co, satyamdas03@gmail.com")
    analytics._require_admin(_user("satyamdas03@gmail.com"))  # no raise


def test_denied_when_allowlist_empty(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    with pytest.raises(HTTPException):
        analytics._require_admin(_user("anyone@example.com"))
