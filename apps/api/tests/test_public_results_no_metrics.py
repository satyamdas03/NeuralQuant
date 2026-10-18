"""Regression tests for F-11 / B1: public quarterly results never expose metrics.

Before the fix, GET /testing/quarterly/public-results served a hardcoded Q1FY27
fixture (alpha 13.65, hit rate 88.1). After 9a8fd6d the empty/error paths
returned available:false, but the success path still computed and returned
alpha, hit_rate and returns whenever quarterly_test_results had return_pct.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.main import app

_METRIC_KEYS = ("alpha", "hit_rate", "avg_return", "avg_benchmark", "return_pct")


@pytest.fixture
def client():
    return TestClient(app)


def _assert_no_metrics(resp):
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["summary"] is None
    assert data["pool_breakdown"] == []
    assert data["equity_curve"] == []
    for key in _METRIC_KEYS:
        assert f'"{key}"' not in resp.text, key


def test_public_results_no_data(client):
    with patch("nq_api.routes.testing._supabase_rest", return_value=[]):
        _assert_no_metrics(client.get("/testing/quarterly/public-results"))


def test_public_results_ignores_evaluated_rows(client):
    """Fails on the old success path: evaluated rows produced alpha/hit_rate."""
    run = [{"id": "run-1", "run_date": "2026-06-02", "quarter": "Q1FY27",
            "test_type": "microcap", "selected_tickers": ["AAA", "BBB"]}]
    rows = [
        {"ticker": "AAA", "entry_price": 10, "exit_price": 12, "return_pct": 20.0,
         "benchmark_return_pct": -6.38, "alpha": 26.38, "evaluated_at": "2026-09-01"},
        {"ticker": "BBB", "entry_price": 10, "exit_price": 11, "return_pct": 10.0,
         "benchmark_return_pct": -6.38, "alpha": 16.38, "evaluated_at": "2026-09-01"},
    ]

    def fake_rest(table, method, query=None, **kw):
        return run if table == "quarterly_test_runs" else rows

    with patch("nq_api.routes.testing._supabase_rest", side_effect=fake_rest) as rest:
        resp = client.get("/testing/quarterly/public-results")
    _assert_no_metrics(resp)
    assert rest.call_count == 0  # the public endpoint does not read test tables
