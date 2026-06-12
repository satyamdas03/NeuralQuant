"""Clarification flow — regression tests.

The 2026-06-12 production crash ("name 're' is not defined") came from new
regex usage in _generate_clarification_questions with no import; nothing in
the suite executed the portfolio branch. These tests actually run it.
"""
from nq_api.services.clarification import (
    _generate_clarification_questions,
    _needs_clarification,
)


PORTFOLIO_Q = (
    "i want to invest 10 lakhs in the indian stock market and want to earn "
    "6 to 8% profit in the next 10 months, give me a solid plan"
)


def test_portfolio_intent_always_clarifies_even_with_specifics():
    assert _needs_clarification(PORTFOLIO_Q, [], "REACT", None) is True


def test_portfolio_questions_generate_without_error():
    qs = _generate_clarification_questions(PORTFOLIO_Q, [], "IN", "REACT")
    assert 2 <= len(qs) <= 3
    texts = " ".join(q.question for q in qs)
    # Return target and horizon were stated -- the gap-aware set must NOT
    # re-ask them, and must ask about deployment instead.
    assert "target return" not in texts.lower()
    assert "deploy" in texts.lower()


def test_vague_portfolio_question_asks_return_and_horizon():
    qs = _generate_clarification_questions(
        "build me a portfolio with 5 lakhs", [], "IN", "REACT"
    )
    texts = " ".join(q.question for q in qs).lower()
    assert "target return" in texts or "time horizon" in texts


def test_ticker_decision_question_generates():
    qs = _generate_clarification_questions(
        "should i buy TCS now?", ["TCS"], "IN", "REACT"
    )
    assert len(qs) >= 1
