"""Auth regression tests for POST /live/classify (F-07).

Before the fix this endpoint was public and called Claude / Finnhub /
StockTwits. It must now require admin JWT or Bearer CRON_SECRET and fail
closed when CRON_SECRET is empty/unset.
"""

import os
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


def test_classify_no_auth_returns_401(client_no_auth_override):
    resp = client_no_auth_override.post("/live/classify", params={"market": "US", "top_n": 2})
    assert resp.status_code == 401
    assert resp.json()["detail"] in ("missing Bearer token", "Admin access required")


def test_classify_wrong_cron_secret_returns_401(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "real-cron-secret-123456789012")
    resp = client_no_auth_override.post(
        "/live/classify",
        params={"market": "US", "top_n": 2},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


def test_classify_empty_cron_secret_returns_401(client_no_auth_override, monkeypatch):
    """Fail-closed: an unset/empty CRON_SECRET never authorizes a bearer header."""
    monkeypatch.setenv("CRON_SECRET", "")
    resp = client_no_auth_override.post(
        "/live/classify",
        params={"market": "US", "top_n": 2},
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 401


def test_classify_valid_cron_secret_does_not_call_downstream(client_no_auth_override, monkeypatch):
    """With a valid cron secret the pipeline should run; with a wrong one the
    downstream Claude/FMP clients must not be invoked."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123456789012")

    with patch("nq_data.news_pipeline.run_classification_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {"status": "ok", "classified": []}
        resp = client_no_auth_override.post(
            "/live/classify",
            params={"market": "US", "top_n": 2},
            headers={"Authorization": "Bearer test-cron-secret-123456789012"},
        )
    assert resp.status_code == 200
    mock_pipeline.assert_called_once()


def test_classify_valid_admin_jwt_uses_require_admin(client_no_auth_override, monkeypatch):
    """Admin JWT path is covered by require_admin; patch JWT verification so the
    fake token is accepted, and mark the returned email as admin."""
    from nq_api.auth import deps as auth_deps

    def fake_verify(token):
        return {"sub": "admin-1", "email": "admin@neuralquant.internal"}

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")

    with patch.object(auth_deps, "verify_supabase_jwt", fake_verify):
        with patch("nq_data.news_pipeline.run_classification_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"status": "ok", "classified": []}
            resp = client_no_auth_override.post(
                "/live/classify",
                params={"market": "US", "top_n": 2},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )

    assert resp.status_code == 200
    mock_pipeline.assert_called_once()
