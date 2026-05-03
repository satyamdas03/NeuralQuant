import contextlib
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from nq_api.main import app
from nq_api.schemas import AnalystResponse, AgentOutput

client = TestClient(app)


def _mock_analyst_response(ticker: str) -> AnalystResponse:
    return AnalystResponse(
        ticker=ticker,
        head_analyst_verdict="BUY",
        investment_thesis="Strong quality fundamentals with positive momentum.",
        bull_case="Quality metrics excellent; management is buying shares.",
        bear_case="Valuation is stretched at current levels.",
        risk_factors=["Regulatory risk", "Margin compression"],
        agent_outputs=[
            AgentOutput(agent="MACRO", stance="BULL", conviction="MEDIUM",
                        thesis="Macro supports.", key_points=["Point A"]),
        ],
        consensus_score=0.72,
    )


@contextlib.contextmanager
def _patch_analyst(ticker: str):
    """Patches the orchestrator for analyst tests.
    Note: analyst.py does not import get_signal_engine, so we don't mock it."""
    with patch("nq_api.routes.analyst.ParaDebateOrchestrator") as MockOrch, \
         patch("nq_api.routes.analyst.score_cache") as mock_cache:
        orch_instance = MagicMock()
        orch_instance.analyse = AsyncMock(return_value=_mock_analyst_response(ticker))
        MockOrch.return_value = orch_instance
        # Mock score_cache to return empty (no enrichment data needed for test)
        mock_cache.read_one.return_value = None
        mock_cache.read_enrichment.return_value = None
        yield


def test_analyst_post_returns_report():
    with _patch_analyst("AAPL"):
        response = client.post("/analyst", json={"ticker": "AAPL", "market": "US"})
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["head_analyst_verdict"] == "BUY"
        assert "investment_thesis" in data
        assert len(data["agent_outputs"]) >= 1


def test_analyst_verdict_is_valid():
    with _patch_analyst("TSLA"):
        response = client.post("/analyst", json={"ticker": "TSLA", "market": "US"})
        assert response.status_code == 200
        data = response.json()
        assert data["head_analyst_verdict"] in (
            "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
        )