from unittest.mock import MagicMock, patch
from nq_api.agents.macro import MacroAgent
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
        assert result.conviction == "LOW"
