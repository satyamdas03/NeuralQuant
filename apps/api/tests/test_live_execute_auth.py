"""Auth regression tests for POST /live/execute (S1 follow-up).

It runs the signal pipeline, writes signal_log rows and, with trading flags
on, can place broker orders. It was open to any signed-in user; it now
requires an admin JWT or Bearer CRON_SECRET, like /live/classify.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.auth.deps import get_current_user, require_admin_or_cron
from nq_api.main import app

PIPELINE = "nq_api.routes.live._get_signals_from_scores"


@pytest.fixture
def client_real_auth():
    """TestClient with the global auth overrides removed so the real
    dependencies run."""
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(require_admin_or_cron, None)
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides = overrides


def _fake_jwt(email):
    def fake_verify(token):
        return {"sub": "user-1", "email": email}
    return fake_verify


def test_execute_no_auth_returns_401(client_real_auth):
    with patch(PIPELINE) as signals:
        resp = client_real_auth.post("/live/execute", params={"market": "US", "n": 1})
    assert resp.status_code == 401
    signals.assert_not_called()


def test_execute_non_admin_jwt_returns_403(client_real_auth, monkeypatch):
    from nq_api.auth import deps as auth_deps

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")
    with patch.object(auth_deps, "verify_supabase_jwt", _fake_jwt("customer@example.com")):
        with patch(PIPELINE) as signals:
            resp = client_real_auth.post(
                "/live/execute",
                params={"market": "US", "n": 1},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"
    signals.assert_not_called()


def test_execute_admin_jwt_reaches_pipeline(client_real_auth, monkeypatch):
    from nq_api.auth import deps as auth_deps

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")
    with patch.object(auth_deps, "verify_supabase_jwt", _fake_jwt("admin@neuralquant.internal")):
        with patch(PIPELINE, return_value=[]) as signals, \
             patch("nq_api.routes.live._get_todays_pnl", return_value=0.0), \
             patch("nq_api.routes.live._count_broker_positions", return_value=0):
            resp = client_real_auth.post(
                "/live/execute",
                params={"market": "US", "n": 1},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )
    assert resp.status_code == 200
    signals.assert_called_once()
