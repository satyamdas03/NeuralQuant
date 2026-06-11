"""Clarification question generation -- determines when and what to ask before answering."""
import logging
from datetime import date as _date, timedelta as _td

from nq_api.services.constants import (
    _CLARIFICATION_STOCK_KEYWORDS, _CLARIFICATION_SKIP_PATTERNS,
)
from nq_api.services.portfolio import _is_portfolio_intent
from nq_api.schemas import ClarificationQuestion, UserProfile

logger = logging.getLogger(__name__)


def _needs_clarification(
    question: str, detected_tickers: list[str], route: str, profile: UserProfile | None,
) -> bool:
    """Decide if the question needs clarification before answering.

    Returns True for ambiguous/vague questions that would benefit from context.
    Returns False for factual/direct questions with clear tickers.
    Portfolio intent WITHOUT profile -> ProfilerCard first, then may still clarify.
    """
    q = question.lower().strip()

    # Portfolio intent -- a real PM never allocates capital from one sentence.
    # Always ask before producing a plan; the saved profile and any specifics
    # in the question make the QUESTIONS smarter, they don't replace them.
    # (Callers pass clarification_answers on the second round, which skips
    # this entirely -- see query.py `and not req.clarification_answers`.)
    if _is_portfolio_intent(question):
        return True

    # Investment decision keywords ALWAYS need clarification (highest priority).
    # These override skip patterns -- "tell me about TCS, should I buy?" is
    # an investment question, not a factual lookup.
    _DECISION_KEYWORDS = [
        "should i buy", "should i sell", "should i hold", "should i invest",
        "is it a good time", "is it worth", "worth buying", "worth selling",
        "buy signal", "sell signal", "entry point", "exit point",
    ]
    if any(kw in q for kw in _DECISION_KEYWORDS):
        return True

    # Skip factual/direct questions with clear tickers
    if detected_tickers and any(p in q for p in _CLARIFICATION_SKIP_PATTERNS):
        return False
    # Direct factual queries even without tickers
    if any(p in q for p in _CLARIFICATION_SKIP_PATTERNS):
        return False

    # Ambiguous/vague questions that need context
    if any(kw in q for kw in _CLARIFICATION_STOCK_KEYWORDS):
        return True

    # Very short or vague questions without tickers
    if len(q) < 20 and not detected_tickers:
        return True

    return False


def _fetch_fmp_context_for_clarification(ticker: str, market: str) -> dict | None:
    """Fetch real-time FMP data to enrich clarification questions with live market context.
    Returns a dict with price, earnings date, analyst consensus, dividend yield, etc.
    """
    try:
        from nq_api.data_builder import _yf_symbol
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if not fmp._enabled:
            return None
        fmp_sym = _yf_symbol(ticker, market)
        ctx = {}

        # Price and basic metrics
        quote = fmp.get_quote(fmp_sym)
        if quote and quote.get("price"):
            ctx["price"] = quote["price"]
            ctx["change_pct"] = quote.get("change_pct")
            ctx["pe"] = quote.get("pe")
            ctx["market_cap"] = quote.get("market_cap")

        # Analyst consensus
        grades = fmp.get_analyst_grades(fmp_sym)
        if grades:
            ctx["analyst_consensus"] = grades.get("consensus")
            total = (grades.get("strong_buy") or 0) + (grades.get("buy") or 0) + \
                    (grades.get("hold") or 0) + (grades.get("sell") or 0) + (grades.get("strong_sell") or 0)
            if total > 0:
                ctx["analyst_buy_pct"] = round(
                    ((grades.get("strong_buy") or 0) + (grades.get("buy") or 0)) / total * 100, 1
                )

        # Analyst price target
        target = fmp.get_price_target(fmp_sym)
        if target and target.get("target_avg"):
            ctx["analyst_target"] = target["target_avg"]
            if target.get("target_high"):
                ctx["analyst_target_high"] = target["target_high"]
            if target.get("target_low"):
                ctx["analyst_target_low"] = target["target_low"]

        # Dividend yield
        divs = fmp.get_dividends(fmp_sym)
        if divs and isinstance(divs, list) and divs:
            ctx["dividend_yield"] = divs[0].get("yield_pct")
            ctx["last_dividend"] = divs[0].get("dividend")

        # Upcoming earnings
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        earnings = fmp.get_earnings_calendar(today.isoformat(), (today + _td(days=30)).isoformat())
        if earnings and isinstance(earnings, list):
            ticker_earnings = [
                e for e in earnings
                if e.get("ticker", "").upper() == ticker.upper()
                or e.get("ticker", "").upper() == fmp_sym.upper()
            ]
            if ticker_earnings:
                ctx["next_earnings_date"] = ticker_earnings[0].get("date")
                ctx["next_earnings_eps_est"] = ticker_earnings[0].get("eps_estimate")

        return ctx if ctx else None
    except Exception as exc:
        logger.debug("FMP context for clarification failed for %s: %s", ticker, exc)
        return None


