"""Auth regression tests for POST /trade/backtest (F-08).

Before the fix this endpoint was public and could pull up to 30 years of FMP
EOD data per request. It must now require admin JWT or Bearer CRON_SECRET and
fail closed when CRON_SECRET is empty/unset.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.auth.deps import require_admin_or_cron
from nq_api.auth.models import User
from nq_api.main import app


@pytest.fixture
def client_no_auth_override():
    """TestClient with the global require_admin_or_cron override removed so
    the real dependency runs."""
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(require_admin_or_cron, None)
    client = TestClient(app)
    yield client
    app.dependency_overrides = overrides


def test_backtest_no_auth_returns_401(client_no_auth_override):
    with patch("nq_data.fmp.get_fmp_client") as mock_get_fmp:
        resp = client_no_auth_override.post("/trade/backtest", json={"market": "US", "years": 1})
    assert resp.status_code == 401
    mock_get_fmp.assert_not_called()


def test_backtest_non_admin_jwt_returns_403(client_no_auth_override, monkeypatch):
    """S1: a valid JWT for a user outside ADMIN_EMAILS gets 403, and the FMP
    client is never constructed."""
    from nq_api.auth import deps as auth_deps

    def fake_verify(token):
        return {"sub": "user-1", "email": "customer@example.com"}

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")

    with patch.object(auth_deps, "verify_supabase_jwt", fake_verify):
        with patch("nq_data.fmp.get_fmp_client") as mock_get_fmp:
            resp = client_no_auth_override.post(
                "/trade/backtest",
                json={"market": "US", "years": 1},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"
    mock_get_fmp.assert_not_called()


def test_backtest_wrong_cron_secret_returns_401(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "real-cron-secret-123456789012")
    resp = client_no_auth_override.post(
        "/trade/backtest",
        json={"market": "US", "years": 1},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


def test_backtest_empty_cron_secret_returns_401(client_no_auth_override, monkeypatch):
    """Fail-closed: an unset/empty CRON_SECRET never authorizes a bearer header."""
    monkeypatch.setenv("CRON_SECRET", "")
    resp = client_no_auth_override.post(
        "/trade/backtest",
        json={"market": "US", "years": 1},
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 401


def test_backtest_valid_cron_secret_does_not_call_fmp_on_wrong_secret(client_no_auth_override, monkeypatch):
    """Wrong secret must stop before the FMP client is ever constructed."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123456789012")

    with patch("nq_data.fmp.get_fmp_client") as mock_get_fmp:
        resp = client_no_auth_override.post(
            "/trade/backtest",
            json={"market": "US", "years": 1},
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert resp.status_code == 401
    mock_get_fmp.assert_not_called()


def test_backtest_valid_cron_secret_authorized(client_no_auth_override, monkeypatch):
    """With the right cron secret the endpoint proceeds (we mock the heavy
    downstream so the test stays fast)."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123456789012")

    fake_client = type(
        "FakeFMP",
        (),
        {
            "_enabled": True,
            "get_historical_prices": lambda *a, **k: None,
        },
    )()

    with patch("nq_data.fmp.get_fmp_client", return_value=fake_client):
        resp = client_no_auth_override.post(
            "/trade/backtest",
            json={"market": "US", "years": 1},
            headers={"Authorization": "Bearer test-cron-secret-123456789012"},
        )
    assert resp.status_code == 200


def test_backtest_valid_admin_jwt_authorized(client_no_auth_override, monkeypatch):
    """Admin JWT path is covered by require_admin; patch JWT verification so the
    fake token is accepted, and mark the returned email as admin."""
    from nq_api.auth import deps as auth_deps

    def fake_verify(token):
        return {"sub": "admin-1", "email": "admin@neuralquant.internal"}

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")

    fake_client = type(
        "FakeFMP",
        (),
        {
            "_enabled": True,
            "get_historical_prices": lambda *a, **k: None,
        },
    )()

    with patch.object(auth_deps, "verify_supabase_jwt", fake_verify):
        with patch("nq_data.fmp.get_fmp_client", return_value=fake_client):
            resp = client_no_auth_override.post(
                "/trade/backtest",
                json={"market": "US", "years": 1},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )

    assert resp.status_code == 200
