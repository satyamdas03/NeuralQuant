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
    """Patches both the orchestrator AND signal engine for analyst tests."""
    with patch("nq_api.routes.analyst.ParaDebateOrchestrator") as MockOrch, \
         patch("nq_api.routes.analyst.get_signal_engine") as mock_engine_factory:
        orch_instance = MagicMock()
        orch_instance.analyse = AsyncMock(return_value=_mock_analyst_response(ticker))
        MockOrch.return_value = orch_instance
        engine = MagicMock()
        engine.compute.return_value = pd.DataFrame([{
            "ticker": ticker,
            "composite_score": 0.75,
            "quality_percentile": 0.8,
            "momentum_percentile": 0.7,
            "short_interest_percentile": 0.6,
            "regime_id": 1,
            "momentum_raw": 0.1,
        }])
        mock_engine_factory.return_value = engine
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
