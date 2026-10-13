"""Auth regression tests for /cron/* and /health/smoke (F-10, F-23).

Before the fix these endpoints used plain string comparison (`token != CRON_SECRET`)
and failed open when CRON_SECRET was empty. They must now use
`secrets.compare_digest`, require a non-empty CRON_SECRET (or admin JWT), and
reject everything else.
"""

from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.auth.deps import require_admin_or_cron
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


CRON_SECRET = "test-cron-secret-123456789012"


def _patch_cron_runners():
    """Prevent cron endpoints from starting real background work in tests."""
    stack = ExitStack()
    stack.enter_context(patch("nq_api.routes.cron._run_score_bg"))
    stack.enter_context(patch("nq_api.routes.cron._run_anjali_bg_wrap"))
    stack.enter_context(patch("nq_api.routes.cron._run_market_refresh_bg"))
    stack.enter_context(patch("nq_api.routes.cron._run_qf_sync_bg"))
    return stack


def test_cron_nightly_score_no_auth_returns_401(client_no_auth_override):
    resp = client_no_auth_override.post("/cron/nightly-score", params={"market": "US"})
    assert resp.status_code == 401


def test_cron_nightly_score_wrong_secret_returns_401(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    resp = client_no_auth_override.post(
        "/cron/nightly-score",
        params={"market": "US"},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


def test_cron_nightly_score_empty_secret_returns_401(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "")
    resp = client_no_auth_override.post(
        "/cron/nightly-score",
        params={"market": "US"},
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 401


def test_cron_nightly_score_valid_secret_returns_202(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    with _patch_cron_runners():
        resp = client_no_auth_override.post(
            "/cron/nightly-score",
            params={"market": "US"},
            headers={"Authorization": f"Bearer {CRON_SECRET}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


def test_cron_status_endpoints_require_auth(client_no_auth_override):
    for path in [
        "/cron/nightly-score/status",
        "/cron/anjali/status",
        "/cron/market-refresh/status",
        "/cron/quantfactor-sync/status",
    ]:
        resp = client_no_auth_override.get(path)
        assert resp.status_code == 401, f"{path} should require auth"


def test_cron_status_valid_secret_returns_200(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    resp = client_no_auth_override.get(
        "/cron/nightly-score/status",
        headers={"Authorization": f"Bearer {CRON_SECRET}"},
    )
    assert resp.status_code == 200


def test_cron_admin_jwt_authorized(client_no_auth_override, monkeypatch):
    """Admin JWT path is covered by require_admin; patch JWT verification so the
    fake token is accepted, and mark the returned email as admin."""
    from nq_api.auth import deps as auth_deps

    def fake_verify(token):
        return {"sub": "admin-1", "email": "admin@neuralquant.internal"}

    monkeypatch.setenv("ADMIN_EMAILS", "admin@neuralquant.internal")

    with patch.object(auth_deps, "verify_supabase_jwt", fake_verify):
        with _patch_cron_runners():
            resp = client_no_auth_override.post(
                "/cron/market-refresh",
                params={"market": "US"},
                headers={"Authorization": "Bearer fake-jwt-token"},
            )

    assert resp.status_code == 200


def test_health_smoke_no_auth_returns_401(client_no_auth_override):
    resp = client_no_auth_override.get("/health/smoke")
    assert resp.status_code == 401


def test_health_smoke_wrong_secret_returns_401(client_no_auth_override, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    resp = client_no_auth_override.get(
        "/health/smoke",
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


def test_health_smoke_valid_secret_passes_gate(client_no_auth_override, monkeypatch):
    """We only assert the auth gate opens; patch the expensive dependency checks."""
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)

    async def _fake_to_thread(*args, **kwargs):
        return {"ok": True}

    import nq_api.main as main_mod
    with patch.object(main_mod.asyncio, "to_thread", _fake_to_thread):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value.json.return_value = {"current_price": 1.0}
            resp = client_no_auth_override.get(
                "/health/smoke",
                headers={"Authorization": f"Bearer {CRON_SECRET}"},
            )
    # The endpoint returns 200 even when downstream checks fail.
    assert resp.status_code == 200
