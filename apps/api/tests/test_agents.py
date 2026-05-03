import pytest
from unittest.mock import MagicMock, patch
from nq_api.agents.macro import MacroAgent
from nq_api.agents.fundamental import FundamentalAgent
from nq_api.agents.technical import TechnicalAgent
from nq_api.agents.sentiment import SentimentAgent
from nq_api.agents.geopolitical import GeopoliticalAgent
from nq_api.agents.adversarial import AdversarialAgent
from nq_api.schemas import AgentOutput


def _mock_claude_response(content: str):
    """Minimal mock of anthropic Message object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=content)]
    return msg


MOCK_MACRO_RESPONSE = """
STANCE: BULL
CONVICTION: MEDIUM
THESIS: The macro environment is supportive with the Fed on pause and ISM PMI above 50, indicating continued expansion. VIX is subdued, suggesting market stability.
KEY_POINTS:
- Fed funds rate stable; no imminent hikes expected
- ISM PMI at 51 signals manufacturing expansion
- VIX at 18 indicates low systemic fear
- Yield curve normalising — 10Y-2Y spread turning positive
- Historical regime analysis favours Risk-On allocation
"""

MOCK_RESPONSE = """
STANCE: NEUTRAL
CONVICTION: MEDIUM
THESIS: Analysis is inconclusive given mixed signals. Further data required.
KEY_POINTS:
- Signal A is positive
- Signal B is negative
- Net effect is neutral
"""


def test_macro_agent_parses_output():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(MOCK_MACRO_RESPONSE)

        agent = MacroAgent()
        result = agent.run(ticker="AAPL", context={"vix": 18.0, "ism_pmi": 51.0})

        assert isinstance(result, AgentOutput)
        assert result.agent == "MACRO"
        assert result.stance == "BULL"
        assert result.conviction == "MEDIUM"
        assert len(result.thesis) > 20
        assert len(result.key_points) >= 3


def test_macro_agent_defaults_neutral_on_parse_failure():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response("Garbage output")

        agent = MacroAgent()
        result = agent.run(ticker="AAPL", context={})

        assert result.stance == "NEUTRAL"
        # _parse_output defaults to MEDIUM conviction when not found in output
        assert result.conviction in ("LOW", "MEDIUM")


@pytest.mark.parametrize("AgentClass,name", [
    (FundamentalAgent, "FUNDAMENTAL"),
    (TechnicalAgent, "TECHNICAL"),
    (SentimentAgent, "SENTIMENT"),
    (GeopoliticalAgent, "GEOPOLITICAL"),
    (AdversarialAgent, "ADVERSARIAL"),
])
def test_agent_returns_valid_output(AgentClass, name):
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(MOCK_RESPONSE)

        agent = AgentClass()
        result = agent.run(ticker="MSFT", context={"quality_percentile": 0.8})

        assert result.agent == name
        assert result.stance in ("BULL", "BEAR", "NEUTRAL")
        assert result.conviction in ("HIGH", "MEDIUM", "LOW")
        assert isinstance(result.key_points, list)