def _generate_clarification_questions(
    question: str, detected_tickers: list[str], market: str, route: str,
    fmp_context: dict | None = None,
) -> list:
    """Generate 2-3 clarification questions based on the query type.
    fmp_context provides real-time market data for dynamic question generation."""
    q = question.lower()
    questions = []
    ctx = fmp_context or {}
    price = ctx.get("price")
    consensus = ctx.get("analyst_consensus", "").lower() if ctx.get("analyst_consensus") else None
    buy_pct = ctx.get("analyst_buy_pct")
    target = ctx.get("analyst_target")
    div_yield = ctx.get("dividend_yield")
    earnings_date = ctx.get("next_earnings_date")
    pe = ctx.get("pe")

    # Stock-specific questions with live data context
    if detected_tickers:
        ticker_label = detected_tickers[0]
        # Build context-aware prefix
        context_parts = []
        if price:
            cur = "Rs." if market == "IN" else "$"
            context_parts.append(f"currently at {cur}{price:,.2f}")
        if pe:
            context_parts.append(f"P/E {pe:.1f}x")
        if consensus:
            context_parts.append(f"analysts say {consensus}")
        if buy_pct and buy_pct > 60:
            context_parts.append(f"{buy_pct:.0f}% buy rating")
        if div_yield and div_yield > 0:
            context_parts.append(f"{div_yield:.1f}% dividend yield")
        if earnings_date:
            context_parts.append(f"earnings on {earnings_date}")

        ctx_str = f" ({'; '.join(context_parts)})" if context_parts else ""

        if any(kw in q for kw in ["should i buy", "is it worth", "should i invest"]):
            questions.append(ClarificationQuestion(
                question=f"What's your time horizon for {ticker_label}{ctx_str}?",
                options=["Short-term (< 3 months)", "Medium-term (3-12 months)", "Long-term (1+ years)"],
                question_type="time_horizon",
            ))
        if any(kw in q for kw in ["should i sell", "should i hold"]):
            questions.append(ClarificationQuestion(
                question=f"What's your basis (avg buy price) for {ticker_label}{ctx_str}?",
                options=["Above current price", "Near current price", "Below current price", "Not sure"],
                question_type="context",
            ))
        if any(kw in q for kw in ["dividend", "income", "yield"]):
            questions.append(ClarificationQuestion(
                question=f"Are you prioritizing dividend income or capital growth for {ticker_label}?",
                options=["Steady dividend income", "Balanced (dividends + growth)", "Pure capital growth"],
                question_type="investment_goal",
            ))
        questions.append(ClarificationQuestion(
            question="What's your risk tolerance?",
            options=["Conservative -- protect capital", "Balanced -- growth & stability", "Aggressive -- maximize returns"],
            question_type="risk_tolerance",
        ))

    # Portfolio-specific clarification questions.
    # Skip anything the user already stated -- a PM asks about the GAPS, not
    # what was just said ("10 lakhs, 6-8% in 10 months" answers return+horizon,
    # so ask about deployment style, liquidity, and concentration instead).
    elif _is_portfolio_intent(question):
        _stated_return = bool(re.search(r"\d+\s*(?:-|to)\s*\d+\s*%|\d+\s*%\s*(?:return|gain|profit)", q))
        _stated_horizon = bool(re.search(r"\d+\s*(?:month|year|week)", q))
        _stated_sector = any(s in q for s in ["sector", "bank", "pharma", "it ", "defence", "energy", "fmcg", "auto"])

        if not _stated_return:
            questions.append(ClarificationQuestion(
                question="What's your target return range for this portfolio?",
                options=["5-8% (conservative)", "8-12% (balanced)", "12-18% (aggressive)", "18%+ (high risk)"],
                question_type="investment_goal",
            ))
        if not _stated_horizon:
            questions.append(ClarificationQuestion(
                question="What's your investment time horizon?",
                options=["Under 6 months", "6-18 months", "1-3 years", "3+ years"],
                question_type="time_horizon",
            ))
        questions.append(ClarificationQuestion(
            question="How do you want to deploy the capital?",
            options=["Lumpsum now", "Staggered over 4-6 weeks (rupee-cost averaging)", "Half now, half on a market dip"],
            question_type="context",
        ))
        if not _stated_sector:
            questions.append(ClarificationQuestion(
                question="Which sectors do you want exposure to?",
                options=["Diversified across all sectors", "Financials & NBFCs", "Technology & IT", "Energy & Infrastructure", "Defence & Manufacturing"],
                question_type="sector_preference",
            ))
        questions.append(ClarificationQuestion(
            question="Could you need this money back early, and how would you handle a -10% month?",
            options=["Funds are locked in -- I'd hold through drawdowns", "Might need partial liquidity -- keep some in liquid funds", "Would likely exit on a -10% drawdown"],
            question_type="risk_tolerance",
        ))

    # General recommendation questions
    elif any(kw in q for kw in ["best stocks", "recommend", "suggest", "top picks", "which stock"]):
        questions.append(ClarificationQuestion(
            question="Which sector are you most interested in?",
            options=["Technology", "Healthcare", "Financial Services", "Energy", "No preference"],
            question_type="sector_preference",
        ))
        questions.append(ClarificationQuestion(
            question="What's your investment goal?",
            options=["Wealth building", "Retirement", "Passive income", "Tax saving"],
            question_type="investment_goal",
        ))

    # Catch-all for vague questions
    if len(questions) < 2:
        if not any(q2.question_type == "risk_tolerance" for q2 in questions):
            questions.append(ClarificationQuestion(
                question="What's your risk tolerance?",
                options=["Conservative -- protect capital", "Balanced -- growth & stability", "Aggressive -- maximize returns"],
                question_type="risk_tolerance",
            ))
        if not any(q2.question_type == "time_horizon" for q2 in questions):
            questions.append(ClarificationQuestion(
                question="What's your investment time horizon?",
                options=["Short-term (< 1 year)", "Medium-term (1-3 years)", "Long-term (3+ years)"],
                question_type="time_horizon",
            ))

    return questions[:3]
