"""Unit tests for Veronica pure logic — no livekit imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantastra.veronica_logic import (
    agent_kind_for_room,
    parse_page_context,
    build_narration_instructions,
    build_veronica_greeting,
)


class TestAgentKindForRoom:
    def test_veronica_room(self):
        assert agent_kind_for_room("veronica-abc-123") == "veronica"

    def test_quantastra_room(self):
        assert agent_kind_for_room("quantastra-abc-123") == "quantastra"

    def test_unknown_defaults_to_quantastra(self):
        assert agent_kind_for_room("random-room") == "quantastra"

    def test_none_defaults_to_quantastra(self):
        assert agent_kind_for_room(None) == "quantastra"


class TestParsePageContext:
    def test_valid_message(self):
        msg = {
            "type": "page_context",
            "route": "/stocks/NVDA",
            "pageType": "stock_detail",
            "ticker": "NVDA",
            "narrate": True,
        }
        ctx = parse_page_context(msg)
        assert ctx == {
            "route": "/stocks/NVDA",
            "page_type": "stock_detail",
            "ticker": "NVDA",
            "narrate": True,
            "key_data": None,
        }

    def test_missing_optional_fields(self):
        ctx = parse_page_context({"type": "page_context", "route": "/dashboard"})
        assert ctx["page_type"] == "page"
        assert ctx["ticker"] is None
        assert ctx["narrate"] is False

    def test_wrong_type_returns_none(self):
        assert parse_page_context({"type": "file_upload"}) is None

    def test_non_dict_returns_none(self):
        assert parse_page_context("garbage") is None


class TestBuildNarrationInstructions:
    def test_stock_page_mentions_ticker_and_brevity(self):
        text = build_narration_instructions(
            {"route": "/stocks/NVDA", "page_type": "stock_detail",
             "ticker": "NVDA", "narrate": True}
        )
        assert "NVDA" in text
        assert "10" in text or "fifteen" in text.lower() or "15" in text

    def test_generic_page(self):
        text = build_narration_instructions(
            {"route": "/portfolio", "page_type": "portfolio",
             "ticker": None, "narrate": True}
        )
        assert "portfolio" in text.lower()


class TestBuildVeronicaGreeting:
    def test_with_name(self):
        g = build_veronica_greeting("Satyam")
        assert "Veronica" in g

    def test_without_name(self):
        g = build_veronica_greeting(None)
        assert "Veronica" in g


def test_veronica_greeting_starts_hey_there_no_name():
    g = build_veronica_greeting("Satyam")
    assert g.startswith("Hey there")
    assert "Satyam" not in g


def test_veronica_greeting_anon_starts_hey_there():
    g = build_veronica_greeting(None)
    assert g.startswith("Hey there")


from quantastra.veronica_logic import parse_page_context


def test_parse_page_context_preserves_key_data():
    msg = {
        "type": "page_context",
        "route": "/stocks/TCS",
        "pageType": "stock_detail",
        "ticker": "TCS",
        "narrate": False,
        "keyData": {"price": 3500.0, "irs_pct": 78, "score": 1},
    }
    page = parse_page_context(msg)
    assert page is not None
    assert page["key_data"] == {"price": 3500.0, "irs_pct": 78, "score": 1}


def test_parse_page_context_key_data_defaults_none():
    msg = {"type": "page_context", "route": "/dashboard", "pageType": "dashboard"}
    page = parse_page_context(msg)
    assert page is not None
    assert page["key_data"] is None


def test_parse_page_context_key_data_must_be_dict():
    msg = {"type": "page_context", "route": "/x", "keyData": "not-a-dict"}
    page = parse_page_context(msg)
    assert page["key_data"] is None
