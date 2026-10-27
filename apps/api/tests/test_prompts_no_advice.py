"""B5: free-text prompts must not steer the model toward buy/sell calls.

The structured verdict enum (STRONG BUY ... STRONG SELL) is an API contract the
UI maps to neutral bands, so it is not checked here. These tests cover the prose
instructions that reach users unmapped.
"""

import re

import pytest

from nq_api.agents.anjali_context import build_anjali_context
from nq_api.services import prompts

PROSE_PROMPTS = {
    "_SYSTEM": prompts._SYSTEM,
    "MORGAN_PERSONA": prompts.MORGAN_PERSONA,
    "MORGAN_STYLE_RULES": prompts.MORGAN_STYLE_RULES,
    "MARKET_WRAP_PROMPT": prompts.MARKET_WRAP_PROMPT,
    "MARKET_WRAP_PERSONALIZED_PROMPT": prompts.MARKET_WRAP_PERSONALIZED_PROMPT,
}

BANNED = [
    r"STRONG BUY zone",
    r"hard sell signal",
    r"No disclaimers",
    r"institutional-grade",
    r"recommend a stock with IRS < 30% as a buy",
]


@pytest.mark.parametrize("name", sorted(PROSE_PROMPTS))
def test_prose_prompts_have_no_advice_steering(name):
    text = PROSE_PROMPTS[name]
    for pat in BANNED:
        assert not re.search(pat, text, re.I), f"{name} contains {pat!r}"


def test_system_prompt_requires_not_advice_line():
    assert "Information only, not investment advice." in prompts._SYSTEM


@pytest.mark.parametrize(
    ("irs_pct", "expected"),
    [
        (80, "Upper research band"),
        (50, "Middle research band"),
        (35, "Lower research band"),
        (10, "Lower research band, weakest"),
    ],
)
def test_anjali_context_uses_research_bands(irs_pct, expected):
    ctx = build_anjali_context({"irs_pct": irs_pct})
    assert expected in ctx
    assert not re.search(r"\b(BUY|SELL|avoid)\b", ctx, re.I)
