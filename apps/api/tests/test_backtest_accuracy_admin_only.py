"""F-11: GET /backtest/accuracy serves unaudited hit-rate and return figures.

It was public (live 200 with no auth on 2026-10-18). It is now admin only.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.auth.deps import get_current_user
from nq_api.main import app


@pytest.fixture
def client_real_auth():
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides = overrides


def test_accuracy_requires_auth(client_real_auth):
    with patch("nq_api.routes.backtest._get_accuracy_sync") as compute:
        resp = client_real_auth.get("/backtest/accuracy")
    assert resp.status_code == 401
    compute.assert_not_called()


def test_accuracy_non_admin_forbidden(monkeypatch):
    # conftest signs every request in as test@test.com (tier pro, not admin)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    with patch("nq_api.routes.backtest._get_accuracy_sync") as compute:
        resp = TestClient(app).get("/backtest/accuracy")
    assert resp.status_code == 403
    compute.assert_not_called()


def test_accuracy_admin_allowed(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "test@test.com")
    from nq_api.routes import backtest
    sentinel = backtest._accuracy_default("ok")
    with patch("nq_api.routes.backtest._get_accuracy_sync", return_value=sentinel) as compute:
        resp = TestClient(app).get("/backtest/accuracy")
    assert resp.status_code == 200
    compute.assert_called_once()
