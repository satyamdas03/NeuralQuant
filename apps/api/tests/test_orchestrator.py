import asyncio
from unittest.mock import patch, MagicMock
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.schemas import AnalystResponse, AgentOutput


def _make_agent_output(agent_name: str, stance: str = "BULL") -> AgentOutput:
    return AgentOutput(
        agent=agent_name,
        stance=stance,
        conviction="MEDIUM",
        thesis=f"{agent_name} thesis here.",
        key_points=["Point A", "Point B", "Point C"],
    )


def _mock_all_agents(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="""
STANCE: BULL
CONVICTION: MEDIUM
THESIS: Overall the stock looks attractive.
KEY_POINTS:
- Strong fundamentals
- Positive macro backdrop
- Insider buying confirmed
""")]
    )
    return mock_client


def test_orchestrator_returns_analyst_response():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls, \
         patch("nq_api.agents.head_analyst.anthropic.Anthropic") as mock_head_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        _mock_all_agents(mock_cls)
        _mock_all_agents(mock_head_cls)
        orch = ParaDebateOrchestrator()
        result = asyncio.run(orch.analyse(ticker="AAPL", market="US", context={"vix": 18.0}))

        assert isinstance(result, AnalystResponse)
        assert result.ticker == "AAPL"
        assert result.head_analyst_verdict in (
            "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
        )
        assert len(result.agent_outputs) == 6  # 5 specialists + adversarial
        assert len(result.investment_thesis) > 50
        assert isinstance(result.risk_factors, list)


def test_orchestrator_adversarial_is_always_bear():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls, \
         patch("nq_api.agents.head_analyst.anthropic.Anthropic") as mock_head_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        _mock_all_agents(mock_cls)
        _mock_all_agents(mock_head_cls)
        orch = ParaDebateOrchestrator()
        result = asyncio.run(orch.analyse(ticker="AAPL", market="US", context={}))

        adversarial = next(o for o in result.agent_outputs if o.agent == "ADVERSARIAL")
        assert adversarial.stance in ("BEAR", "NEUTRAL"), \
            "Adversarial agent must never be BULL"
