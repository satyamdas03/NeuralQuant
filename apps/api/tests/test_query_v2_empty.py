"""Regression tests for F-03 and F-04: Ask AI v2 empty summary + prompt fences.

Before the fix, POST /query/v2 could return HTTP 200 with a blank summary.
The user question was also concatenated into the prompt with no length cap
and no structural fence.
"""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from nq_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_tool_response(tool_input: dict, text_block: str | None = None):
    """Build a minimal Anthropic-style response object for _extract_tool_use_input."""
    from nq_api.services.prompts import _STRUCTURED_TOOL

    class ToolBlock:
        type = "tool_use"
        name = _STRUCTURED_TOOL["name"]
        input = tool_input

    class TextBlock:
        type = "text"
        text = text_block or ""

    content = [ToolBlock]
    if text_block is not None:
        content.append(TextBlock)

    class Response:
        pass

    resp = Response()
    resp.content = content
    return resp


def _mock_context():
    """Patch the slow context-gathering helpers to return empty defaults."""
    return patch.multiple(
        "nq_api.routes.query",
        _fetch_enrichment=lambda t, m: {},
        _fetch_relevant_news=lambda q, t, n: [],
        _build_macro_context=lambda q, m, d: None,
        _enrich_with_platform_data=lambda q, m, t: None,
        _fetch_finnhub_news_summaries=lambda t, m, n: [],
        _detect_tickers_in_question=lambda q, m: ([], []),
    )


# Obviously fake, low-entropy placeholder. The route returns 200 "service
# unavailable" before the mocked LLM call when no key is set, so these tests
# need a key present; the LLM call itself is always mocked.
_DUMMY_KEY = "test-dummy-key"


def test_v2_blank_summary_returns_502(client, monkeypatch):
    """F-03: a structured response with empty summary must fail closed as 502."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", _DUMMY_KEY)
    tool_input = {
        "verdict": "HOLD",
        "confidence": 50,
        "timeframe": "Medium-term",
        "summary": "",  # blank
        "reasoning": {
            "why_this": "N/A",
            "why_not_alt": "N/A",
            "edge_summary": "N/A",
            "second_best": "N/A",
            "confidence_gap": "N/A",
        },
        "metrics": [],
        "scenarios": [],
        "follow_up_questions": [],
    }
    mock_response = _make_tool_response(tool_input)
    with _mock_context(), \
         patch("nq_api.routes.query._call_anthropic_with_retry", new=AsyncMock(return_value=mock_response)):
        resp = client.post("/query/v2", json={"question": "What do you think of AAPL?", "ticker": "AAPL"})
    assert resp.status_code == 502
    assert "NQ_QUERY_EMPTY_ANSWER" in resp.json()["detail"]


def test_v2_long_question_rejected(client):
    """F-04: question length is capped at 4000 chars at the API boundary."""
    long_q = "x" * 4001
    resp = client.post("/query/v2", json={"question": long_q})
    assert resp.status_code == 422


def test_v2_user_question_wrapped_in_fence(client, monkeypatch):
    """F-04: the user question is wrapped in <user-query> tags before the LLM."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", _DUMMY_KEY)
    captured = {}

    async def _capture_call(*args, **kwargs):
        captured["messages"] = kwargs.get("messages")
        # Return a minimal valid structured response so the endpoint succeeds
        return _make_tool_response({
            "verdict": "HOLD",
            "confidence": 50,
            "timeframe": "Medium-term",
            "summary": "AAPL looks fairly valued at the current price.",
            "reasoning": {
                "why_this": "Stable metrics",
                "why_not_alt": "No better alternative",
                "edge_summary": "Neutral",
                "second_best": "N/A",
                "confidence_gap": "N/A",
            },
            "metrics": [],
            "scenarios": [],
            "follow_up_questions": [],
        })

    with _mock_context(), \
         patch("nq_api.routes.query._call_anthropic_with_retry", new=_capture_call):
        resp = client.post("/query/v2", json={"question": "AUDITCANARY", "ticker": "AAPL"})
    assert resp.status_code == 200
    # Prompt injection canary must not appear in the final response summary
    assert "AUDITCANARY" not in resp.json().get("summary", "")
    # The question must be fenced in the prompt sent to the model
    messages = captured.get("messages", [])
    assert messages
    user_msg = messages[-1]["content"]
    assert "<user-query>" in user_msg
    assert "</user-query>" in user_msg
    assert "AUDITCANARY" in user_msg
