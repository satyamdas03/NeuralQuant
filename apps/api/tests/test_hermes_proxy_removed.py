"""T8 / F-06: the public Hermes proxy is not mounted.

It served live paper-trading state (positions, prices, P&L) without auth.
"""

import pytest
from fastapi.testclient import TestClient

from nq_api.main import app


@pytest.mark.parametrize("path", ["/hermes/health", "/hermes/status", "/hermes/trades",
                                  "/hermes/strategy", "/hermes/reflections", "/hermes/events"])
def test_hermes_routes_return_404(path):
    assert TestClient(app).get(path).status_code == 404
