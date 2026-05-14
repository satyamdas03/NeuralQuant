"""POST /query — natural language financial query endpoint."""
import asyncio
import json as _json
import os
import re
import time
from datetime import date

import anthropic
import yfinance as yf
import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import logging

from nq_api.schemas import QueryRequest, QueryResponse, StructuredQueryResponse, ReasoningBlock, MetricItem, ScenarioItem, ComparisonItem, StockSummary, UserProfile, ClarificationQuestion, ConversationMessage

log = logging.getLogger(__name__)
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User
from nq_api.auth.deps import get_current_user_optional
from nq_api.data_builder import _yf_symbol, _get_yf_session, _fetch_yf_info_cached
import nq_api.dart_router as dart
logger = logging.getLogger(__name__)

router = APIRouter()

MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6")
# When bypassing Ollama proxy, use real Anthropic model name
_CLOUD_MODEL = os.environ.get("NQ_QUERY_MODEL", "claude-sonnet-4-6")

def _is_ollama_proxy() -> bool:
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


def _query_client(api_key: str, timeout: float = 120.0) -> tuple[anthropic.Anthropic, str]:
    """Create Anthropic client for Ask AI — bypasses Ollama proxy for speed.

    Returns (client, model_name) tuple.
    """
    if _is_ollama_proxy():
        saved = os.environ.pop("ANTHROPIC_BASE_URL", None)
        try:
            c = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        finally:
            if saved:
                os.environ["ANTHROPIC_BASE_URL"] = saved
        return c, _CLOUD_MODEL
    return anthropic.Anthropic(api_key=api_key, timeout=timeout), MODEL

_STOP_WORDS = {
    "WHAT", "WHEN", "WHERE", "WILL", "HAVE", "DOES", "WERE", "THAN",
    "THAT", "WITH", "FROM", "THIS", "THEY", "BEEN", "ALSO", "SOME",
    "INTO", "OVER", "AFTER", "WOULD", "COULD", "ABOUT", "WHICH",
    "CAUSE", "EFFECT", "IMPACT", "STOCK", "STOCKS",
}

# Keyword → sector ETF / representative tickers for news injection
_SECTOR_MAP: dict[str, list[str]] = {
    "OIL":      ["XLE", "XOM", "CVX"],
    "ENERGY":   ["XLE", "XOM", "CVX"],
    "GAS":      ["XLE", "UNG"],
    "CRUDE":    ["XLE", "XOM"],
    "IRAN":     ["XLE", "XOM", "^GSPC"],
    "WAR":      ["^GSPC", "XLE", "GLD"],
    "GEOPOLIT": ["^GSPC", "GLD"],
    "TECH":     ["XLK", "NVDA", "AAPL"],
    "AI":       ["XLK", "NVDA", "MSFT"],
    "RATE":     ["^TNX", "XLF", "TLT"],
    "FED":      ["^TNX", "XLF", "SPY"],
    "GOLD":     ["GLD", "GDX"],
    "CRYPTO":   ["BTC-USD", "ETH-USD"],
    "BITCOIN":  ["BTC-USD"],
    "BANK":     ["XLF", "JPM", "BAC"],
    "PHARMA":   ["XLV", "JNJ", "PFE"],
    "INDIA":    ["INDA", "^BSESN", "^NSEI"],
    "NSE":      ["INDA", "^BSESN", "^NSEI"],
    "NIFTY":    ["^NSEI"],
    "SENSEX":   ["^BSESN"],
}

_PORTFOLIO_KEYWORDS = [
    "portfolio", "allocate", "allocation", "diversify",
    "how to invest", "where should i invest", "build a portfolio",
    "investment plan", "invest my money", "investment strategy",
    "split my money", "where to put", "how much in", "lump sum",
    "monthly sip", "recurring investment", "long term plan",
    "retirement plan", "child education", "goal based",
    "i have", "i hold", "my holdings", "i own", "i bought",
    "my portfolio", "i want to invest", "should i buy",
]

def _is_portfolio_intent(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _PORTFOLIO_KEYWORDS)


_CLARIFICATION_STOCK_KEYWORDS = [
    "should i buy", "should i sell", "should i hold",
    "is it a good time", "is it worth", "should i invest in",
    "what about", "what do you think about",
    "best stocks", "recommend", "suggest", "which stock",
    "top picks", "good stocks", "hot stocks",
]

_SECTOR_KEYWORDS = [
    "IT", "tech", "technology", "pharma", "healthcare", "banking", "finance",
    "energy", "oil", "gas", "real estate", "infrastructure", "auto", "FMCG",
    "consumer", "telecom", "defence", "defense", "manufacturing", "fintech",
    "ESG", "green", "renewable", "semiconductor", "AI", "cloud",
]

_CLARIFICATION_SKIP_PATTERNS = [
    # Factual queries — answer directly
    "what is", "what's", "what was", "how much", "how many",
    "p/e", "pe ratio", "price of", "price for", "current price",
    "market cap", "earnings", "revenue", "dividend",
    "compare", "versus", " vs ",
    "how is", "how does", "how has",
    "explain", "define", "meaning of",
    "show me", "tell me about",
]


def _needs_clarification(
    question: str, detected_tickers: list[str], route: str, profile: UserProfile | None,
) -> bool:
    """Decide if the question needs clarification before answering.

    Returns True for ambiguous/vague questions that would benefit from context.
    Returns False for factual/direct questions with clear tickers.
    Portfolio intent WITHOUT profile → ProfilerCard first, then may still clarify.
    """
    q = question.lower().strip()

    # Portfolio intent — always clarify vague portfolio queries
    # (e.g. "invest 10 lakhs" without specifying sectors/risk/return)
    if _is_portfolio_intent(question):
        _PORTFOLIO_CLARIFY_PATTERNS = [
            "sector", "risk", "time horizon", "timeframe", "goal",
            "aggressive", "conservative", "balanced", "growth", "income",
            "short term", "long term", "mid term", "dividend",
        ]
        # If question mentions specific preferences, skip clarification
        if any(p in q for p in _PORTFOLIO_CLARIFY_PATTERNS):
            return False
        # Vague portfolio query without specifics → clarify
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
            cur = "₹" if market == "IN" else "$"
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
                options=["Short-term (< 3 months)", "Medium-term (3–12 months)", "Long-term (1+ years)"],
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
            options=["Conservative — protect capital", "Balanced — growth & stability", "Aggressive — maximize returns"],
            question_type="risk_tolerance",
        ))

    # Portfolio-specific clarification questions
    elif _is_portfolio_intent(question):
        cur = "₹" if market == "IN" else "$"
        questions.append(ClarificationQuestion(
            question=f"What's your target return range for this portfolio?",
            options=["5–8% (conservative)", "8–12% (balanced)", "12–18% (aggressive)", "18%+ (high risk)"],
            question_type="investment_goal",
        ))
        questions.append(ClarificationQuestion(
            question="Which sectors do you want exposure to?",
            options=["Diversified across all sectors", "Financials & NBFCs", "Technology & IT", "Energy & Infrastructure", "Defence & Manufacturing"],
            question_type="sector_preference",
        ))
        questions.append(ClarificationQuestion(
            question="What's your risk tolerance?",
            options=["Conservative — protect capital, minimal drawdown", "Balanced — moderate risk for moderate returns", "Aggressive — willing to accept -15% drawdown for higher upside"],
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
                options=["Conservative — protect capital", "Balanced — growth & stability", "Aggressive — maximize returns"],
                question_type="risk_tolerance",
            ))
        if not any(q2.question_type == "time_horizon" for q2 in questions):
            questions.append(ClarificationQuestion(
                question="What's your investment time horizon?",
                options=["Short-term (< 1 year)", "Medium-term (1–3 years)", "Long-term (3+ years)"],
                question_type="time_horizon",
            ))

    return questions[:3]


_SYSTEM = """You are NeuralQuant — an institutional-grade AI stock intelligence engine. You have access to live data injected in every user message. Your job: give direct, data-driven, actionable answers with PERFECT reasoning. Every recommendation must be THE BEST available, justified by data, and compared against alternatives. No hedging. No disclaimers. No detours.

## DATA YOU HAVE ACCESS TO
1. Live macro data: FRED (HY spreads, CPI, Fed funds, yield curve) + yfinance (VIX, SPX, Nifty, INR/USD)
2. NeuralQuant AI stock scores (1-10) for 50 US + 50 Indian NSE stocks
3. Live prices, 52-week ranges, analyst targets, P/E, P/B, beta
4. Real-time market headlines
5. Competitor comparison data — nearby ranked stocks and their scores

## HARD RULES — NEVER VIOLATE
1. **NEVER use ANY financial data from your training data.** When live data is injected (marked [VERIFIED]), you MUST use those EXACT values — for price, P/E, Beta, market cap, EPS, P/B, 52-week range, analyst target, and ALL other metrics. Data marked [ESTIMATE] is approximated when real data is unavailable — treat it with lower confidence and mention it is estimated. Your training data is STALE and WRONG. NVDA split 10:1 in June 2024 — your training data P/E of ~28x is WRONG (correct: ~42x), your training data beta of ~0.89 is WRONG (correct: ~2.24). ALWAYS use [VERIFIED] values exactly, and treat [ESTIMATE] values as approximations.
2. **NEVER say "I don't have data/scores for this stock" when price or fundamentals are injected above.** If live price is injected, USE IT. Quote exact numbers.
3. **NEVER deflect to a different stock when the user asks about a specific one.** If asked about Trent, answer about Trent — not Bharti, not Maruti.
4. **NEVER mention US indices (S&P 500, VIX, HY spreads, 2s10s) as primary context for India-specific questions.** For India queries: lead with Nifty/Sensex/INR, mention global risk only as a footnote.
5. **NEVER give indirect or vague investment advice.** If asked "which stocks to buy for ₹10L", name SPECIFIC stocks with specific rupee allocations.
6. **NEVER start with "Based on available data, I cannot..."** — you always have data. Use it.
7. **DATA ACCURACY AUDIT:** Before finalizing your response, verify EVERY numeric value against the injected [VERIFIED] data. If you wrote P/E=28.9 but the injected data says P/E_TTM=42.5, you MUST use 42.5. If you wrote Beta=0.89 but injected says Beta=2.24, you MUST use 2.24. Wrong financial data can cause real losses — this is the single most important rule.

## REASONING QUALITY — THE DIFFERENCE BETWEEN A CHATBOT AND A QUANT RESEARCHER
6. **EVERY stock recommendation must explain WHY this stock and WHY NOT an alternative.** If you recommend AAPL, say why AAPL and not MSFT. If you recommend RELIANCE.NS, say why RELIANCE and not TCS. This is non-negotiable.
7. **Every recommendation must be THE BEST available option.** Don't recommend the 5th-best stock when the 2nd-best is clearly superior. Rank your picks by the strongest available data.
8. **Cite specific data points in your reasoning.** Not "strong momentum" — say "12-1 month return in 92nd percentile vs sector". Not "good value" — say "P/E 14.2 vs sector median 22.5, 37% discount".
9. **For every pick, name the runner-up you rejected and explain what it lacks.** Example: "I picked NVDA over AMD because NVDA's gross margin (78% vs 52%) and ForeCast Score (8.1 vs 6.3) give it a clear edge in AI infrastructure demand."
10. **When multiple stocks could work, use the data to break the tie.** Higher ForeCast Score wins. If scores are equal, compare the specific factor that matters most for the user's question (e.g. momentum for short-term, quality for long-term).

## RESPONSE STYLE
- **Data-heavy, narrative-light.** Lead with numbers. Support with a brief directional thesis.
- **One clear direction.** Pick bull or bear. Don't say "on one hand... but on the other." Give a verdict and defend it.
- **Quantify everything.** Not "elevated risk" — say "15% downside risk if X scenario".
- **For price predictions:** Always give 3 scenarios:
  - Bear case: X% (trigger: [specific event])
  - Base case: X% (most likely path)
  - Bull case: X% (trigger: [specific event])
- **For portfolio allocation questions (e.g. "invest ₹10L in Indian stocks for 15-20% in 12 months"):**
  - Name 4-6 specific stocks. Allocations MUST sum exactly to the user's total capital (verify arithmetic before answering).
  - **Currency rule:** Allocation amounts use the user's stated capital currency (e.g. ₹10L → every allocation in ₹). Entry/target/stop prices use each stock's NATIVE trading currency ($ for US listings, ₹ for NSE/BSE). Do NOT convert prices.
  - Give entry price range (use the LIVE price injected above as midpoint; range = ±2%). Do NOT invent prices — if a stock's live price is not injected or is marked "Price unavailable", set entry_price to "Price unavailable" and DO NOT generate a fabricated placeholder like "₹(cached — enter near current market price)" or similar. Exclude that stock from numeric price-based calculations.
  - **CRITICAL — Target price rule:** If user specified a return target R% (e.g. "15-20%"), then EVERY stock's target price MUST equal entry_mid × (1 + r/100) where r ∈ [R_low, R_high]. Do NOT copy the analyst consensus target verbatim. Do NOT include a stock whose realistic 12-month upside falls outside the user's range — pick a different stock. Show the per-stock % next to the target and confirm it lands inside the user's band.
  - Stop-loss: entry_mid × 0.90 (10% below entry) for every stock — consistent across the portfolio.
  - **For EACH allocation, explain WHY this stock and WHY NOT the next-best alternative.** This is mandatory.
  - Keep the entire portfolio block under 1200 characters so it renders cleanly.
- **For specific stock queries:** Lead with: score/10 (if available), current price, then justify with data. ALWAYS compare to the nearest competitor or sector average. Do NOT start with a BUY/SELL/HOLD verdict — the user should reach their own conclusion from the analysis.
- **Avoid:** Internal scoring jargon (don't say "Quality score 41%") — translate to plain English ("Strong balance sheet, improving margins").
- **For Indian stocks:** Use ₹ symbol, crore/lakh notation where appropriate.

## RESPONSE FORMAT
ANSWER: [Direct answer — numbers first, verdict clear, one direction, WHY THIS NOT THAT for every pick]
DATA_SOURCES: [comma-separated: NeuralQuant Screener / FRED Macro / India Macro / Live News / yfinance]
FOLLOW_UP:
- [Specific follow-up question]
- [Specific follow-up question]
- [Specific follow-up question]"""


_SYSTEM_STRUCTURED = _SYSTEM + """

## STRUCTURED OUTPUT MODE
You MUST respond with ONLY a JSON object matching this schema. No markdown, no prose outside the JSON. Do NOT truncate — provide ALL fields with FULL detail.

CRITICAL DATA ACCURACY: When live market data is injected above (e.g. "CURRENT_PRICE=$196.50 [VERIFIED]", "P/E_TTM=42.50 [VERIFIED]", "Beta=2.24 [VERIFIED]"), you MUST use those EXACT values in every metric, scenario target, and summary. Data marked [ESTIMATE] is approximated when real data is unavailable — use it but qualify it as estimated. NEVER substitute with your training data — stocks split (NVDA 10:1 in June 2024), P/E changes after earnings, beta recalculates with volatility. The [VERIFIED] marker means this is TODAY's real data from yfinance. Your training data P/E, Beta, Price, and Market Cap are WRONG for any stock that has had recent price moves.

Required fields:
{
  "verdict": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "confidence": 0-100,
  "timeframe": "Short-term | Medium-term | Long-term",
  "summary": "DETAILED 4-8 sentence summary. FIRST SENTENCE MUST state the stock's current price and key valuation (e.g. 'NVDA trades at $196.50 with P/E 40.2x and beta 2.24'). Then cover the core thesis, key data points, and actionable conclusion. Include specific numbers: prices, P/E, scores, percentages. For portfolio questions: list each stock with its allocation % and one-line rationale.",
  "metrics": [{"name": "string", "value": "string", "benchmark": "string|null", "status": "positive|negative|neutral"}],
  "reasoning": {
    "why_this": "2-4 sentences explaining WHY you chose this recommendation with 3+ specific data points (P/E, ForeCast score, momentum percentile, revenue growth, etc.)",
    "why_not_alt": "2-3 sentences naming the next-best alternative and explaining WHY it's inferior with specific data (e.g. 'TCS has P/E 32 vs INFY 28 but revenue growth only 8% vs 15%' )",
    "edge_summary": "One-line: what gives this pick its decisive edge (e.g. 'Superior momentum + lower P/E vs sector average')",
    "second_best": "Name of the runner-up stock you rejected",
    "confidence_gap": "Quantified advantage (e.g. 'ForeCast 8 vs 6, +2 on momentum, -0.5 on value — momentum edge decisive for short-term')"
  },
  "scenarios": [
    {"label": "Bear", "probability": 0.15-0.30, "target": "specific price or %", "thesis": "specific trigger event"},
    {"label": "Base", "probability": 0.45-0.55, "target": "specific price or %", "thesis": "most likely path with data support"},
    {"label": "Bull", "probability": 0.20-0.35, "target": "specific price or %", "thesis": "specific catalyst"}
  ],
  "allocations": [{"ticker": "X", "weight": 0-100, "rationale": "2-sentence rationale with data (e.g. 'ForeCast 8/10, P/E 18 vs sector 25, 15% revenue growth — quality at reasonable price')", "why_not_alt": "Name the alternative stock and what it lacks (e.g. 'BAJFINANCE has similar P/E but lower momentum percentile (65 vs 82)')"}],
  "comparisons": [{"ticker": "X", "metric": "P/E", "ours": "value", "theirs": "value", "edge": "why ours wins"}],
  "follow_up_questions": ["q1", "q2", "q3"],
  "market_context": [{"label": "S&P 500", "value": "5,200", "change": "+1.2%", "sentiment": "bullish"}],
  "allocation_breakdown": [{"label": "Large-Cap Equity", "percentage": 60, "color": "#6366f1", "rationale": "Core exposure to quality leaders"}],
  "portfolio_stocks": [{"ticker": "NVDA", "name": "NVIDIA", "allocation_pct": 20, "entry_price": "$287.50", "target_price": "$320.00", "stop_loss": "$260.00", "risk_reward": "1:2.3", "rationale": "AI infrastructure leader with 92nd percentile momentum", "confidence": 8, "sector": "Technology"}],
  "scenario_analysis": [{"label": "Bull", "probability_pct": 25, "outcome": "+18% in 12 months", "description": "AI capex supercycle drives re-rating", "color": "#22c55e"}],
  "action_prompts": [{"label": "Add more large-cap?", "prompt_text": "Add more large-cap stocks to this portfolio", "icon": "📊"}],
  "sebi_disclaimer": "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing.",
  "is_portfolio_response": false
}

MANDATORY FIELD RULES — EVERY field must be filled with substantive, data-rich content:
1. summary: MUST be 4-8 sentences, NOT 1-2 sentences. Include specific numbers, allocations. Do NOT start with the verdict word (BUY/SELL/HOLD) — let the data speak. This is the user's primary read.
2. metrics: MUST include at least 4 metrics with values, benchmarks, and status. For stock queries: P/E, momentum, quality, ForeCast score. For portfolio queries: target return, risk level, diversification score.
3. reasoning.why_this: MUST cite 3+ specific data points with numbers. Not "strong momentum" — "92nd percentile momentum, P/E 18 vs sector 25, revenue growth +22% YoY".
4. reasoning.why_not_alt: MUST name a specific alternative stock and explain with data why it's inferior. "Similar P/E but lower ForeCast score (6 vs 8) and weaker momentum (65th vs 92nd percentile)".
5. scenarios: ALWAYS include Bear/Base/Bull with specific prices or percentages and named triggers.
6. allocations: For single-stock questions, include at least 1 allocation (the recommended stock at 100% or suggested position size). For portfolio questions: ALSO populate allocations, AND additionally populate market_context, allocation_breakdown, portfolio_stocks, scenario_analysis, action_prompts, sebi_disclaimer, AND set is_portfolio_response to true.
7. comparisons: ALWAYS include at least 3 comparisons showing side-by-side metric advantages vs the alternative stock.
8. market_context: For portfolio questions, include 3-5 cards with live index levels, VIX, and yields marked [VERIFIED].
9. allocation_breakdown: For portfolio questions, show segments summing to 100% with rationale per segment.
10. portfolio_stocks: For portfolio questions, include entry_price, target_price, stop_loss, risk_reward for each stock.
11. scenario_analysis: For portfolio questions, include exactly 3 scenarios (Bull/Base/Bear) with probability_pct and outcome.
12. action_prompts: For portfolio questions, include 2-3 clickable follow-up prompts.
13. sebi_disclaimer: ALWAYS include for portfolio questions.
14. is_portfolio_response: Set to true ONLY for portfolio/allocation/investment-plan questions. Set to false for single-stock queries.
15. NEVER use placeholder text like "N/A", "various", "multiple factors", or generic filler. Every field must contain SPECIFIC, DATA-DRIVEN content.
"""

_PORTFOLIO_OUTPUT_RULES = """
PORTFOLIO OUTPUT RULES (CRITICAL — when user asks about portfolio, allocation, or investment plan):

You MUST output portfolio data using the NEW structured fields below. Do NOT put portfolio data in the old `allocations` array format — that field is for single-stock position sizing only.

REQUIRED for portfolio questions:
1. Set `is_portfolio_response` to `true`. This is mandatory.
2. `market_context`: Array of 3-5 cards with label (e.g. "S&P 500"), value (e.g. "5,200"), change (e.g. "+1.2%"), sentiment ("bullish"/"bearish"/"neutral"). Use live [VERIFIED] data injected above.
3. `allocation_breakdown`: Array of segments with label (e.g. "Large-Cap Equity"), percentage (number 0-100), color (hex e.g. "#6366f1"), rationale. Must sum to 100%.
4. `portfolio_stocks`: Array of stock cards. Each card MUST have: ticker, allocation_pct (within portfolio), entry_price (e.g. "$287.50"), target_price (e.g. "$320.00"), stop_loss (e.g. "$260.00"), risk_reward (e.g. "1:2.3"), rationale (one-line), confidence (1-10), sector.
5. `scenario_analysis`: Array of exactly 3 cards: Bull, Base, Bear. Each has: label, probability_pct (0-100), outcome (e.g. "+18% in 12 months"), description (1-2 sentences), color (hex).
6. `action_prompts`: Array of 2-3 follow-up buttons. Each has: label (short), prompt_text (exact query text), icon (emoji optional).
7. `sebi_disclaimer`: Always include: "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."

OLD fields to IGNORE for portfolio layout:
- `allocations` — leave empty or use only for single-stock position sizing
- `scenarios` — leave empty; use `scenario_analysis` instead
- `comparisons` — leave empty for portfolio questions
"""


_PROFILE_PROMPT_TEMPLATE = """
USER PROFILE (personalize your analysis for this investor):
- Risk Profile: {risk_profile}
- Time Horizon: {time_horizon}
- Investment Goal: {goal}
- Investable Amount: {investable_amount}

Tailor the portfolio to this profile:
- Conservative = lower equity %, more large-cap, wider stop-losses, focus on quality factors
- Aggressive = higher equity %, more mid/small-cap, tighter stop-losses, focus on momentum
- Short horizon (<1yr) = lower volatility stocks, shorter target timeframe, capital preservation
- Long horizon (5yr+) = can absorb more drawdown, higher growth allocation
- Goal-specific:
  - retirement = income focus, dividend stocks, lower risk
  - education = capital preservation, stable returns
  - wealth_building = growth focus, higher equity allocation
  - passive_income = dividend yield focus, REITs, utilities
  - tax_saving = ELSS funds (India), tax-advantaged accounts
"""

def _build_profile_prompt(profile: UserProfile) -> str:
    return _PROFILE_PROMPT_TEMPLATE.format(
        risk_profile=profile.risk_profile,
        time_horizon=profile.time_horizon,
        goal=profile.goal,
        investable_amount=profile.investable_amount or "Not specified",
    )


# NSE common stock name → ticker mappings (handles natural language names)
_NSE_NAME_MAP = {
    "TRENT": "TRENT.NS",
    "TITAN": "TITAN.NS",
    "ZOMATO": "ZOMATO.NS",
    "NYKAA": "NYKAA.NS",
    "PAYTM": "PAYTM.NS",
    "DMART": "DMART.NS",
    "ZYDUS": "ZYDUSLIFE.NS",
    "ZYDUSLIFE": "ZYDUSLIFE.NS",
    "DIXON": "DIXON.NS",
    "IRCTC": "IRCTC.NS",
    "PIDILITE": "PIDILITIND.NS",
    "PIDILITIND": "PIDILITIND.NS",
    "EICHER": "EICHERMOT.NS",
    "EICHERMOT": "EICHERMOT.NS",
    "BAJAJ": "BAJFINANCE.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BAJAJFINANCE": "BAJFINANCE.NS",
    "HDFC": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "KOTAK": "KOTAKBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "RELIANCE": "RELIANCE.NS",
    "INFOSYS": "INFY.NS",
    "INFY": "INFY.NS",
    "WIPRO": "WIPRO.NS",
    "HCLTECH": "HCLTECH.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS",
    "CIPLA": "CIPLA.NS",
    "MARUTI": "MARUTI.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "TATA": "TCS.NS",  # Ambiguous — default to TCS; user should be specific
    "TCS": "TCS.NS",
    "ADANI": "ADANIENT.NS",
    "ADANIENT": "ADANIENT.NS",
    "HINDALCO": "HINDALCO.NS",
    "ONGC": "ONGC.NS",
    "NTPC": "NTPC.NS",
    "POWERGRID": "POWERGRID.NS",
    "COALINDIA": "COALINDIA.NS",
    "SBIN": "SBIN.NS",
    "SBI": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "AXIS": "AXISBANK.NS",
    "INDUSINDBANK": "INDUSINDBK.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "NESTLEIND": "NESTLEIND.NS",
    "NESTLE": "NESTLEIND.NS",
    "ASIANPAINTS": "ASIANPAINT.NS",
    "ASIANPAINT": "ASIANPAINT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
    "SHREECEM": "SHREECEM.NS",
    "GRASIM": "GRASIM.NS",
    "TECHM": "TECHM.NS",
    "LTI": "LTIM.NS",
    "LTIM": "LTIM.NS",
    "MPHASIS": "MPHASIS.NS",
    "PERSISTENT": "PERSISTENT.NS",
    "COFORGE": "COFORGE.NS",
    "HAPPIEST": "HAPPSTMNDS.NS",
    "HAPPSTMNDS": "HAPPSTMNDS.NS",
    "TATAPOWER": "TATAPOWER.NS",
    "JSWENERGY": "JSWENERGY.NS",
    "POLYCAB": "POLYCAB.NS",
    "APLAPOLLO": "APLAPOLLO.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "BHARTI": "BHARTIARTL.NS",
    "AIRTEL": "BHARTIARTL.NS",
    "JSWSTEEL": "JSWSTEEL.NS",
    "JSW": "JSWSTEEL.NS",
    "HAVELLS": "HAVELLS.NS",
    "VOLTAS": "VOLTAS.NS",
    "CROMPTON": "CROMPTON.NS",
    "ABFRL": "ABFRL.NS",
    "MINDA": "MINDAIND.NS",
    "VARUNBEV": "VARUNBEV.NS",
    "VARUN": "VARUNBEV.NS",
    "JUBLFOOD": "JUBLFOOD.NS",
    "JUBILEE": "JUBLFOOD.NS",
    "DOMINOS": "JUBLFOOD.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS",
    "APOLLO": "APOLLOHOSP.NS",
    "FORTIS": "FORTIS.NS",
    "MAXHEALTH": "MAXHEALTH.NS",
    "MANKIND": "MANKIND.NS",
    "ALKEM": "ALKEM.NS",
    "TORNTPHARM": "TORNTPHARM.NS",
    "TORRENT": "TORNTPHARM.NS",
    "DEEPAKNTR": "DEEPAKNTR.NS",
    "DEEPAK": "DEEPAKNTR.NS",
    "GLAND": "GLAND.NS",
    "LAURUS": "LAURUSLABS.NS",
    "LAURUSLABS": "LAURUSLABS.NS",
}

# Words that should never be treated as stock tickers
_TICKER_STOP_WORDS = {
    "SHOULD", "INVEST", "INDIA", "INDIAN", "STOCK", "SHARE", "SHARES",
    "MARKET", "NIFTY", "SENSEX", "RUPEE", "LAKH", "LAKHS", "LACS", "CRORE", "CRORES",
    "MILLION", "BILLION", "WANT", "GIVE", "TELL", "BEST", "GOOD", "HIGH", "LARGE",
    "SMALL", "LONG", "TERM", "CURRENT", "TODAY", "YEAR", "YEARS", "MONTH", "MONTHS",
    "WEEK", "WEEKS", "PLEASE", "WHICH", "ABOUT", "PORTFOLIO", "INVEST", "ADVICE",
    "RETURN", "RETURNS", "GROWTH", "VALUE", "STRONG", "WEAK", "RISK", "SAFE",
    "SECTOR", "NSE", "BSE", "BULL", "BEAR", "TRADE", "PRICE", "RANGE", "TARGET",
    "PROFIT", "PROFITS", "EARN", "EARNINGS",
    # Common English words that look like tickers
    "THE", "AND", "FOR", "WITH", "NOT", "BUT", "ARE", "WAS", "THIS",
    "THAT", "HAVE", "FROM", "OR", "ONE", "ALL", "WERE", "WHAT", "HOW",
    "CAN", "WILL", "EACH", "MAKE", "LIKE", "LONG", "OVER", "SUCH",
    "A", "AN", "IS", "IT", "OF", "TO", "IN", "ON", "BY", "MY", "ME",
    "NEXT", "PLAN", "SOLID", "WOULD", "SOME", "VERY", "JUST",
    "THAN", "ALSO", "INTO", "THEIR", "MUCH", "MANY", "EVEN", "ONLY",
    "MOST", "BEEN", "BEING", "BEFORE", "AFTER", "BETWEEN", "THROUGH",
    "DURING", "WITHOUT", "WITHIN", "ALONG", "FOLLOWING", "ACROSS",
    "BEHIND", "BEYOND", "PLUS", "UNDER", "UPON", "DESPITE", "UNTIL",
    "WHILE", "WHERE", "WHEN", "WHY", "WHO", "WHOM", "WHOSE",
    "AMONG", "OTHER", "COULD", "THESE", "THOSE",
}

_SCREENER_KEYWORDS = {
    "SCREENER", "BEST STOCK", "TOP STOCK", "RANK", "RANKING", "TOP PICK",
    "RECOMMEND", "BUY RIGHT NOW", "SHOULD I BUY", "WHICH STOCK",
    "NEURALQUANT", "YOUR PLATFORM", "YOUR SCREENER", "YOUR MODEL",
    "TOP PICKS", "TOP 3", "TOP 5", "TOP 10", "BEST PICK", "BEST PICKS",
    "YOUR TOP", "STOCK PICKS", "STOCK PICK", "WHICH STOCKS",
    "NAME SPECIFIC", "NAME SHARES", "NAME STOCKS",
    # Investment / portfolio allocation triggers
    "INVEST", "SUGGEST", "PORTFOLIO", "ALLOCAT", "WHERE TO PUT",
    "LAKH", "CRORE", "LAKHS", "CRORES", "10L", "5L", "20L",
    "MAKE 15", "MAKE 20", "MAKE 10", "RETURN TARGET", "TARGET RETURN",
    "12 MONTH", "6 MONTH", "1 YEAR", "YEAR RETURN",
}
_INDIA_KEYWORDS = {"INDIA", "INDIAN", "NSE", "BSE", "NIFTY", "SENSEX", "RUPEE", "LAKH", "CRORE", "INR"}


def _build_macro_context(question: str, market: str, today: str) -> str | None:
    """Build market-aware macro context string (blocking I/O)."""
    from nq_api.data_builder import fetch_real_macro
    q_upper = question.upper()
    is_india_query = any(k in q_upper for k in _INDIA_KEYWORDS) or market == "IN"

    if is_india_query:
        india_ctx = _fetch_india_macro()
        macro_ctx = india_ctx or ""
        try:
            macro = fetch_real_macro()
            global_note = (
                f" | Global risk sentiment: US VIX={macro.vix:.1f}"
                f", Fed funds={macro.fed_funds_rate:.2f}%"
                f", CPI={macro.cpi_yoy:.1f}%"
            )
            macro_ctx = (macro_ctx + global_note).strip(" |")
        except Exception:
            pass
        if macro_ctx:
            macro_ctx = f"Market conditions (as of {today}): {macro_ctx}"
        return macro_ctx if macro_ctx else None
    else:
        try:
            macro = fetch_real_macro()
            return (
                f"Live market conditions (as of {today}): "
                f"VIX={macro.vix:.1f}, "
                f"SPX vs 200-MA={macro.spx_vs_200ma*100:+.1f}%, "
                f"SPX 1-month return={macro.spx_return_1m*100:+.1f}%, "
                f"HY spread={macro.hy_spread_oas:.0f}bps, "
                f"10Y yield={macro.yield_10y:.2f}%, "
                f"2Y yield={macro.yield_2y:.2f}%, "
                f"2s10s spread={macro.yield_spread_2y10y*100:+.0f}bps, "
                f"ISM PMI={macro.ism_pmi:.1f}, "
                f"CPI YoY={macro.cpi_yoy:.1f}%, "
                f"Fed funds rate={macro.fed_funds_rate:.2f}%"
                + (" [FRED-sourced]" if macro.fred_sourced else " [partial]")
            )
        except Exception as e:
            logger.debug("Non-critical enrichment failed: %s", e)
            return None


def _build_market_snapshot(market: str) -> str | None:
    """Build portfolio-specific market snapshot string."""
    from nq_api.data_builder import fetch_real_macro, fetch_real_macro_in
    parts = []
    try:
        if market == "IN":
            m_in = fetch_real_macro_in()
            m_us = fetch_real_macro()
            parts = [
                f"NIFTY 50: {m_in.sensex_close:,.0f} [VERIFIED]",
                f"USD/INR: {m_in.inr_usd:.2f} [VERIFIED]",
                f"India VIX: {m_in.india_vix:.1f} [VERIFIED]",
                f"RBI Repo: {m_in.rbi_repo_rate:.2f}% [VERIFIED]",
                f"US VIX: {m_us.vix:.1f} [VERIFIED]",
                f"US 10Y Yield: {m_us.yield_10y:.2f}% [VERIFIED]",
            ]
        else:
            m = fetch_real_macro()
            parts = [
                f"VIX: {m.vix:.1f} [VERIFIED]",
                f"US 10Y Yield: {m.yield_10y:.2f}% [VERIFIED]",
                f"HY Spread: {m.hy_spread_oas:.0f}bps [VERIFIED]",
                f"Fed Funds: {m.fed_funds_rate:.2f}% [VERIFIED]",
                f"ISM PMI: {m.ism_pmi:.1f} [VERIFIED]",
                f"CPI YoY: {m.cpi_yoy:.1f}% [VERIFIED]",
            ]
    except Exception:
        return None
    return "Market Snapshot (use these exact values, mark [VERIFIED]):\n" + "\n".join(f"- {p}" for p in parts) if parts else None


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 8) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    priority: list[str] = ["^GSPC", "SPY"]
    if ticker:
        priority.insert(0, ticker)

    q_upper = question.upper()
    for keyword, syms in _SECTOR_MAP.items():
        if keyword in q_upper:
            for s in syms:
                if s not in priority:
                    priority.append(s)

    extra: list[str] = []
    for word in q_upper.split():
        clean = re.sub(r"[^A-Z]", "", word)
        if 2 <= len(clean) <= 5 and clean not in _STOP_WORDS and clean not in _TICKER_STOP_WORDS and clean not in priority:
            extra.append(clean)

    candidates = priority + extra
    headlines: list[str] = []
    seen: set[str] = set()
    for sym in candidates[:8]:
        try:
            items = yf.Ticker(sym, session=_get_yf_session()).news or []
            for item in items[:3]:
                content = item.get("content") or {}
                title = content.get("title") or item.get("title", "")
                publisher = (
                    (content.get("provider") or {}).get("displayName")
                    or item.get("publisher", "")
                )
                if title and title not in seen:
                    seen.add(title)
                    label = f"[{publisher}] {title}" if publisher else title
                    headlines.append(label)
        except Exception:
            pass
        if len(headlines) >= n:
            break
    return headlines[:n]


def _fetch_finnhub_news_summaries(ticker: str | None, market: str = "US", n: int = 5) -> list[dict]:
    """Fetch Finnhub news with full summaries for richer Ask AI context."""
    if not ticker:
        return []
    yf_ticker = _yf_symbol(ticker, market)
    try:
        from nq_data.finnhub import get_finnhub_client
        client = get_finnhub_client()
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return []

    try:
        articles = client.get_news(yf_ticker, days=7)
        if not articles:
            return []
        results = []
        for a in articles[:n]:
            results.append({
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "source": a.get("source", ""),
            })
        return results
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return []



def _fetch_enrichment(ticker: str | None, market: str = "US") -> dict:
    """Fetch technical indicators + insider + news sentiment for Ask AI.
    Cache-first: reads from enrichment_cache (1h TTL) before live fetch.
    Falls back to stale cache when Finnhub is rate-limited."""
    if not ticker:
        return {}
    # Try cache first (1-hour TTL)
    try:
        from nq_api.cache.score_cache import read_enrichment, write_enrichment, read_enrichment_stale
        cached = read_enrichment(ticker, market)
        if cached:
            log.info('Ask AI enrichment cache HIT for %s/%s: %d fields', ticker, market, len(cached))
            return cached
    except Exception:
        pass  # Cache miss — fall through to live fetch
    try:
        from nq_api.routes.analyst import _fetch_finnhub_data
        result = _fetch_finnhub_data(ticker, market)
        if result:
            try:
                write_enrichment(ticker, market, result)
            except Exception:
                pass  # Cache write failure is non-critical
            return result
        # Finnhub returned empty (rate-limited). Try stale cache.
        try:
            stale = read_enrichment_stale(ticker, market)
            if stale:
                log.info('Ask AI enrichment stale cache fallback for %s/%s: %d fields', ticker, market, len(stale))
                return stale
        except Exception:
            pass
        return {}
    except Exception as exc:
        log.warning('Enrichment for Ask AI failed %s: %s', ticker, exc)
        # Last resort: try stale cache
        try:
            stale = read_enrichment_stale(ticker, market)
            if stale:
                log.info('Ask AI enrichment stale cache fallback (after error) for %s/%s', ticker, market)
                return stale
        except Exception:
            pass
        return {}


# ── Post-processing: validate LLM output against injected data ────────────────
import re as _val_re

_VALIDATION_RULES = [
    (["P/E", "PE", "PRICE-EARNINGS"], "P/E_TTM", 0.15),
    (["BETA"], "BETA", 0.20),
    (["PRICE", "CURRENT_PRICE"], "CURRENT_PRICE", 0.05),
    (["EPS"], "EPS", 0.15),
    (["P/B", "PRICE-BOOK", "PRICE TO BOOK"], "P/B", 0.20),
    (["MARKET CAP", "MCAP", "MKT CAP"], "MCAP", 0.20),
]


def _extract_verified_values(platform_ctx: str | None) -> dict[str, float]:
    """Extract [VERIFIED] and [ESTIMATE] values from platform context for post-hoc validation."""
    if not platform_ctx:
        return {}
    verified = {}
    for m in _val_re.finditer(r'(\w[\w/]*)=([\$₹]?[\d,]+\.?\d*)\s*\[(?:VERIFIED|ESTIMATE)\]', platform_ctx):
        key = m.group(1).upper().replace("/", "_")
        val_str = m.group(2).replace(",", "").replace("$", "").replace("₹", "")
        try:
            verified[key] = float(val_str)
        except ValueError:
            pass
    return verified


def _validate_response_metrics(result, verified: dict[str, float]) -> "StructuredQueryResponse":
    """Validate LLM metrics against [VERIFIED] data. Correct P/E, Beta, Price discrepancies > tolerance."""
    if not verified or not hasattr(result, 'metrics') or not result.metrics:
        return result

    corrections_made = []

    for metric in result.metrics:
        name = metric.name.upper() if metric.name else ""
        value_str = str(metric.value) if metric.value else ""
        num_match = _val_re.search(r'[\d,]+\.?\d*', value_str.replace(",", ""))
        if not num_match:
            continue
        try:
            llm_val = float(num_match.group())
        except ValueError:
            continue

        for patterns, ctx_key, tolerance in _VALIDATION_RULES:
            if ctx_key not in verified:
                continue
            if not any(p in name for p in patterns):
                continue
            ctx_val = verified[ctx_key]
            if ctx_val > 0 and abs(llm_val - ctx_val) / ctx_val > tolerance:
                old_val = metric.value
                if "P/E" in ctx_key or "PE" in ctx_key:
                    metric.value = f"{ctx_val:.1f}x"
                elif "BETA" in ctx_key:
                    metric.value = f"{ctx_val:.2f}"
                elif "PRICE" in ctx_key:
                    cur = "₹" if "Rs" in value_str else "$"
                    metric.value = f"{cur}{ctx_val:,.2f}"
                else:
                    metric.value = str(ctx_val)
                corrections_made.append(f"{name}: {old_val} → {metric.value}")
                logger.info("Corrected LLM metric %s from %s to %s (verified: %s)",
                            name, old_val, metric.value, ctx_val)
            break

    if corrections_made and hasattr(result, 'summary') and result.summary:
        if "Corrected" not in result.summary:
            result.summary += f" [Corrected metrics: {'; '.join(corrections_made)}]"

    return result


def _validate_portfolio_stocks(portfolio_stocks: list[dict], market: str, summary: str = "") -> tuple[list[dict], str, list[str]]:
    """Fetch real yfinance data for each portfolio stock and validate rationale + summary claims.

    Returns (corrected_stocks, corrected_summary, correction_notes).
    """
    if not portfolio_stocks:
        return portfolio_stocks, summary, []

    corrections = []
    ticker_to_real: dict[str, dict] = {}

    # Batch-fetch real data
    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        if not ticker:
            continue
        sym = ticker + ".NS" if market == "IN" and "." not in ticker else ticker
        info = _fetch_yf_info_cached(sym)
        if not info.get("_cached_ok"):
            continue
        real_pe = info.get("trailingPE")
        real_beta = info.get("beta")
        real_div = info.get("dividendYield")
        if real_div and real_div < 1:
            real_div = real_div * 100
        ticker_to_real[ticker] = {
            "pe": real_pe,
            "beta": real_beta,
            "div": real_div,
        }

    # Validate per-stock rationale
    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        real = ticker_to_real.get(ticker)
        if not real:
            continue
        rationale = stock.get("rationale", "")
        if not rationale:
            continue

        real_pe = real["pe"]
        real_beta = real["beta"]
        real_div = real["div"]

        # P/E claims — tolerance 10% (tighter than 20% to catch stock-to-stock swaps)
        pe_patterns = [
            re.compile(r"P/E\s*(?:of|at|is|:|=)?\s*\D{0,15}(\d+\.?\d*)", re.I),
            re.compile(r"(\d+\.?\d*)\s*x?\s*P/E\b", re.I),
        ]
        for pe_pat in pe_patterns:
            pe_matches = list(pe_pat.finditer(rationale))
            for m in pe_matches:
                claimed = float(m.group(1))
                if real_pe and real_pe > 0 and abs(claimed - real_pe) / real_pe > 0.10:
                    old_r = rationale
                    rationale = re.sub(re.escape(m.group(0)),
                                       f"P/E {real_pe:.1f}", rationale, count=1, flags=re.I)
                    if rationale != old_r:
                        corrections.append(f"{ticker} P/E: {claimed:.1f}x → {real_pe:.1f}x")

        # Beta claims
        beta_matches = list(re.finditer(r"beta\s*(?:of|at|is|:|=)?\s*(\d+\.?\d*)", rationale, re.I))
        for m in beta_matches:
            claimed = float(m.group(1))
            if real_beta and abs(claimed - real_beta) / max(real_beta, 0.1) > 0.25:
                old_r = rationale
                rationale = re.sub(r"beta\s*(?:of|at|is|:|=)?\s*" + re.escape(m.group(1)),
                                   f"beta {real_beta:.2f}", rationale, count=1, flags=re.I)
                if rationale != old_r:
                    corrections.append(f"{ticker} Beta: {claimed:.2f} → {real_beta:.2f}")

        # Yield claims
        if real_div and real_div > 0:
            yield_matches = list(re.finditer(r"~?(\d+\.?\d*)%\s*(?:yield|dividend)", rationale, re.I))
            for m in yield_matches:
                claimed = float(m.group(1))
                if abs(claimed - real_div) / real_div > 0.30:
                    old_r = rationale
                    rationale = re.sub(r"~?" + re.escape(m.group(1)) + r"%\s*(?=yield|dividend)",
                                       f"~{real_div:.1f}%", rationale, count=1, flags=re.I)
                    if rationale != old_r:
                        corrections.append(f"{ticker} Yield: {claimed:.1f}% → {real_div:.1f}%")

        if rationale != stock.get("rationale", ""):
            stock["rationale"] = rationale

    # Validate summary — replace P/E claims near ticker mentions
    if summary and ticker_to_real:
        for ticker, real in ticker_to_real.items():
            real_pe = real["pe"]
            if not real_pe:
                continue
            # Match ticker name followed by up to 70 chars (not crossing sentence boundary) then P/E claim
            # Flexible: allows words like "only" / "attractive" between P/E and the number
            pattern = re.compile(
                rf"({re.escape(ticker)}[^.\n]{{0,70}}P/E\s*(?:of|at|is|:|=)?\s*\D{{0,15}})(\d+\.?\d*)",
                re.I,
            )
            for m in pattern.finditer(summary):
                claimed = float(m.group(2))
                if abs(claimed - real_pe) / real_pe > 0.10:
                    prefix = m.group(1)
                    old_text = m.group(0)
                    new_text = f"{prefix}{real_pe:.1f}"
                    summary = summary.replace(old_text, new_text, 1)
                    corrections.append(f"{ticker} summary P/E: {claimed:.1f}x → {real_pe:.1f}x")

    return portfolio_stocks, summary, corrections


def _validate_and_fill_portfolio_prices(
    portfolio_stocks: list[dict], market: str
) -> tuple[list[dict], list[str]]:
    """Validate and fill entry_price, target_price, stop_loss for portfolio stocks.
    Replaces 'Live N/A' placeholders with real prices and computes
    target/stop_loss deterministically from the live entry price.

    Price source priority (US): FMP quote → yfinance → FMP profile → score_cache (7d)
    Price source priority (IN): yfinance (.NS) → FMP profile → score_cache (7d)

    Returns (corrected_stocks, fill_notes).
    """
    if not portfolio_stocks:
        return portfolio_stocks, []

    fill_notes = []
    cur = "₹" if market == "IN" else "$"

    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        if not ticker:
            continue

        sym = ticker + ".NS" if market == "IN" and "." not in ticker else ticker
        live_price = None
        price_source = None

        # ── Price Tier 1: FMP (most reliable on cloud for US) or yfinance (.NS for IN) ──
        if market == "US":
            # US: try FMP first (more reliable than yfinance on cloud)
            try:
                from nq_data.fmp import get_fmp_client
                fmp = get_fmp_client()
                if fmp._enabled:
                    quote = fmp.get_quote(ticker)
                    if quote and quote.get("price"):
                        live_price = float(quote["price"])
                        price_source = "fmp_quote"
                    if not live_price or live_price <= 0:
                        profile = fmp.get_profile(ticker)
                        if profile and profile.get("price"):
                            live_price = float(profile["price"])
                            price_source = "fmp_profile"
            except Exception as exc:
                log.warning("FMP price fetch failed for %s: %s", ticker, exc)

            # US yfinance fallback (cached + direct)
            if not live_price or live_price <= 0:
                info = _fetch_yf_info_cached(ticker)
                if info.get("_cached_ok"):
                    live_price = info.get("currentPrice") or info.get("regularMarketPrice")
                    if live_price and live_price > 0:
                        price_source = "yfinance"
                else:
                    # Bypass failure cache with direct fetch
                    try:
                        t = yf.Ticker(ticker, session=_get_yf_session())
                        info = t.info or {}
                        live_price = info.get("currentPrice") or info.get("regularMarketPrice")
                        if live_price and live_price > 0:
                            price_source = "yfinance_direct"
                    except Exception as exc:
                        log.debug("Direct yfinance fallback failed for %s: %s", ticker, exc)

        else:
            # IN: FMP first (not rate-limited on cloud), then yfinance fallback
            # Tier 1: FMP quote + profile (works for some IN stocks, no rate limits)
            try:
                from nq_data.fmp import get_fmp_client
                fmp = get_fmp_client()
                if fmp._enabled:
                    quote = fmp.get_quote(sym)
                    if quote and quote.get("price"):
                        live_price = float(quote["price"])
                        price_source = "fmp_quote_in"
                    if not live_price or live_price <= 0:
                        profile = fmp.get_profile(sym)
                        if profile and profile.get("price"):
                            live_price = float(profile["price"])
                            price_source = "fmp_profile_in"
                    # Also try bare ticker on FMP
                    if (not live_price or live_price <= 0) and "." not in ticker:
                        quote_bare = fmp.get_quote(ticker)
                        if quote_bare and quote_bare.get("price"):
                            live_price = float(quote_bare["price"])
                            price_source = "fmp_quote_in_bare"
            except Exception as exc:
                log.debug("FMP IN price fallback failed for %s: %s", sym, exc)

            # Tier 2: yfinance .NS direct (bypass failure cache for IN stocks)
            if not live_price or live_price <= 0:
                try:
                    t = yf.Ticker(sym, session=_get_yf_session())
                    info = t.info or {}
                    live_price = info.get("currentPrice") or info.get("regularMarketPrice")
                    if live_price and live_price > 0:
                        price_source = "yfinance_ns_direct"
                except Exception as exc:
                    log.debug("Direct yfinance NS failed for %s: %s", sym, exc)

            # Tier 3: yf.download (often more reliable on cloud than Ticker.info)
            if not live_price or live_price <= 0:
                try:
                    import yfinance as yf
                    hist = yf.download(sym, period="5d", progress=False, auto_adjust=True,
                                       threads=False, session=_get_yf_session())
                    if hist is not None and not hist.empty and "Close" in hist.columns:
                        close = hist["Close"]
                        if isinstance(close, pd.DataFrame):
                            close = close[sym] if sym in close.columns else close.iloc[:, 0]
                        close = close.dropna()
                        if len(close) > 0:
                            live_price = float(close.iloc[-1])
                            price_source = "yf_download_ns"
                except Exception as exc:
                    log.debug("yf.download NS failed for %s: %s", sym, exc)

            # Tier 4: yfinance .NS with plain requests session (no impersonation)
            if not live_price or live_price <= 0:
                try:
                    t_plain = yf.Ticker(sym)
                    info_plain = t_plain.info or {}
                    live_price = info_plain.get("currentPrice") or info_plain.get("regularMarketPrice")
                    if live_price and live_price > 0:
                        price_source = "yfinance_ns_plain"
                except Exception as exc:
                    log.debug("Plain yfinance NS failed for %s: %s", sym, exc)

            # Tier 5: bare ticker on yfinance (some tickers work without .NS)
            if not live_price or live_price <= 0:
                if "." not in ticker:
                    try:
                        t = yf.Ticker(ticker, session=_get_yf_session())
                        info_bare = t.info or {}
                        live_price = info_bare.get("currentPrice") or info_bare.get("regularMarketPrice")
                        if live_price and live_price > 0:
                            price_source = "yfinance_bare_direct"
                    except Exception as exc:
                        log.debug("Direct yfinance bare failed for %s: %s", ticker, exc)

        # ── Price Tier 2: score_cache (up to 7 days stale) ──
        if not live_price or live_price <= 0:
            try:
                from nq_api.cache.score_cache import read_one as _sc_read_one
                sc = _sc_read_one(ticker.upper(), market, max_age_seconds=604800)  # 7 days
                if sc and sc.get("current_price"):
                    live_price = float(sc["current_price"])
                    price_source = "score_cache_7d"
                    fill_notes.append(f"{ticker} price: stale cache 7d ({live_price:.2f})")
            except Exception:
                pass

        if not live_price or live_price <= 0:
            # All sources failed
            stock["price_unavailable"] = True
            stock["entry_price"] = "Price unavailable"
            stock["target_price"] = "N/A"
            stock["stop_loss"] = "N/A"
            fill_notes.append(f"{ticker}: price unavailable from all sources (tried {'FMP+yf+cache' if market == 'US' else 'yf_ns+yf_dl+yf_plain+FMP+yf_bare+cache'})")
            log.warning("Portfolio price unavailable for %s/%s (market=%s)", ticker, sym, market)
            continue

        if price_source:
            log.debug("Portfolio price for %s/%s: %.2f via %s", ticker, sym, live_price, price_source)

        entry_str = stock.get("entry_price", "")
        needs_fill = (
            not entry_str
            or "N/A" in entry_str
            or "Live N/A" in entry_str
            or "unavailable" in entry_str.lower()
            or "enter at market" in entry_str.lower()
        )

        # Check if existing entry price is stale (>5% off live)
        entry_off = 0.0
        if not needs_fill and entry_str:
            nums = re.findall(r'[\d,]+\.?\d*', entry_str)
            if nums:
                try:
                    entry_num = float(nums[0].replace(",", ""))
                    if entry_num > 0:
                        entry_off = abs(live_price - entry_num) / entry_num
                        if entry_off > 0.05:
                            needs_fill = True
                except ValueError:
                    pass

        if needs_fill:
            # Compute entry range: live price ±2%
            entry_low = live_price * 0.98
            entry_high = live_price * 1.02
            if market == "IN":
                stock["entry_price"] = f"₹{live_price:,.0f} (₹{entry_low:,.0f}–₹{entry_high:,.0f})"
            else:
                stock["entry_price"] = f"${live_price:,.2f} (${entry_low:,.2f}–${entry_high:,.2f})"
            fill_notes.append(f"{ticker} entry: live price {cur}{live_price:,.2f} via {price_source}")

        # Fill target_price if missing or looks like placeholder
        target_str = stock.get("target_price", "")
        if not target_str or "N/A" in target_str or "unavailable" in target_str.lower():
            target_price = live_price * 1.15
            if market == "IN":
                stock["target_price"] = f"₹{target_price:,.0f} (+15%)"
            else:
                stock["target_price"] = f"${target_price:,.2f} (+15%)"

        # Fill stop_loss if missing
        stop_str = stock.get("stop_loss", "")
        if not stop_str or "N/A" in stop_str or "unavailable" in stop_str.lower():
            stop_price = live_price * 0.90
            if market == "IN":
                stock["stop_loss"] = f"₹{stop_price:,.0f} (-10%)"
            else:
                stock["stop_loss"] = f"${stop_price:,.2f} (-10%)"

        # Recompute risk_reward if missing or looks placeholder-ish
        rr_str = stock.get("risk_reward", "")
        if not rr_str or "N/A" in rr_str:
            try:
                nums_entry = re.findall(r'[\d,]+\.?\d*', stock.get("entry_price", ""))
                nums_target = re.findall(r'[\d,]+\.?\d*', stock.get("target_price", ""))
                nums_stop = re.findall(r'[\d,]+\.?\d*', stock.get("stop_loss", ""))
                if nums_entry and nums_target and nums_stop:
                    e = float(nums_entry[0].replace(",", ""))
                    t = float(nums_target[0].replace(",", ""))
                    s = float(nums_stop[0].replace(",", ""))
                    if e > 0 and s > 0:
                        reward = abs(t - e)
                        risk = abs(e - s)
                        if risk > 0:
                            rr = reward / risk
                            stock["risk_reward"] = f"1:{rr:.1f}"
            except (ValueError, ZeroDivisionError):
                pass

    # Strip LLM-fabricated placeholder text from entry_price fields
    _CACHED_PATTERN = re.compile(
        r"(?:cached|enter near|enter at|market price|current price)", re.IGNORECASE
    )
    for stock in portfolio_stocks:
        ep = stock.get("entry_price", "")
        if ep and _CACHED_PATTERN.search(ep):
            stock["entry_price"] = "Price unavailable"
            stock["price_unavailable"] = True

    return portfolio_stocks, fill_notes


def _build_stock_summary(ticker: str | None, market: str, enrichment: dict, platform_ctx: str | None) -> StockSummary | None:
    """Build a StockSummary from enrichment + platform data for the quick-glance card."""
    if not ticker and not enrichment and not platform_ctx:
        return None

    # Determine the ticker to use
    effective_ticker = ticker or ""
    if not effective_ticker and enrichment:
        effective_ticker = enrichment.get("symbol", "")

    # If still no ticker, try to extract from platform_ctx
    # Format: "  NVDA: ForeCast=8.1/10 | CURRENT_PRICE=$196.50 | ..." or "AAPL | Apple Inc. | ..."
    if not effective_ticker and platform_ctx:
        import re as _re
        # Try "TICKER:" format — only match lines with ForeCast or CURRENT_PRICE to avoid
        # false matches on common English words (e.g. "TECH:" from "tech portfolio")
        m = _re.search(r"^\s*([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*:\s*(?:ForeCast|CURRENT_PRICE)", platform_ctx, _re.MULTILINE)
        if not m:
            # Broader fallback: "TICKER:" followed by stock data patterns
            m = _re.search(r"^\s*([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*:\s*\d+/10", platform_ctx, _re.MULTILINE)
        if not m:
            # Try "TICKER |" format (screener)
            m = _re.search(r"^([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*\|", platform_ctx.strip())
        if m:
            effective_ticker = m.group(1)

    if not effective_ticker:
        return None

    # Auto-detect market from ticker suffix
    detected_market = market
    if effective_ticker.endswith(".NS") or effective_ticker.endswith(".BO"):
        detected_market = "IN"

    is_india = detected_market == "IN" or effective_ticker.endswith(".NS") or effective_ticker.endswith(".BO")
    cur = "₹" if is_india else "$"

    # Try to get price/fundamentals from enrichment first
    price = enrichment.get("current_price") or enrichment.get("regularMarketPrice") or enrichment.get("finnhub_price")
    change_pct = enrichment.get("change_pct") or enrichment.get("regularMarketChangePercent")
    pe = enrichment.get("pe_ttm") or enrichment.get("trailingPE")
    pb = enrichment.get("pb_ratio") or enrichment.get("priceToBook")
    mcap = enrichment.get("market_cap") or enrichment.get("marketCap")
    high52 = enrichment.get("week_52_high") or enrichment.get("fiftyTwoWeekHigh")
    low52 = enrichment.get("week_52_low") or enrichment.get("fiftyTwoWeekLow")
    target = enrichment.get("analyst_target") or enrichment.get("targetMeanPrice")
    rec = enrichment.get("analyst_rec") or enrichment.get("recommendationKey", "")
    beta = enrichment.get("beta")
    sector = enrichment.get("sector", "")
    name = enrichment.get("long_name") or enrichment.get("shortName") or effective_ticker
    eps = enrichment.get("eps_ttm")

    # Try to get ForeCast score from platform_ctx text
    forecast_score = None
    if platform_ctx:
        import re as _re
        m = _re.search(rf"{_re.escape(effective_ticker)}.*?(\d+\.?\d*)/10", platform_ctx)
        if m:
            try:
                forecast_score = float(m.group(1))
            except ValueError:
                pass

    # If enrichment lacks fundamentals (price/P/E/beta), fetch from _fetch_one
    needs_fundamentals = not price or not pe or not beta
    if needs_fundamentals and effective_ticker:
        try:
            from nq_api.data_builder import _fetch_one
            fund = _fetch_one(effective_ticker, detected_market, fast_pe=False)
            if fund and fund.get("_is_real"):
                if not price:
                    price = fund.get("current_price")
                if not change_pct:
                    change_pct = fund.get("change_pct")
                if not pe:
                    pe = fund.get("pe_ttm")
                if not pb:
                    pb = fund.get("pb_ratio")
                if not mcap:
                    mcap = fund.get("market_cap")
                if not high52:
                    high52 = fund.get("week52_high") or fund.get("week_52_high")
                if not low52:
                    low52 = fund.get("week52_low") or fund.get("week_52_low")
                if not target:
                    target = fund.get("analyst_target")
                if not rec:
                    rec = fund.get("analyst_rec", "")
                if not beta:
                    beta = fund.get("beta")
                if not sector:
                    sector = fund.get("sector", "")
                if not name or name == effective_ticker:
                    name = fund.get("long_name", effective_ticker)
                if not eps:
                    eps = fund.get("eps_ttm")
        except Exception:
            pass

    # Fallback: try score_cache for fundamentals if _fetch_one failed or returned incomplete data
    # (Finnhub may provide price but miss P/E, Beta, etc. — score_cache often has them.)
    needs_cache = (price is None or pe is None or beta is None or mcap is None) and effective_ticker
    if needs_cache:
        try:
            from nq_api.cache import score_cache
            cached = score_cache.read_one(effective_ticker, detected_market, max_age_seconds=999999999)
            if cached:
                if price is None:
                    price = cached.get("current_price")
                if pe is None:
                    pe = cached.get("pe_ttm")
                if pb is None:
                    pb = cached.get("pb_ratio")
                if mcap is None:
                    mcap = cached.get("market_cap")
                if beta is None:
                    beta = cached.get("beta")
                if not sector:
                    sector = cached.get("sector", "")
                if not name or name == effective_ticker:
                    name = cached.get("long_name") or cached.get("name") or effective_ticker
                if change_pct is None:
                    change_pct = cached.get("change_pct")
        except Exception:
            pass

    # FMP supplement: DCF valuation, analyst target, insider trading, estimates, earnings
    if effective_ticker:
        try:
            from nq_data.fmp import get_fmp_client
            fmp = get_fmp_client()
            if fmp._enabled:
                fmp_sym = _yf_symbol(effective_ticker, detected_market)
                # DCF valuation
                if not target:
                    fmp_target = fmp.get_price_target(fmp_sym)
                    if fmp_target and fmp_target.get("target_avg") is not None:
                        target = round(float(fmp_target["target_avg"]), 2)
                # Analyst consensus
                if not rec:
                    fmp_grades = fmp.get_analyst_grades(fmp_sym)
                    if fmp_grades and fmp_grades.get("consensus"):
                        rec = fmp_grades["consensus"].lower()
        except Exception:
            pass
    if price is None and platform_ctx and effective_ticker:
        import re as _re
        cur_pat = r"Rs\." if is_india else r"\$"
        m = _re.search(
            rf"{_re.escape(effective_ticker)}.*?CURRENT_PRICE={cur_pat}([\d,]+\.?\d*)",
            platform_ctx,
        )
        if m:
            try:
                price = float(m.group(1).replace(",", ""))
            except (ValueError, IndexError):
                pass

    # Only return summary if we have at least a price
    if price is None:
        return None

    return StockSummary(
        ticker=effective_ticker,
        name=name if name else None,
        price=round(float(price), 2) if price else None,
        change_pct=round(float(change_pct), 2) if change_pct is not None else None,
        pe_ttm=round(float(pe), 1) if pe else None,
        eps_ttm=round(float(eps), 2) if eps else None,
        pb_ratio=round(float(pb), 2) if pb else None,
        market_cap=float(mcap) if mcap else None,
        week_52_high=round(float(high52), 2) if high52 else None,
        week_52_low=round(float(low52), 2) if low52 else None,
        analyst_target=round(float(target), 2) if target else None,
        analyst_recommendation=rec.upper() if rec else None,
        beta=round(float(beta), 2) if beta else None,
        sector=sector if sector else None,
        forecast_score=forecast_score,
        currency=cur,
    )


def _save_conversation_turn(user_id: str | None, session_key: str, role: str, content: str,
                            ticker: str | None = None, market: str = "US") -> None:
    """Persist a conversation turn to Supabase for multi-session memory."""
    if not user_id or not session_key:
        return
    try:
        from nq_api.cache.score_cache import _supabase_rest
        _supabase_rest("conversations", method="POST", body=[{
            "user_id": user_id,
            "session_key": session_key,
            "role": role,
            "content": content[:5000],  # truncate long messages
            "ticker": ticker,
            "market": market,
        }])
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        pass  # Best-effort — never block the main query flow


def _load_conversation_history(user_id: str | None, session_key: str, limit: int = 20) -> list[dict]:
    """Load recent conversation turns for multi-session memory."""
    if not user_id or not session_key:
        return []
    try:
        from nq_api.cache.score_cache import _supabase_rest
        data = _supabase_rest("conversations", method="GET", query={
            "select": "role,content,created_at",
            "user_id": f"eq.{user_id}",
            "session_key": f"eq.{session_key}",
            "order": "created_at.desc",
            "limit": str(limit),
        })
        if isinstance(data, list) and data:
            # Return in chronological order
            data.reverse()
            return data
    except Exception:
        pass
    return []


def _fetch_india_macro() -> str | None:
    """Fetch India-specific market context: Nifty 50, Sensex, INR/USD, India VIX."""
    try:
        lines = []

        # Nifty 50
        nifty = yf.Ticker("^NSEI", session=_get_yf_session())
        hist = nifty.history(period="5d", auto_adjust=True)
        if len(hist) >= 2:
            nifty_price = float(hist["Close"].iloc[-1])
            nifty_prev = float(hist["Close"].iloc[-2])
            nifty_chg = (nifty_price - nifty_prev) / nifty_prev * 100
            lines.append(f"Nifty 50: {nifty_price:,.0f} ({nifty_chg:+.2f}% today)")

        # BSE Sensex
        sensex = yf.Ticker("^BSESN", session=_get_yf_session())
        hist2 = sensex.history(period="5d", auto_adjust=True)
        if len(hist2) >= 2:
            sensex_price = float(hist2["Close"].iloc[-1])
            sensex_prev = float(hist2["Close"].iloc[-2])
            sensex_chg = (sensex_price - sensex_prev) / sensex_prev * 100
            lines.append(f"BSE Sensex: {sensex_price:,.0f} ({sensex_chg:+.2f}% today)")

        # INR/USD exchange rate
        inr = yf.Ticker("USDINR=X", session=_get_yf_session())
        inr_hist = inr.history(period="5d", auto_adjust=True)
        if not inr_hist.empty:
            inr_rate = float(inr_hist["Close"].iloc[-1])
            lines.append(f"USD/INR: {inr_rate:.2f}")

        # India VIX
        india_vix = yf.Ticker("^INDIAVIX", session=_get_yf_session())
        vix_hist = india_vix.history(period="5d", auto_adjust=True)
        if not vix_hist.empty:
            ivix = float(vix_hist["Close"].iloc[-1])
            lines.append(f"India VIX: {ivix:.1f} ({'elevated' if ivix > 20 else 'normal'})")

        return "Indian Market Context: " + " | ".join(lines) if lines else None
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return None


def _fetch_dynamic_nse_stock(word: str) -> dict | None:
    """
    Try to fetch live data for an NSE stock not in our screener universe.
    word: uppercase stock name/ticker from user query.
    Returns a dict with price, fundamentals, or None if not found.
    Tries yfinance first, falls back to FMP for price data.
    """
    nse_sym = _NSE_NAME_MAP.get(word)
    if not nse_sym:
        nse_sym = f"{word}.NS"

    def _try_fmp() -> dict | None:
        """FMP fallback for price when yfinance fails."""
        try:
            from nq_data.fmp import get_fmp_client
            fmp = get_fmp_client()
            if not fmp._enabled:
                return None
            quote = fmp.get_quote(nse_sym)
            if quote and quote.get("price"):
                return {
                    "symbol": nse_sym,
                    "display": word,
                    "price": quote["price"],
                    "currency": "INR",
                    "change_pct": quote.get("change_pct", 0),
                    "week52_high": quote.get("year_high"),
                    "week52_low": quote.get("year_low"),
                    "pe_ttm": quote.get("pe"),
                    "pb_ratio": None,
                    "market_cap": quote.get("market_cap"),
                    "beta": None,
                    "analyst_target": None,
                    "analyst_recommendation": "",
                    "gross_margin": None,
                    "revenue_growth": None,
                    "sector": "",
                    "longName": word,
                }
        except Exception:
            pass
        return None

    try:
        t = yf.Ticker(nse_sym, session=_get_yf_session())
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return _try_fmp()  # yfinance got no price, try FMP

        return {
            "symbol": nse_sym,
            "display": word,
            "price": price,
            "currency": info.get("currency", "INR"),
            "change_pct": info.get("regularMarketChangePercent", 0),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
            "pe_ttm": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "beta": info.get("beta"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey", "").upper(),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "sector": info.get("sector", ""),
            "longName": info.get("longName", word),
        }
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return _try_fmp()  # yfinance exception, try FMP


def _detect_tickers_in_question(question: str, market: str = "US") -> tuple[list[str], list[str]]:
    """
    Returns (in_universe_tickers, out_of_universe_words).
    in_universe_tickers: known tickers found in question.
    out_of_universe_words: words that look like NSE tickers but aren't in universe.
    """
    from nq_api.universe import US_DEFAULT, IN_DEFAULT
    known_us = set(US_DEFAULT)
    known_in = set(IN_DEFAULT)
    in_universe = []
    q_upper = question.upper()

    # Check known universe tickers — skip single-letter tickers (A, T, F, etc.)
    # to avoid false positives from common English words.
    # When market=IN, only check Indian tickers.
    search_pool = known_in if market == "IN" else (known_us | known_in)
    for t in search_pool:
        base = t.replace(".NS", "").replace(".BO", "")
        if len(base) <= 2:
            continue  # single/double-letter tickers match too many English words
        if re.search(r'\b' + re.escape(base) + r'\b', q_upper):
            in_universe.append(t)

    # For India queries, also check NSE name map keys
    out_of_universe = []
    known_bases = {t.replace(".NS", "").replace(".BO", "") for t in search_pool}
    if market == "IN" or any(k in q_upper for k in _INDIA_KEYWORDS):
        # First check the name map directly
        for name_key in _NSE_NAME_MAP:
            if (re.search(r'\b' + re.escape(name_key) + r'\b', q_upper)
                    and name_key not in known_bases):
                if name_key not in out_of_universe:
                    out_of_universe.append(name_key)

        # Then scan remaining words that look like tickers
        for word in q_upper.split():
            clean = re.sub(r"[^A-Z]", "", word)
            if (3 <= len(clean) <= 12
                    and clean not in _STOP_WORDS
                    and clean not in _TICKER_STOP_WORDS
                    and clean not in known_bases
                    and clean not in out_of_universe
                    and clean not in _NSE_NAME_MAP):
                out_of_universe.append(clean)

    return in_universe[:5], out_of_universe[:3]


def _fmt_price_row(ticker: str, fund: dict, score: int, market: str, rank: int | None = None) -> str:
    """Format a single stock row with LIVE price + score for LLM context injection."""
    is_india = market == "IN" or ticker.endswith(".NS") or ticker.endswith(".BO")
    cur = "Rs." if is_india else "$"  # ASCII-safe currency symbol

    price    = fund.get("current_price")
    low52    = fund.get("week52_low")
    high52   = fund.get("week52_high")
    target   = fund.get("analyst_target")
    rec      = fund.get("analyst_rec", "")
    chg      = fund.get("change_pct", 0.0)
    pe       = fund.get("pe_ttm")
    pb       = fund.get("pb_ratio")
    name     = fund.get("long_name", ticker)
    mcap     = fund.get("market_cap")

    price_str  = f"{cur}{price:,.2f} ({chg:+.1f}%)" if price else "price N/A"
    range_str  = f"52w {cur}{low52:,.0f}-{cur}{high52:,.0f}" if low52 and high52 else ""
    target_str = f"analyst target {cur}{target:,.0f} ({rec})" if target else ""
    pe_str     = f"P/E={pe:.1f}" if pe else ""
    mcap_str   = ""
    if mcap:
        if is_india:
            mcap_str = f"MCap={mcap/1e7:.0f}Cr"
        else:
            mcap_str = f"MCap=${mcap/1e9:.0f}B" if mcap >= 1e9 else f"MCap=${mcap/1e6:.0f}M"

    prefix = f"#{rank} " if rank else "  "
    details = " | ".join(x for x in [range_str, pe_str, mcap_str, target_str] if x)
    return f"{prefix}{ticker} ({name}): {score}/10 | {price_str} | {details}"


def _enrich_with_platform_data(question: str, market: str) -> str | None:
    """
    Fetch NeuralQuant's own stock scores + live prices when the question needs them.
    Uses score_cache (instant) + _fetch_one (2-5s per stock) instead of
    build_real_snapshot (30-120s for full universe).
    """
    from nq_api.data_builder import _fetch_one
    from nq_api.cache import score_cache

    q_upper = question.upper()
    parts: list[str] = []
    target_market = "IN" if any(k in q_upper for k in _INDIA_KEYWORDS) else market

    needs_screener = any(k in q_upper for k in _SCREENER_KEYWORDS)
    in_universe_tickers, out_of_universe_words = _detect_tickers_in_question(question, target_market)
    needs_stock_scores = (
        in_universe_tickers
        or out_of_universe_words
        or any(k in q_upper for k in ["IS A BUY", "IS A SELL", "COMPARE", "VERSUS", "VS ", "OVERVALUED", "SHORT INTEREST"])
    )

    if not needs_screener and not needs_stock_scores:
        return None

    try:
        # Pre-fetch FMP batch quotes for all detected tickers (single API call, ~200ms)
        # Falls back gracefully — returns {} if FMP disabled or fails
        fmp_prices: dict[str, dict] = {}
        try:
            from nq_data.fmp import get_fmp_client
            fmp_client = get_fmp_client()
            if fmp_client._enabled:
                # Ensure IN tickers have .NS suffix — FMP requires it for NSE stocks
                all_tickers = list(in_universe_tickers) + out_of_universe_words
                if target_market == "IN":
                    all_tickers = [
                        t if "." in t else f"{t}.NS" for t in all_tickers
                    ]
                if all_tickers:
                    fmp_prices = fmp_client.get_batch_quotes(all_tickers) or {}
        except Exception:
            pass

        # FAST PATH: score_cache for screener data (sub-100ms)
        if needs_screener or (not in_universe_tickers and not out_of_universe_words and needs_stock_scores):
            cached = score_cache.read_top(target_market, 20, max_age_seconds=300)
            if not cached:
                cached = score_cache.read_top(target_market, 20, max_age_seconds=86400)
            if not cached:
                cached = score_cache.read_top(target_market, 20, max_age_seconds=999999999)
            if cached:
                lines = [f"NeuralQuant {target_market} Screener — Top 20 (cached scores). LIVE PRICES for top 5 — USE THESE, NOT training data:"]
                for i, row in enumerate(cached[:20]):
                    t = row.get("ticker", "")
                    sc = int(row.get("composite_score", 0.5) * 10)
                    pe = row.get("pe_ttm")
                    gpm = row.get("gross_profit_margin")
                    momentum = row.get("momentum_percentile")
                    quality = row.get("quality_percentile")
                    value = row.get("value_percentile")
                    # Fetch live price for top stocks only (first 5)
                    if i < 5:
                        fund = _fetch_one(t, target_market, fast_pe=False)
                        price = fund.get("current_price")
                        chg = fund.get("change_pct", 0)
                        # FMP batch-quote fallback
                        if not price:
                            fmp_fb = (fmp_prices.get(t)
                                      or fmp_prices.get(f"{t}.NS")
                                      or fmp_prices.get(f"{t}.BO")
                                      or {})
                            if fmp_fb.get("price"):
                                price = fmp_fb["price"]
                                chg = fmp_fb.get("change_pct", 0) or chg
                        cur = "Rs." if target_market == "IN" else "$"
                        price_str = f"{cur}{price:,.2f} ({chg:+.1f}%)" if price else "N/A"
                    else:
                        price_str = "N/A (cached)"
                    details = []
                    if pe: details.append(f"P/E={pe:.1f}")
                    if gpm: details.append(f"GPM={gpm:.0%}")
                    if momentum: details.append(f"Momentum={momentum:.0%}")
                    if quality: details.append(f"Quality={quality:.0%}")
                    if value: details.append(f"Value={value:.0%}")
                    det_str = " | ".join(details) if details else ""
                    lines.append(f"#{i+1} {t}: {sc}/10 | {price_str} | {det_str}")
                lines.append("IMPORTANT: Live prices for top 5, rest cached. Do NOT use prices from training data — stocks may have split (e.g. NVDA 10:1 in June 2024). [VERIFIED] values are from live data and MUST be used exactly.")
                parts.append("\n".join(lines))
            else:
                # No cache — fetch top 5 stocks only (fast)
                from nq_api.universe import UNIVERSE_BY_MARKET
                top_tickers = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])[:5]
                lines = [f"NeuralQuant {target_market} — Quick scan (live prices):"]
                for t in top_tickers:
                    fund = _fetch_one(t, target_market, fast_pe=False)
                    if fund.get("_is_real"):
                        price = fund.get("current_price")
                        chg = fund.get("change_pct", 0)
                        # FMP batch-quote fallback
                        if not price:
                            fmp_fb = (fmp_prices.get(t)
                                      or fmp_prices.get(f"{t}.NS")
                                      or fmp_prices.get(f"{t}.BO")
                                      or {})
                            if fmp_fb.get("price"):
                                price = fmp_fb["price"]
                                chg = fmp_fb.get("change_pct", 0) or chg
                        pe = fund.get("pe_ttm")
                        cur = "Rs." if target_market == "IN" else "$"
                        price_str = f"{cur}{price:,.2f} ({chg:+.1f}%) [VERIFIED]" if price else "N/A"
                        pe_str = f"P/E={pe:.1f} [VERIFIED]" if pe else ""
                        lines.append(f"  {t}: {price_str} | {pe_str}")
                lines.append("NOTE: Full screener data not cached. Showing top 5 with live prices.")
                parts.append("\n".join(lines))

        # Fetch specific stock data with live prices (fast: 1-3 calls, ~5s)
        if in_universe_tickers:
            from datetime import date as _date
            today_str = _date.today().strftime("%B %d, %Y")
            lines = [f"CRITICAL — LIVE MARKET DATA AS OF {today_str} — USE THESE EXACT PRICES, NOT YOUR TRAINING DATA:"]
            cached_all = score_cache.read_top(target_market, 50, max_age_seconds=300)
            if not cached_all:
                cached_all = score_cache.read_top(target_market, 50, max_age_seconds=86400)
            if not cached_all:
                cached_all = score_cache.read_top(target_market, 50, max_age_seconds=999999999)
            cache_map = {r.get("ticker"): r for r in cached_all} if cached_all else {}
            for t in in_universe_tickers[:5]:
                fund = _fetch_one(t, target_market, fast_pe=False)
                cached_row = cache_map.get(t, {})
                sc = int(cached_row.get("composite_score", 0.5) * 10) if cached_row else "N/A"
                price = fund.get("current_price")
                chg = fund.get("change_pct", 0)
                # FMP batch-quote fallback — critical for IN stocks where yfinance fails on cloud IPs
                if not price:
                    fmp_fb = (fmp_prices.get(t)
                              or fmp_prices.get(f"{t}.NS")
                              or fmp_prices.get(f"{t}.BO")
                              or {})
                    if fmp_fb.get("price"):
                        price = fmp_fb["price"]
                        chg = fmp_fb.get("change_pct", 0) or chg
                        if fmp_fb.get("pe"):
                            fund["pe_ttm"] = fmp_fb["pe"]
                pe = fund.get("pe_ttm")
                pb = fund.get("pb_ratio")
                target = fund.get("analyst_target")
                rec = fund.get("analyst_rec", "")
                w52h = fund.get("week52_high")
                w52l = fund.get("week52_low")
                beta_val = fund.get("beta")
                mcap = fund.get("market_cap")
                eps = fund.get("eps_ttm")
                cur = "Rs." if target_market == "IN" else "$"
                # Build a very explicit data block the LLM cannot ignore
                # Use [ESTIMATE] for synthetic data, [VERIFIED] for real data
                synthetic_fields = fund.get("_is_synthetic", set())
                is_real = fund.get("_is_real", False)
                def _marker(field_name: str) -> str:
                    """Return [VERIFIED] for real data, [ESTIMATE] for synthetic defaults."""
                    return "[ESTIMATE]" if field_name in synthetic_fields else "[VERIFIED]"
                detail_parts = [f"ForeCast={sc}/10"]
                if price: detail_parts.append(f"CURRENT_PRICE={cur}{price:,.2f} {_marker('current_price')}")
                if chg: detail_parts.append(f"CHANGE={chg:+.1f}%")
                if pe: detail_parts.append(f"P/E_TTM={pe:.1f} {_marker('pe_ttm')}")
                if eps: detail_parts.append(f"EPS={eps:.2f} {_marker('eps_ttm')}")
                if pb: detail_parts.append(f"P/B={pb:.2f} {_marker('pb_ratio')}")
                if beta_val: detail_parts.append(f"Beta={beta_val:.2f} {_marker('beta')}")
                if mcap:
                    mcap_marker = _marker('market_cap')
                    if cur == "Rs.":
                        if mcap >= 1e13: detail_parts.append(f"Mcap=₹{mcap/1e13:.1f}L Cr {mcap_marker}")
                        elif mcap >= 1e11: detail_parts.append(f"Mcap=₹{mcap/1e11:.1f}K Cr {mcap_marker}")
                        else: detail_parts.append(f"Mcap=₹{mcap/1e7:.0f} Cr {mcap_marker}")
                    else:
                        if mcap >= 1e12: detail_parts.append(f"Mcap=${mcap/1e12:.1f}T {mcap_marker}")
                        elif mcap >= 1e9: detail_parts.append(f"Mcap=${mcap/1e9:.1f}B {mcap_marker}")
                        else: detail_parts.append(f"Mcap=${mcap/1e6:.0f}M {mcap_marker}")
                if w52l and w52h: detail_parts.append(f"52wk={cur}{w52l:,.0f}-{cur}{w52h:,.0f} {_marker('week52')}")
                if target: detail_parts.append(f"AnalystTarget={cur}{target:,.0f}({rec}) {_marker('analyst_target')}")
                momentum = cached_row.get("momentum_percentile")
                quality = cached_row.get("quality_percentile")
                if momentum: detail_parts.append(f"Momentum={momentum:.0%}")
                if quality: detail_parts.append(f"Quality={quality:.0%}")
                lines.append(f"  {t}: {' | '.join(detail_parts)}")
            lines.append("")
            lines.append("⚠ MANDATORY: ALL values marked [VERIFIED] are REAL live data from yfinance for TODAY. Values marked [ESTIMATE] are approximations when real data is unavailable — treat them with lower confidence. P/E, Beta, Price, Market Cap change after earnings, splits, and volatility shifts. Your training data is WRONG for these values. ALWAYS quote the EXACT [VERIFIED] values shown above. Using different P/E or Beta values is a critical error.")
            parts.append("\n".join(lines))

        # Inject competitor comparison for specific stocks
        if in_universe_tickers and needs_stock_scores:
            try:
                comp_lines = ["Competitor comparison:"]
                for t in in_universe_tickers[:2]:
                    try:
                        info = _fetch_yf_info_cached(t)
                        if info.get("_cached_ok"):
                            sector = info.get("sector", "")
                            industry = info.get("industry", "")
                            if sector or industry:
                                comp_lines.append(f"  {t} sector: {sector} | industry: {industry}")
                    except Exception:
                        pass
                # Show nearby alternatives from cache
                cached_all = score_cache.read_top(target_market, 50, max_age_seconds=300)
                if not cached_all:
                    cached_all = score_cache.read_top(target_market, 50, max_age_seconds=86400)
                if not cached_all:
                    cached_all = score_cache.read_top(target_market, 50, max_age_seconds=999999999)
                if cached_all:
                    cache_map = {r.get("ticker"): r for r in cached_all}
                    for t in in_universe_tickers[:2]:
                        if t in cache_map:
                            row = cache_map[t]
                            rank = next((i for i, r in enumerate(cached_all) if r.get("ticker") == t), -1)
                            for pi in range(max(0, rank - 1), min(len(cached_all), rank + 2)):
                                if pi != rank and pi < len(cached_all):
                                    peer = cached_all[pi]
                                    peer_sc = int(peer.get("composite_score", 0.5) * 10)
                                    comp_lines.append(
                                        f"  Alternative: {peer['ticker']} (ForeCast {peer_sc}/10) "
                                        f"— Quality {peer.get('quality_percentile', 0):.0%} "
                                        f"Momentum {peer.get('momentum_percentile', 0):.0%}"
                                    )
                if len(comp_lines) > 1:
                    parts.append("\n".join(comp_lines))
            except Exception:
                pass

        # Dynamic fetch for out-of-universe NSE stocks
        if out_of_universe_words:
            dynamic_lines = ["Live data for requested stocks (dynamically fetched from NSE):"]
            found_any = False
            for word in out_of_universe_words:
                data = _fetch_dynamic_nse_stock(word)
                if data:
                    found_any = True
                    pe_str = f"P/E={data['pe_ttm']:.1f}" if data.get("pe_ttm") else "P/E=N/A"
                    target_str = f"Analyst target=Rs.{data['analyst_target']:.0f}" if data.get("analyst_target") else ""
                    chg_str = f"{data['change_pct']:+.2f}%" if data.get("change_pct") else ""
                    dynamic_lines.append(
                        f"  {data['longName']} ({data['symbol']}): "
                        f"Rs.{data['price']:.2f} {chg_str} | {pe_str} | {target_str}"
                    )
            if found_any:
                parts.append("\n".join(dynamic_lines))

    except Exception as exc:
        return f"[Platform data unavailable: {exc}]"

    return "\n\n".join(parts) if parts else None


async def _call_anthropic_with_retry(client, *, model: str, max_tokens: int, system: str, messages: list, tools: list | None = None, tool_choice: dict | None = None, timeout: float = 90.0):
    """Call Anthropic API with exponential-backoff retry on 5xx / connection / rate-limit errors."""
    kwargs: dict = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    last_exc = None
    for attempt in range(3):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(client.messages.create, **kwargs),
                timeout=timeout,
            )
        except anthropic.APIError as e:
            status = getattr(e, "status_code", None)
            if status and 500 <= status < 600:
                last_exc = e
                wait = 2 ** attempt
                log.warning("Anthropic API error %s (attempt %d/3), retrying in %ds...", status, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            raise
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            last_exc = e
            wait = 2 ** attempt
            log.warning("Anthropic connection/rate error (attempt %d/3), retrying in %ds...", attempt + 1, wait)
            await asyncio.sleep(wait)
            continue
    raise last_exc


@router.post("", response_model=QueryResponse)
async def run_nl_query(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
) -> QueryResponse:
    if not req.question or len(req.question.strip()) < 3:
        return QueryResponse(
            answer="Please enter a question (at least 3 characters).",
            data_sources=[],
            follow_up_questions=["What is the current Nifty level?", "Which Indian stocks rank highest?", "What is the Fed funds rate?"],
            route="REACT",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return QueryResponse(
            answer="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )

    # ── DART routing ──────────────────────────────────────────────────────────
    route = dart.classify_query(req.question, req.ticker)

    if route == "SNAP":
        return await dart.handle_snap(req)

    if route == "DEEP":
        return await dart.handle_deep(req)

    # REACT: existing LLM-powered logic with optimized context
    client, query_model = _query_client(api_key)

    # ── Detect ticker from question when not provided ───────────────────────
    effective_ticker = req.ticker
    if not effective_ticker:
        try:
            detected, _ = _detect_tickers_in_question(req.question, req.market or "US")
            if detected:
                effective_ticker = detected[0].replace(".NS", "").replace(".BO", "")
        except Exception:
            pass

    # ── Offload blocking I/O to thread pool ──────────────────────────────────
    # Each task gets a hard cap so the total context-build phase completes in
    # ≤ 25 s — leaving ample headroom for the 300 s Anthropic timeout.
    # Note: wait_for cancels the asyncio task on timeout but the underlying
    # thread may still run; this is a resource trade-off vs correct behaviour.
    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    enrichment, headlines, macro_ctx, platform_ctx, finnhub_news = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_enrichment, effective_ticker, req.market or 'US'), 45.0, {}),
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 45.0, None),
        _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, req.ticker, req.market or "US", 5), 8.0, []),
    )

    context_parts = [
        f"Today's date: {today}",
        f"User question: {req.question}",
    ]
    if macro_ctx:
        context_parts.append(macro_ctx)
    if platform_ctx:
        context_parts.append(platform_ctx)
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market or 'US'} market)")
        # Sector peer comparison
        try:
            from nq_api.universe import sector_of
            from nq_api.cache.score_cache import read_sector_median
            sector = sector_of(req.ticker, req.market or "US")
            if sector and sector != "Unknown":
                medians = read_sector_median(sector, req.market or "US")
                if medians:
                    lines = [f"Sector median ({sector}):"]
                    for k, v in medians.items():
                        if v is not None:
                            lines.append(f"  {k}: {round(v, 3)}")
                    context_parts.append("\n".join(lines))
        except Exception:
            pass
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")
    if finnhub_news:
        context_parts.append("Detailed news summaries (use these for deeper context):")
        for a in finnhub_news:
            summary_text = a.get("summary", "")
            title_text = a.get("title", "")
            source_text = a.get("source", "")
            if summary_text:
                context_parts.append(f"  • [{source_text}] {title_text}: {summary_text[:300]}")
    if enrichment:
        tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
        field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
            "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
            "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
            "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
            "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
            "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
            "insider_net_buy_ratio": "Insider Buy Ratio"}
        for k, label in field_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        # Analyst & earnings data from FMP (enriched in analyst.py)
        fmp_labels = {
            "analyst_consensus": "Analyst Consensus",
            "analyst_buy_pct": "Analyst Buy %",
            "analyst_target_avg": "Analyst Target Avg",
            "analyst_target_high": "Analyst Target High",
            "analyst_target_low": "Analyst Target Low",
            "analyst_revenue_est": "Revenue Estimate",
            "analyst_eps_est": "EPS Estimate",
            "analyst_count": "Analyst Count",
            "altman_z_score": "Altman Z-Score",
            "piotroski_score": "Piotroski Score",
            "insider_buys": "Insider Buys",
            "insider_sells": "Insider Sells",
            "insider_shares_bought": "Insider Shares Bought",
            "insider_shares_sold": "Insider Shares Sold",
            "dividend_latest": "Latest Dividend",
            "dividend_yield_pct": "Dividend Yield %",
            "next_earnings_date": "Next Earnings Date",
            "next_earnings_eps_est": "Earnings EPS Estimate",
            # OpenBB enrichment
            "iv_percentile": "IV Percentile",
            "put_call_ratio": "Put/Call Ratio",
            "implied_volatility": "Implied Volatility",
            "yield_curve_2y": "2Y Treasury Yield",
            "yield_curve_10y": "10Y Treasury Yield",
            "yield_curve_spread": "Yield Curve Spread",
        }
        for k, label in fmp_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        if len(tech_lines) > 1:
            context_parts.append("\n".join(tech_lines))

    user_msg = "\n".join(context_parts)

    try:
        # Build message list — keep up to 4 prior turns; truncate long messages
        messages = []
        for m in (req.history or [])[-4:]:
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        response = await _call_anthropic_with_retry(
            client,
            model=query_model,
            max_tokens=3000,
            system=_SYSTEM,
            messages=messages,
        )
        # Extract text from first text-type block (skip thinking blocks)
        raw = ""
        for block in response.content:
            if block.type == "text":
                raw = block.text
                break
        if not raw:
            raw = response.content[0].text if hasattr(response.content[0], "text") else ""

        # Skip second-pass reasoning — the system prompt already requires
        # "why this not that" reasoning. Second LLM call doubles latency.
        answer_text = raw

        return _parse_query_response(answer_text, route="REACT")
    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        return QueryResponse(
            answer="Query timed out — the AI took too long to respond. Try a shorter question.",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )
    except Exception as exc:
        return QueryResponse(
            answer=f"Query failed: {str(exc)[:200]}",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )


def _structured_from_markdown(raw: str, freeform_resp: QueryResponse, route: str, stock_summary: StockSummary | None = None) -> StructuredQueryResponse:
    """Convert freeform markdown LLM output into a rich StructuredQueryResponse.
    Called when JSON parsing fails — extracts verdict, metrics, scenarios, etc.
    from the markdown text so the frontend card components have real data."""
    # Extract verdict from text
    verdict = "HOLD"
    verdict_map = {"STRONG BUY": "STRONG BUY", "BUY": "BUY", "HOLD": "HOLD", "SELL": "SELL", "STRONG SELL": "STRONG SELL"}
    for v in verdict_map:
        if re.search(rf"\b{re.escape(v)}\b", raw, re.I):
            verdict = verdict_map[v]
            break

    # Extract metrics from markdown tables or inline data
    metrics: list[MetricItem] = []
    # Look for patterns like "P/E: 30.8" or "Momentum: 92%" or "| P/E | 30.8 |"
    metric_patterns = [
        (r"P/E[^|]*?(?:[:|]\s*)([\d.]+)", "P/E (TTM)", "Sector avg"),
        (r"Momentum[^|]*?(?:[:|]\s*)([\d.]+)%?", "Momentum", "50% avg"),
        (r"Quality[^|]*?(?:[:|]\s*)([\d.]+)%?", "Quality", "50% avg"),
        (r"ForeCast[^|]*?(?:[:|]\s*)([\d.]+)/10", "ForeCast Score", "5/10 avg"),
        (r"Value[^|]*?(?:[:|]\s*)([\d.]+)%?", "Value", "50% avg"),
        (r"Beta[^|]*?(?:[:|]\s*)([\d.]+)", "Beta", "1.0 avg"),
    ]
    for pattern, name, benchmark in metric_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            val = m.group(1)
            try:
                float(val)  # validate it's a number
                status = "positive" if name in ("Momentum", "Quality", "Value", "ForeCast Score") and float(val) > 50 else "neutral"
                if name == "P/E (TTM)":
                    status = "negative" if float(val) > 35 else "positive"
                metrics.append(MetricItem(name=name, value=val, benchmark=benchmark, status=status))
            except ValueError:
                pass

    # Extract scenarios (Bear/Base/Bull)
    scenarios: list[ScenarioItem] = []
    scenario_patterns = [
        (r"(?:🐻\s*)?Bear[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\-?\d+%)[^()]*?(?:\(([^)]+)\))?", "Bear", 0.20),
        (r"(?:📊\s*)?Base[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\+?\d+%)[^()]*?(?:\(([^)]+)\))?", "Base", 0.50),
        (r"(?:🐂\s*)?Bull[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\+?\d+%)[^()]*?(?:\(([^)]+)\))?", "Bull", 0.30),
    ]
    for pattern, label, prob in scenario_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            target = m.group(1) or ""
            thesis = m.group(2) or ""
            scenarios.append(ScenarioItem(label=label, probability=prob, target=target, thesis=thesis))

    # Extract reasoning sections
    why_this = ""
    why_not_alt = ""
    edge_summary = ""
    second_best = "N/A"
    confidence_gap = "N/A"

    # Look for "Why" sections
    why_match = re.search(r"(?:Why|Why This|Why GOOGL)[^:]*?:\s*(.+?)(?=\n\n|\n(?:Why Not|vs|Bear|Bull|Base|Risk|Scenario|Price|Stop|$))", raw, re.I | re.S)
    if why_match:
        why_this = why_match.group(1).strip()[:300]

    # Look for "Why not" / "vs" / comparison sections
    why_not_match = re.search(r"(?:Why Not|vs\.?|versus|Alternative|compared to)[^:]*?:\s*(.+?)(?=\n\n|\n(?:Why|Bear|Bull|Base|Risk|Scenario|Price|Stop|Macro|$))", raw, re.I | re.S)
    if why_not_match:
        why_not_alt = why_not_match.group(1).strip()[:300]

    # Extract "vs" comparisons for second_best
    vs_match = re.search(r"vs\.?\s+([A-Z]{1,5}(?:\.NS)?)", raw)
    if vs_match:
        second_best = vs_match.group(1)

    # Extract comparison data from tables or inline
    comparisons: list[ComparisonItem] = []
    # Look for "ours vs theirs" patterns or table rows with comparisons
    comp_matches = re.finditer(r"(?:vs\.?|versus|compared to)\s+([A-Z]{1,5}(?:\.NS)?)[^:]*?(?:P/E|momentum|quality|score|value)[^)]*?\)", raw, re.I)
    seen_tickers = set()
    for cm in comp_matches:
        ticker = cm.group(1)
        if ticker not in seen_tickers:
            comparisons.append(ComparisonItem(
                ticker=ticker, metric="Composite", ours="Higher", theirs="Lower",
                edge="Superior ForeCast score and factor alignment"
            ))
            seen_tickers.add(ticker)

    # Build reasoning from extracted data
    if not why_this:
        # Fallback: use first 2-3 sentences of the answer
        first_sentences = re.split(r'[.!?]\s', freeform_resp.answer)[:3]
        why_this = '. '.join(first_sentences) if first_sentences else "See summary for details"

    if not why_not_alt:
        why_not_alt = "Alternative stocks evaluated but this pick showed superior factor alignment"

    if not edge_summary:
        edge_summary = "Selected based on strongest combined score and factor alignment"

    # Determine confidence from verdict
    confidence = {"STRONG BUY": 85, "BUY": 70, "HOLD": 50, "SELL": 70, "STRONG SELL": 85}.get(verdict, 50)

    # Extract timeframe from question
    timeframe = "Medium-term"
    q_lower = (freeform_resp.answer + " ").lower()
    if any(w in q_lower for w in ["next month", "1 month", "short term", "short-term", "weeks"]):
        timeframe = "Short-term"
    elif any(w in q_lower for w in ["long term", "long-term", "year", "years", "5 year"]):
        timeframe = "Long-term"

    # Strip markdown so the summary <p> doesn't render raw `#` and `**` chars.
    clean_summary = re.sub(r"^#+\s*", "", freeform_resp.answer, flags=re.M)  # strip headers
    clean_summary = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_summary)          # strip bold
    clean_summary = re.sub(r"^[-*]\s+", "• ", clean_summary, flags=re.M)      # bullets
    clean_summary = re.sub(r"^---+$", "", clean_summary, flags=re.M)          # rules
    clean_summary = re.sub(r"\n{3,}", "\n\n", clean_summary).strip()

    return StructuredQueryResponse(
        verdict=verdict,
        confidence=confidence,
        timeframe=timeframe,
        summary=clean_summary[:800],
        metrics=metrics[:6],
        reasoning=ReasoningBlock(
            why_this=why_this,
            why_not_alt=why_not_alt,
            edge_summary=edge_summary,
            second_best=second_best,
            confidence_gap=confidence_gap,
        ),
        scenarios=scenarios[:3],
        allocations=[],
        comparisons=comparisons[:4],
        data_sources=freeform_resp.data_sources,
        follow_up_questions=freeform_resp.follow_up_questions,
        route=freeform_resp.route,
        stock_summary=stock_summary,
    )


def _enrich_snap_structured(req: QueryRequest) -> tuple[list, ReasoningBlock, str]:
    """Build metrics and reasoning from score cache for SNAP responses."""
    from nq_api.cache import score_cache
    from nq_api.score_builder import _score_to_1_10

    ticker = (req.ticker or "").upper()
    market = req.market or "US"
    metrics: list[MetricItem] = []
    verdict = "HOLD"
    why_this = "Based on NeuralQuant score data"
    why_not_alt = "Alternative not scored"
    edge_summary = "Score-based assessment"
    second_best = "N/A"
    confidence_gap = "N/A"

    if not ticker:
        return metrics, ReasoningBlock(
            why_this=why_this, why_not_alt=why_not_alt,
            edge_summary=edge_summary, second_best=second_best, confidence_gap=confidence_gap,
        ), verdict

    cached = None
    try:
        cached = score_cache.read_one(ticker, market, 86400) or score_cache.read_one(ticker, market, 999999999)
    except Exception:
        pass

    if cached:
        score = cached.get("composite_score", 0.5)
        score_10 = _score_to_1_10(float(score)) if score is not None else 5
        momentum = cached.get("momentum_percentile")
        quality = cached.get("quality_percentile")
        value = cached.get("value_percentile")
        pe = cached.get("pe_ttm")
        pb = cached.get("pb_ratio")

        if score is not None:
            metrics.append(MetricItem(name="ForeCast Score", value=f"{score_10}/10", benchmark="5/10 avg", status="positive" if score_10 >= 6 else "negative"))
        if momentum is not None:
            metrics.append(MetricItem(name="Momentum", value=f"{float(momentum)*100:.0f}%", benchmark="50% avg", status="positive" if float(momentum) >= 0.5 else "negative"))
        if quality is not None:
            metrics.append(MetricItem(name="Quality", value=f"{float(quality)*100:.0f}%", benchmark="50% avg", status="positive" if float(quality) >= 0.5 else "negative"))
        if value is not None:
            metrics.append(MetricItem(name="Value", value=f"{float(value)*100:.0f}%", benchmark="50% avg", status="positive" if float(value) >= 0.5 else "negative"))
        if pe is not None:
            metrics.append(MetricItem(name="P/E (TTM)", value=f"{float(pe):.1f}", benchmark="Sector avg", status="positive" if float(pe) < 25 else "negative"))
        if pb is not None:
            metrics.append(MetricItem(name="P/B", value=f"{float(pb):.2f}", benchmark="Sector avg", status="positive" if float(pb) < 3 else "negative"))

        if score_10 >= 7:
            verdict = "BUY"
        elif score_10 >= 5:
            verdict = "HOLD"
        else:
            verdict = "SELL"

        # Build richer reasoning from cache data
        data_points = []
        if score_10:
            data_points.append(f"ForeCast {score_10}/10")
        if momentum is not None:
            data_points.append(f"momentum {float(momentum)*100:.0f}%")
        if quality is not None:
            data_points.append(f"quality {float(quality)*100:.0f}%")
        why_this = f"Score-driven assessment: {', '.join(data_points[:3])}" if data_points else "Based on NeuralQuant score data"

        # Find nearest competitor in cache for comparison
        try:
            from nq_api.universe import US_DEFAULT, IN_DEFAULT
            universe = IN_DEFAULT if market == "IN" else US_DEFAULT
            # Try up to 8 nearby tickers to find a competitor with cached data
            for alt_ticker in universe[:8]:
                if alt_ticker == ticker:
                    continue
                alt_cached = score_cache.read_one(alt_ticker, market, 86400)
                if alt_cached and alt_cached.get("composite_score") is not None:
                    alt_score = float(alt_cached["composite_score"])
                    alt_10 = _score_to_1_10(alt_score)
                    second_best = alt_ticker
                    why_not_alt = f"{alt_ticker} scores {alt_10}/10 — selected stock has {'higher' if score_10 >= alt_10 else 'comparable'} composite score"
                    confidence_gap = f"ForeCast {score_10} vs {alt_10}, {'+' if score_10 >= alt_10 else ''}{score_10 - alt_10} edge"
                    edge_summary = f"ForeCast {score_10}/10 vs {alt_ticker}'s {alt_10}/10"
                    break
        except Exception:
            pass

    return metrics, ReasoningBlock(
        why_this=why_this, why_not_alt=why_not_alt,
        edge_summary=edge_summary, second_best=second_best, confidence_gap=confidence_gap,
    ), verdict


def _parse_query_response(raw: str, route: str = "REACT") -> QueryResponse:
    # Strip markdown bold around section headers (Claude occasionally wraps
    # `ANSWER:` as `**ANSWER:**`), which previously leaked `**` into the
    # answer text and data_sources list. Normalize BEFORE regex splits.
    norm = re.sub(r"\*\*\s*(ANSWER|DATA_SOURCES|FOLLOW_UP)\s*:\s*\*\*", r"\1:", raw, flags=re.I)

    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|\Z)", norm, re.I | re.S | re.M)
    answer = answer_match.group(1).strip() if answer_match else norm[:8000]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|\Z)", norm, re.I | re.S | re.M)
    sources_raw = sources_match.group(1) if sources_match else ""
    # Strip any leftover `**` from individual source tokens and drop empties.
    sources = [
        re.sub(r"\*+", "", s).strip()
        for s in sources_raw.split(",")
    ]
    sources = [s for s in sources if s and s not in ("-", "*")]

    followup_match = re.search(r"FOLLOW_UP:(.*)", norm, re.I | re.S | re.M)
    followups: list[str] = []
    if followup_match:
        followups = [
            re.sub(r"^[-*•]\s*|\d+\.\s*", "", q.strip()).strip().strip("*").strip()
            for q in followup_match.group(1).strip().splitlines()
            if q.strip() and q.strip() not in ("-", "*", "•")
        ]
        followups = [q for q in followups if q]

    return QueryResponse(
        answer=answer[:8000],
        data_sources=sources[:5],
        follow_up_questions=followups[:3],
        route=route,
    )


def _extract_json_from_llm(text: str) -> dict | None:
    """Try to extract a JSON object from LLM output (may be wrapped in markdown or garbled)."""
    import json as _json

    cleaned = text.strip()

    # Strategy 1: Direct parse (clean JSON)
    try:
        return _json.loads(cleaned)
    except (_json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Remove markdown code fences (```json ... ```)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        try:
            return _json.loads(fence_match.group(1))
        except (_json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Find JSON object boundaries (first { to last })
    first_brace = cleaned.find("{")
    if first_brace >= 0:
        # Walk through string counting braces to find matching close
        depth = 0
        for i in range(first_brace, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _json.loads(cleaned[first_brace : i + 1])
                    except (_json.JSONDecodeError, ValueError):
                        break

    # Strategy 4: Aggressive — strip all markdown, find anything JSON-like
    aggressive = re.sub(r"```(?:json)?\s*", "", cleaned)
    aggressive = re.sub(r"\s*```", "", aggressive)
    aggressive = re.sub(r"\*\*[^*]+\*\*", "", aggressive)  # remove markdown bold
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, aggressive)
        if match:
            try:
                return _json.loads(match.group())
            except (_json.JSONDecodeError, ValueError):
                continue

    # Strategy 5: Truncated JSON — close open braces/brackets and retry
    # Common when max_tokens is hit mid-response
    first_brace = cleaned.find("{")
    if first_brace >= 0:
        snippet = cleaned[first_brace:]
        # Count unclosed braces and brackets
        open_braces = snippet.count("{") - snippet.count("}")
        open_brackets = snippet.count("[") - snippet.count("]")
        if open_braces > 0 or open_brackets > 0:
            repaired = snippet + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            try:
                return _json.loads(repaired)
            except (_json.JSONDecodeError, ValueError):
                pass
    return None


@router.post("/v2", response_model=StructuredQueryResponse)
async def run_nl_query_v2(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
) -> StructuredQueryResponse:
    """Structured output version of /query. Returns typed JSON with reasoning blocks."""
    from pydantic import ValidationError
    import json

    if not req.question or len(req.question.strip()) < 3:
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=0,
            timeframe="Medium-term",
            summary="Please enter a question (at least 3 characters).",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            follow_up_questions=["What is the current Nifty level?", "Which Indian stocks rank highest?"],
            route="REACT",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=0,
            timeframe="Medium-term",
            summary="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route="REACT",
        )

    # ── DART routing ── (SNAP disabled — force REACT for full structured detail)
    classified = dart.classify_query(req.question, req.ticker)
    route = "REACT" if classified == "SNAP" else classified

    # REACT or DEEP: use LLM with structured prompt
    client, query_model = _query_client(api_key)

    # ── Detect ticker from question when not provided ───────────────────────
    effective_ticker_v2 = req.ticker
    if not effective_ticker_v2:
        try:
            detected, _ = _detect_tickers_in_question(req.question, req.market or "US")
            if detected:
                effective_ticker_v2 = detected[0].replace(".NS", "").replace(".BO", "")
        except Exception:
            pass

    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    headlines, macro_ctx, platform_ctx, finnhub_news, enrichment = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 22.0, None),
        _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, req.ticker, req.market or "US", 5), 8.0, []),
        _timed(asyncio.to_thread(_fetch_enrichment, effective_ticker_v2, req.market or 'US'), 25.0, {}),
    )

    context_parts = [
        f"Today's date: {today}",
        f"User question: {req.question}",
    ]
    if macro_ctx:
        context_parts.append(macro_ctx)
    if platform_ctx:
        context_parts.append(platform_ctx)
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market or 'US'} market)")
        # Sector peer comparison
        try:
            from nq_api.universe import sector_of
            from nq_api.cache.score_cache import read_sector_median
            sector = sector_of(req.ticker, req.market or "US")
            if sector and sector != "Unknown":
                medians = read_sector_median(sector, req.market or "US")
                if medians:
                    lines = [f"Sector median ({sector}):"]
                    for k, v in medians.items():
                        if v is not None:
                            lines.append(f"  {k}: {round(v, 3)}")
                    context_parts.append("\n".join(lines))
        except Exception:
            pass
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")
    if finnhub_news:
        context_parts.append("Detailed news summaries (use these for deeper context):")
        for a in finnhub_news:
            summary_text = a.get("summary", "")
            title_text = a.get("title", "")
            source_text = a.get("source", "")
            if summary_text:
                context_parts.append(f"  • [{source_text}] {title_text}: {summary_text[:300]}")
    if enrichment:
        tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
        field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
            "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
            "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
            "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
            "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
            "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
            "insider_net_buy_ratio": "Insider Buy Ratio"}
        for k, label in field_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        # Analyst & earnings data from FMP (enriched in analyst.py)
        fmp_labels = {
            "analyst_consensus": "Analyst Consensus",
            "analyst_buy_pct": "Analyst Buy %",
            "analyst_target_avg": "Analyst Target Avg",
            "analyst_target_high": "Analyst Target High",
            "analyst_target_low": "Analyst Target Low",
            "analyst_revenue_est": "Revenue Estimate",
            "analyst_eps_est": "EPS Estimate",
            "analyst_count": "Analyst Count",
            "altman_z_score": "Altman Z-Score",
            "piotroski_score": "Piotroski Score",
            "insider_buys": "Insider Buys",
            "insider_sells": "Insider Sells",
            "insider_shares_bought": "Insider Shares Bought",
            "insider_shares_sold": "Insider Shares Sold",
            "dividend_latest": "Latest Dividend",
            "dividend_yield_pct": "Dividend Yield %",
            "next_earnings_date": "Next Earnings Date",
            "next_earnings_eps_est": "Earnings EPS Estimate",
            # OpenBB enrichment
            "iv_percentile": "IV Percentile",
            "put_call_ratio": "Put/Call Ratio",
            "implied_volatility": "Implied Volatility",
            "yield_curve_2y": "2Y Treasury Yield",
            "yield_curve_10y": "10Y Treasury Yield",
            "yield_curve_spread": "Yield Curve Spread",
        }
        for k, label in fmp_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        if len(tech_lines) > 1:
            context_parts.append("\n".join(tech_lines))

    user_msg = "\n".join(context_parts)

    # Reinforce: if platform_ctx contains CURRENT_PRICE, add an extra reminder at the end
    if platform_ctx and "CURRENT_PRICE" in platform_ctx:
        user_msg += "\n\nREMINDER: ALL values marked [VERIFIED] above are TODAY's live market data (yfinance). You MUST use EXACT P/E, Beta, Price, and Market Cap values shown — your training data has WRONG values for stocks with recent earnings changes or splits (e.g. NVDA P/E is ~42x NOT ~28x, Beta is ~2.2 NOT ~0.9). Wrong financial data causes real investment losses."

    # Load persistent conversation memory if session_key provided
    user_id = str(user.id) if user else None
    persistent_history = []
    if user_id and req.session_key:
        persistent_history = await asyncio.to_thread(
            _load_conversation_history, user_id, req.session_key, limit=10
        )
        if persistent_history:
            context_parts.insert(0, f"[Previous conversation context ({len(persistent_history)} turns)]")
            user_msg = "\n".join(context_parts)

    try:
        messages = []
        # Merge client-provided history, persistent history, and current message
        seen_content = set()
        all_history = list(req.history or [])[-4:]
        for ph in persistent_history:
            all_history.append(ConversationMessage(role=ph["role"], content=ph["content"]))
        for m in all_history[-8:]:  # max 8 total history turns
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            if content not in seen_content:
                seen_content.add(content)
                messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        # ── Clarification check (ask follow-up before answering) ──────────
        detected_tickers_v2 = []
        if not req.ticker:
            try:
                detected_tickers_v2, _ = _detect_tickers_in_question(req.question, req.market or "US")
            except Exception:
                pass
        else:
            detected_tickers_v2 = [req.ticker]

        if req.clarification_answers:
            # Inject user's clarification answers into the prompt
            answers_text = "\n".join(f"• {a}" for a in req.clarification_answers)
            user_msg += f"\n\n[USER CONTEXT] User clarified their needs:\n{answers_text}"
            messages[-1] = {"role": "user", "content": user_msg}

        clarification = _needs_clarification(req.question, detected_tickers_v2, route, req.profile)
        # Build dynamic clarification context with live market data
        _fmp_ctx = _fetch_fmp_context_for_clarification(
            detected_tickers_v2[0] if detected_tickers_v2 else "",
            req.market or "US",
        ) if detected_tickers_v2 else None
        _clarification_qs = _generate_clarification_questions(
            req.question, detected_tickers_v2, req.market or "US", route,
            fmp_context=_fmp_ctx,
        )
        _ctx_str = "Answer these questions so I can give you a personalized response."
        if _fmp_ctx and detected_tickers_v2:
            _ctx_parts = []
            cur = "₹" if (req.market or "US") == "IN" else "$"
            if _fmp_ctx.get("price"):
                _ctx_parts.append(f"Price: {cur}{_fmp_ctx['price']:,.2f}")
            if _fmp_ctx.get("pe"):
                _ctx_parts.append(f"P/E: {_fmp_ctx['pe']:.1f}x")
            if _fmp_ctx.get("analyst_consensus"):
                _ctx_parts.append(f"Analysts: {_fmp_ctx['analyst_consensus'].title()}")
            if _fmp_ctx.get("dividend_yield"):
                _ctx_parts.append(f"Yield: {_fmp_ctx['dividend_yield']:.1f}%")
            if _fmp_ctx.get("next_earnings_date"):
                _ctx_parts.append(f"Earnings: {_fmp_ctx['next_earnings_date']}")
            if _ctx_parts:
                _ctx_str = f"Live data for {detected_tickers_v2[0]}: {' | '.join(_ctx_parts)}"

        if clarification and not req.clarification_answers:
            return StructuredQueryResponse(
                verdict="HOLD",
                confidence=0,
                timeframe="N/A",
                summary="I'd like to understand your needs better before answering.",
                reasoning=ReasoningBlock(
                    why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                    second_best="N/A", confidence_gap="N/A",
                ),
                clarification_needed=True,
                clarification_questions=_clarification_qs,
                clarification_context=_ctx_str,
                route="REACT",
                data_sources=["NeuralQuant Clarification"],
                follow_up_questions=[],
                metrics=[],
                scenarios=[],
                allocations=[],
                comparisons=[],
            )

        # Portfolio intent detection and prompt injection
        portfolio_intent = _is_portfolio_intent(req.question)

        # If clarification needed, show it before profiler
        # (clarification already returned above if True and no clarification_answers)

        # Check if profile needed for portfolio questions
        # Only show profiler if clarification was NOT needed (or was already answered)
        if portfolio_intent and not req.profile and not clarification:
            return StructuredQueryResponse(
                verdict="HOLD",
                confidence=0,
                timeframe="Medium-term",
                summary="Before I build your portfolio, I need to understand your goals.",
                reasoning=ReasoningBlock(
                    why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                    second_best="N/A", confidence_gap="N/A",
                ),
                profiler_needed=True,
                route="REACT",
                data_sources=["NeuralQuant Profiler"],
                follow_up_questions=[],
                metrics=[],
                scenarios=[],
                allocations=[],
                comparisons=[],
            )

        system_prompt = _SYSTEM_STRUCTURED
        if portfolio_intent:
            system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
            snap = _build_market_snapshot(req.market or "US")
            if snap:
                user_msg = user_msg + "\n\n" + snap
            # Inject profile if present
            if req.profile:
                user_msg = user_msg + "\n\n" + _build_profile_prompt(req.profile)
            messages[-1]["content"] = user_msg

        # Inject profile context for all queries (not just portfolio)
        if req.profile and not portfolio_intent:
            user_msg = user_msg + "\n\n[INVESTOR PROFILE CONTEXT] " + _build_profile_prompt(req.profile)
            messages[-1]["content"] = user_msg

        # Force tool_use for guaranteed structured output (no markdown leakage).
        response = await _call_anthropic_with_retry(
            client,
            model=query_model,
            max_tokens=8000,
            system=system_prompt,
            tools=[_STRUCTURED_TOOL],
            tool_choice={"type": "tool", "name": _STRUCTURED_TOOL["name"]},
            messages=messages,
        )

        parsed = _extract_tool_use_input(response)
        if parsed:
            try:
                parsed.setdefault("route", route)
                parsed.setdefault("data_sources", [])
                parsed.setdefault("follow_up_questions", [])
                if "reasoning" not in parsed:
                    parsed["reasoning"] = {
                        "why_this": "Based on the highest ForeCast Score and strongest factor alignment",
                        "why_not_alt": "Alternative had lower scores on key factors",
                        "edge_summary": "Selected stock leads on composite score and factor quality",
                        "second_best": "N/A",
                        "confidence_gap": "N/A",
                    }
                # Portfolio validation post-processing
                if portfolio_intent:
                    parsed["is_portfolio_response"] = True
                    if not parsed.get("sebi_disclaimer") or "SEBI" not in parsed.get("sebi_disclaimer", "").upper():
                        parsed["sebi_disclaimer"] = (
                            "This is AI-generated investment research, not SEBI-registered investment advice. "
                            "Please consult a certified financial advisor before investing."
                        )
                    if not parsed.get("portfolio_stocks") and parsed.get("allocations"):
                        parsed["portfolio_stocks"] = []
                        for a in parsed["allocations"]:
                            ticker = a.get("ticker", "")
                            weight = a.get("weight", 0)
                            rationale = a.get("rationale", "")
                            entry_match = re.search(r'Entry[:\s]+([^;\n]+)', rationale)
                            entry_price = entry_match.group(1).strip() if entry_match else None
                            target_match = re.search(r'Target[:\s]+([^;\n]+)', rationale)
                            target_price = target_match.group(1).strip() if target_match else None
                            stop_match = re.search(r'Stop[:\s]+([^;\n]+)', rationale)
                            stop_loss = stop_match.group(1).strip() if stop_match else None
                            parsed["portfolio_stocks"].append({
                                "ticker": ticker,
                                "allocation_pct": weight,
                                "rationale": rationale,
                                "entry_price": entry_price,
                                "target_price": target_price,
                                "stop_loss": stop_loss,
                            })
                    if not parsed.get("scenario_analysis") and parsed.get("scenarios"):
                        parsed["scenario_analysis"] = []
                        scenario_colors = {"Bull": "#22c55e", "Base": "#6366f1", "Bear": "#ef4444"}
                        for s in parsed["scenarios"]:
                            label = s.get("label", "")
                            prob = int(s.get("probability", 0) * 100)
                            parsed["scenario_analysis"].append({
                                "label": label,
                                "probability_pct": prob,
                                "outcome": s.get("target", ""),
                                "description": s.get("thesis", ""),
                                "color": scenario_colors.get(label, "#6366f1"),
                            })
                    if not parsed.get("allocation_breakdown") and parsed.get("allocations"):
                        parsed["allocation_breakdown"] = []
                        for a in parsed["allocations"]:
                            parsed["allocation_breakdown"].append({
                                "label": a.get("ticker", ""),
                                "percentage": a.get("weight", 0),
                                "rationale": a.get("rationale", ""),
                            })
                    if not parsed.get("market_context"):
                        parsed["market_context"] = []
                    if not parsed.get("action_prompts"):
                        parsed["action_prompts"] = []
                    # Validate portfolio stock data against real yfinance
                    if parsed.get("portfolio_stocks"):
                        corrected_stocks, corrected_summary, pf_corrections = await asyncio.to_thread(
                            _validate_portfolio_stocks, parsed["portfolio_stocks"], req.market or "US", parsed.get("summary", "")
                        )
                        parsed["portfolio_stocks"] = corrected_stocks
                        if corrected_summary != parsed.get("summary", ""):
                            parsed["summary"] = corrected_summary
                        if pf_corrections and parsed.get("summary"):
                            parsed["summary"] += f" [Data verified: {'; '.join(pf_corrections)}]"
                        # Fill live prices for entry/target/stop_loss
                        filled_stocks, fill_notes = await asyncio.to_thread(
                            _validate_and_fill_portfolio_prices, parsed["portfolio_stocks"], req.market or "US"
                        )
                        parsed["portfolio_stocks"] = filled_stocks
                        if fill_notes and parsed.get("summary"):
                            parsed["summary"] += f" [Live prices verified: {'; '.join(fill_notes)}]"
                result = StructuredQueryResponse(**parsed)
                # Validate LLM metrics against injected [VERIFIED] data
                verified = _extract_verified_values(platform_ctx)
                result = _validate_response_metrics(result, verified)
                # Attach stock summary from enrichment data
                result.stock_summary = _build_stock_summary(effective_ticker_v2, req.market or "US", enrichment, platform_ctx)
                # Persist conversation turn (best-effort)
                if user_id and req.session_key:
                    await asyncio.to_thread(
                        _save_conversation_turn, user_id, req.session_key,
                        "user", req.question, req.ticker, req.market or "US"
                    )
                    await asyncio.to_thread(
                        _save_conversation_turn, user_id, req.session_key,
                        "assistant", result.summary, req.ticker, req.market or "US"
                    )
                return result
            except (ValidationError, Exception) as e:
                log.warning("Tool-use structured output validation failed: %s", e)

        # Extreme fallback: tool_use was rejected — salvage from any text block
        raw = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw = block.text
                break
        freeform_resp = _parse_query_response(raw, route)
        result = _structured_from_markdown(raw, freeform_resp, route, _build_stock_summary(effective_ticker_v2, req.market or "US", enrichment, platform_ctx))
        # Validate LLM metrics against injected [VERIFIED] data
        verified = _extract_verified_values(platform_ctx)
        result = _validate_response_metrics(result, verified)
        return result

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        return StructuredQueryResponse(
            verdict="HOLD", confidence=0, timeframe="Medium-term",
            summary="Query timed out — the AI took too long to respond. Try a shorter question.",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route=route,
        )
    except Exception as exc:
        return StructuredQueryResponse(
            verdict="HOLD", confidence=0, timeframe="Medium-term",
            summary=f"Query failed: {str(exc)[:200]}",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route=route,
        )


# ── SSE streaming variant of /v2 ──────────────────────────────────────────────

_PHASE_LABELS = {
    "classify":  "Understanding your question",
    "news":      "Scanning latest market headlines",
    "macro":     "Loading macro context (VIX, SPX, yields, CPI)",
    "platform":  "Reading NeuralQuant ForeCast scores + factor data",
    "context":   "Assembling reasoning context",
    "prompt":    "Sending data to AI (Claude Sonnet 4.6)",
    "thinking":  "AI is reasoning over the data",
    "generate":  "AI is generating structured response",
    "parse":     "Parsing AI output into rich cards",
    "render":    "Building NeuralQuant ForeCast",
}


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic tool definition for guaranteed structured output.
# Using `tool_use` instead of free-form prompting forces the model to emit
# arguments that match the JSON schema exactly — no markdown, no parse failures.
# Reference: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
# ──────────────────────────────────────────────────────────────────────────────
_STRUCTURED_TOOL = {
    "name": "respond_with_neuralquant_forecast",
    "description": (
        "Respond to the user's stock or portfolio question with a detailed "
        "NeuralQuant ForeCast structured analysis. ALWAYS use this tool — "
        "never reply with plain text or markdown."
    ),
    "input_schema": {
        "type": "object",
        "required": ["verdict", "confidence", "timeframe", "summary", "reasoning"],
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
                "description": "Top-line investment verdict.",
            },
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Conviction level 0-100.",
            },
            "timeframe": {
                "type": "string",
                "enum": ["Short-term", "Medium-term", "Long-term"],
            },
            "summary": {
                "type": "string",
                "description": (
                    "4–8 sentence detailed plain-text summary. NO markdown headers, "
                    "NO `#`, NO `**`, NO bullets. Include specific numbers (prices, P/E, "
                    "scores, percentages). For portfolio questions, mention each stock with "
                    "allocation %. This is the user's primary read."
                ),
            },
            "metrics": {
                "type": "array",
                "description": "4+ metric cards. P/E, momentum, quality, ForeCast score, etc.",
                "items": {
                    "type": "object",
                    "required": ["name", "value", "status"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "benchmark": {"type": "string"},
                        "status": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    },
                },
            },
            "reasoning": {
                "type": "object",
                "required": ["why_this", "why_not_alt", "edge_summary"],
                "properties": {
                    "why_this": {
                        "type": "string",
                        "description": "2-4 sentences with 3+ specific data points (P/E, momentum, score, etc.)",
                    },
                    "why_not_alt": {
                        "type": "string",
                        "description": "2-3 sentences naming the runner-up stock and why it's inferior with data.",
                    },
                    "edge_summary": {
                        "type": "string",
                        "description": "One-line decisive edge.",
                    },
                    "second_best": {"type": "string", "description": "Name of runner-up stock"},
                    "confidence_gap": {"type": "string", "description": "Quantified advantage"},
                },
            },
            "scenarios": {
                "type": "array",
                "description": "Bear / Base / Bull scenarios with target + thesis.",
                "items": {
                    "type": "object",
                    "required": ["label", "probability", "target", "thesis"],
                    "properties": {
                        "label": {"type": "string", "enum": ["Bear", "Base", "Bull"]},
                        "probability": {"type": "number", "minimum": 0, "maximum": 1},
                        "target": {"type": "string", "description": "Specific price or %"},
                        "thesis": {"type": "string", "description": "Specific trigger / catalyst"},
                    },
                },
            },
            "allocations": {
                "type": "array",
                "description": "Portfolio allocations (for invest/portfolio questions).",
                "items": {
                    "type": "object",
                    "required": ["ticker", "weight", "rationale"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "weight": {"type": "number", "minimum": 0, "maximum": 100},
                        "rationale": {"type": "string", "description": "2-sentence rationale with data"},
                        "why_not_alt": {"type": "string", "description": "Name alt stock + what it lacks"},
                    },
                },
            },
            "comparisons": {
                "type": "array",
                "description": "Head-to-head metric comparisons vs alternative stock(s).",
                "items": {
                    "type": "object",
                    "required": ["ticker", "metric", "ours", "theirs", "edge"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "metric": {"type": "string"},
                        "ours": {"type": "string"},
                        "theirs": {"type": "string"},
                        "edge": {"type": "string"},
                    },
                },
            },
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3 suggested follow-up questions.",
            },
            "market_context": {
                "type": "array",
                "description": "Live market context cards for portfolio layout. Only set when is_portfolio_response=true.",
                "items": {
                    "type": "object",
                    "required": ["label", "value"],
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                        "change": {"type": "string"},
                        "sentiment": {"type": "string"},
                    },
                },
            },
            "allocation_breakdown": {
                "type": "array",
                "description": "Portfolio allocation segments. Must sum to 100%. Only set when is_portfolio_response=true.",
                "items": {
                    "type": "object",
                    "required": ["label", "percentage"],
                    "properties": {
                        "label": {"type": "string"},
                        "percentage": {"type": "number"},
                        "color": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                },
            },
            "portfolio_stocks": {
                "type": "array",
                "description": "Individual stock cards with entry/target/stop-loss. Only set when is_portfolio_response=true.",
                "items": {
                    "type": "object",
                    "required": ["ticker", "allocation_pct"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "name": {"type": "string"},
                        "allocation_pct": {"type": "number"},
                        "entry_price": {"type": "string"},
                        "target_price": {"type": "string"},
                        "stop_loss": {"type": "string"},
                        "risk_reward": {"type": "string"},
                        "rationale": {"type": "string"},
                        "confidence": {"type": "integer", "minimum": 1, "maximum": 10},
                        "sector": {"type": "string"},
                    },
                },
            },
            "scenario_analysis": {
                "type": "array",
                "description": "Bull / Base / Bear scenario cards with probability bars. Only set when is_portfolio_response=true.",
                "items": {
                    "type": "object",
                    "required": ["label"],
                    "properties": {
                        "label": {"type": "string"},
                        "probability_pct": {"type": "integer", "minimum": 0, "maximum": 100},
                        "outcome": {"type": "string"},
                        "description": {"type": "string"},
                        "color": {"type": "string"},
                    },
                },
            },
            "action_prompts": {
                "type": "array",
                "description": "Follow-up prompt buttons for portfolio refinement. Only set when is_portfolio_response=true.",
                "items": {
                    "type": "object",
                    "required": ["label", "prompt_text"],
                    "properties": {
                        "label": {"type": "string"},
                        "prompt_text": {"type": "string"},
                        "icon": {"type": "string"},
                    },
                },
            },
            "sebi_disclaimer": {
                "type": "string",
                "description": "SEBI regulatory disclaimer for Indian/investment advice contexts.",
            },
            "is_portfolio_response": {
                "type": "boolean",
                "description": "Set to true when this response follows the portfolio output template (market_context, allocation_breakdown, portfolio_stocks, etc.).",
            },
        },
    },
}


def _extract_tool_use_input(response) -> dict | None:
    """Pull the tool_use input dict from an Anthropic response. Returns None
    if the model returned text/no tool_use (e.g. on tool_choice rejection)."""
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _STRUCTURED_TOOL["name"]:
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None


@router.post("/v2/stream")
async def run_nl_query_v2_stream(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
):
    """SSE streaming variant of /v2. Emits phase labels + keep-alive pings."""
    from pydantic import ValidationError

    async def generate():
        if not req.question or len(req.question.strip()) < 3:
            err = StructuredQueryResponse(
                verdict="HOLD", confidence=0, timeframe="Medium-term",
                summary="Please enter a question (at least 3 characters).",
                reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                follow_up_questions=["What is the current Nifty level?"],
                route="REACT",
            )
            yield f'data: {_json.dumps({"status":"done","result":err.model_dump()})}\n\n'
            yield "data: [DONE]\n\n"
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            yield f'data: {_json.dumps({"status":"error","message":"ANTHROPIC_API_KEY not configured"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Phase 1: Classify (always REACT — SNAP disabled for richer detail)
        yield f'data: {_json.dumps({"status":"phase","phase":"classify","label":_PHASE_LABELS["classify"]})}\n\n'
        # Force REACT for all queries — user wants every answer detailed with full
        # cards (verdict banner, metrics, reasoning, scenarios, comparisons).
        # SNAP returns short cache-only answers which produce empty/weak cards.
        # DEEP (PARA-DEBATE) is reserved for explicit deep-analysis triggers and
        # is fine to keep. All other queries route to REACT.
        classified = dart.classify_query(req.question, req.ticker)
        route = "REACT" if classified == "SNAP" else classified

        # Phase 2-4: Context gathering (parallel)
        client, query_model = _query_client(api_key)
        query_start = time.monotonic()
        today = date.today().strftime("%B %d, %Y")

        # ── Detect ticker from question when not provided ───────────────────────
        stream_ticker = req.ticker
        if not stream_ticker:
            try:
                detected, _ = _detect_tickers_in_question(req.question, req.market or "US")
                if detected:
                    stream_ticker = detected[0].replace(".NS", "").replace(".BO", "")
            except Exception:
                pass

        yield f'data: {_json.dumps({"status":"phase","phase":"news","label":_PHASE_LABELS["news"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"macro","label":_PHASE_LABELS["macro"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"platform","label":_PHASE_LABELS["platform"]})}\n\n'

        result_holder: dict = {}
        context_done = asyncio.Event()

        async def _gather_context():
            async def _timed(coro, timeout, default):
                try:
                    return await asyncio.wait_for(coro, timeout=timeout)
                except (asyncio.TimeoutError, Exception):
                    return default

            headlines, macro_ctx, platform_ctx, finnhub_news, enrichment = await asyncio.gather(
                _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
                _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
                _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 45.0, None),
                _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, req.ticker, req.market or "US", 5), 8.0, []),
                _timed(asyncio.to_thread(_fetch_enrichment, stream_ticker, req.market or 'US'), 45.0, {}),
            )
            context_parts = [f"Today's date: {today}", f"User question: {req.question}"]
            if macro_ctx:
                context_parts.append(macro_ctx)
            if platform_ctx:
                context_parts.append(platform_ctx)
            if req.ticker:
                context_parts.append(f"Stock in focus: {req.ticker} ({req.market or 'US'} market)")
                # Sector peer comparison
                try:
                    from nq_api.universe import sector_of
                    from nq_api.cache.score_cache import read_sector_median
                    sector = sector_of(req.ticker, req.market or "US")
                    if sector and sector != "Unknown":
                        medians = read_sector_median(sector, req.market or "US")
                        if medians:
                            lines = [f"Sector median ({sector}):"]
                            for k, v in medians.items():
                                if v is not None:
                                    lines.append(f"  {k}: {round(v, 3)}")
                            context_parts.append("\n".join(lines))
                except Exception:
                    pass
            if headlines:
                context_parts.append("Recent market headlines (use these to answer current-events questions):")
                for h in headlines:
                    context_parts.append(f"  • {h}")
            if finnhub_news:
                context_parts.append("Detailed news summaries (use these for deeper context):")
                for a in finnhub_news:
                    summary_text = a.get("summary", "")
                    title_text = a.get("title", "")
                    source_text = a.get("source", "")
                    if summary_text:
                        context_parts.append(f"  • [{source_text}] {title_text}: {summary_text[:300]}")
            if enrichment:
                tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
                field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
                    "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
                    "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
                    "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
                    "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
                    "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
                    "insider_net_buy_ratio": "Insider Buy Ratio"}
                for k, label in field_labels.items():
                    v = enrichment.get(k)
                    if v is not None:
                        tech_lines.append(f"  {label}: {v}")
                if len(tech_lines) > 1:
                    context_parts.append("\n".join(tech_lines))
            result_holder["user_msg"] = "\n".join(context_parts)
            # Reinforce: if platform_ctx contains CURRENT_PRICE, add reminder
            if platform_ctx and "CURRENT_PRICE" in platform_ctx:
                result_holder["user_msg"] += "\n\nREMINDER: ALL values marked [VERIFIED] above are TODAY's live market data (yfinance). You MUST use EXACT P/E, Beta, Price, and Market Cap values shown — your training data has WRONG values for stocks with recent earnings changes or splits (e.g. NVDA P/E is ~42x NOT ~28x, Beta is ~2.2 NOT ~0.9). Wrong financial data causes real investment losses."
            result_holder["enrichment"] = enrichment
            result_holder["platform_ctx"] = platform_ctx
            context_done.set()

        context_task = asyncio.create_task(_gather_context())
        ctx_start = time.monotonic()
        while not context_done.is_set():
            yield 'data: {"status":"running"}\n\n'
            elapsed = time.monotonic() - ctx_start
            if elapsed > 30:                       # bumped 15s -> 30s
                context_task.cancel()
                result_holder.setdefault("error", "Context gathering timed out")
                break
            try:
                await asyncio.wait_for(asyncio.shield(context_done.wait()), timeout=4.0)
            except asyncio.TimeoutError:
                pass

        if "error" in result_holder:
            yield f'data: {_json.dumps({"status":"error","message":result_holder["error"]})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Context built — emit "context" phase as completed marker
        yield f'data: {_json.dumps({"status":"phase","phase":"context","label":_PHASE_LABELS["context"]})}\n\n'

        # Phase 5+: LLM call broken into prompt → thinking → generate → parse
        yield f'data: {_json.dumps({"status":"phase","phase":"prompt","label":_PHASE_LABELS["prompt"]})}\n\n'
        total_elapsed = time.monotonic() - query_start

        llm_done = asyncio.Event()

        async def _call_llm():
            try:
                # Load persistent conversation memory if session_key provided
                user_id_stream = str(user.id) if user else None
                persistent_history_stream = []
                if user_id_stream and req.session_key:
                    try:
                        persistent_history_stream = await asyncio.to_thread(
                            _load_conversation_history, user_id_stream, req.session_key, limit=10
                        )
                    except Exception:
                        pass

                messages = []
                # Merge client-provided history, persistent history, and current message
                seen_content = set()
                all_history = list(req.history or [])[-4:]
                for ph in persistent_history_stream:
                    all_history.append(ConversationMessage(role=ph["role"], content=ph["content"]))
                for m in all_history[-8:]:
                    content = m.content[:1500] if len(m.content) > 1500 else m.content
                    if content not in seen_content:
                        seen_content.add(content)
                        messages.append({"role": m.role, "content": content})
                messages.append({"role": "user", "content": result_holder["user_msg"]})

                # ── Clarification check (ask follow-up before answering) ──────────
                detected_tickers_stream = []
                if not req.ticker:
                    try:
                        detected_tickers_stream, _ = _detect_tickers_in_question(req.question, req.market or "US")
                    except Exception:
                        pass
                else:
                    detected_tickers_stream = [req.ticker]

                if req.clarification_answers:
                    answers_text = "\n".join(f"• {a}" for a in req.clarification_answers)
                    result_holder["user_msg"] += f"\n\n[USER CONTEXT] User clarified their needs:\n{answers_text}"
                    messages[-1] = {"role": "user", "content": result_holder["user_msg"]}

                # Build dynamic clarification context with live market data (streaming)
                _fmp_ctx_s = _fetch_fmp_context_for_clarification(
                    detected_tickers_stream[0] if detected_tickers_stream else "",
                    req.market or "US",
                ) if detected_tickers_stream else None
                _clarification_qs_s = _generate_clarification_questions(
                    req.question, detected_tickers_stream, req.market or "US", route,
                    fmp_context=_fmp_ctx_s,
                )
                _ctx_str_s = "Answer these questions so I can give you a personalized response."
                if _fmp_ctx_s and detected_tickers_stream:
                    _ctx_parts_s = []
                    cur_s = "₹" if (req.market or "US") == "IN" else "$"
                    if _fmp_ctx_s.get("price"):
                        _ctx_parts_s.append(f"Price: {cur_s}{_fmp_ctx_s['price']:,.2f}")
                    if _fmp_ctx_s.get("pe"):
                        _ctx_parts_s.append(f"P/E: {_fmp_ctx_s['pe']:.1f}x")
                    if _fmp_ctx_s.get("analyst_consensus"):
                        _ctx_parts_s.append(f"Analysts: {_fmp_ctx_s['analyst_consensus'].title()}")
                    if _fmp_ctx_s.get("dividend_yield"):
                        _ctx_parts_s.append(f"Yield: {_fmp_ctx_s['dividend_yield']:.1f}%")
                    if _fmp_ctx_s.get("next_earnings_date"):
                        _ctx_parts_s.append(f"Earnings: {_fmp_ctx_s['next_earnings_date']}")
                    if _ctx_parts_s:
                        _ctx_str_s = f"Live data for {detected_tickers_stream[0]}: {' | '.join(_ctx_parts_s)}"

                clarification = _needs_clarification(req.question, detected_tickers_stream, route, req.profile)
                if clarification and not req.clarification_answers:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD",
                        confidence=0,
                        timeframe="N/A",
                        summary="I'd like to understand your needs better before answering.",
                        reasoning=ReasoningBlock(
                            why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                            second_best="N/A", confidence_gap="N/A",
                        ),
                        clarification_needed=True,
                        clarification_questions=_clarification_qs_s,
                        clarification_context=_ctx_str_s,
                        route="REACT",
                        data_sources=["NeuralQuant Clarification"],
                        follow_up_questions=[],
                        metrics=[],
                        scenarios=[],
                        allocations=[],
                        comparisons=[],
                    )
                    return

                # Portfolio intent detection and prompt injection
                portfolio_intent = _is_portfolio_intent(req.question)

                # Check if profile needed for portfolio questions
                # Only show profiler if clarification was NOT needed (or was already answered)
                if portfolio_intent and not req.profile and not clarification:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD",
                        confidence=0,
                        timeframe="Medium-term",
                        summary="Before I build your portfolio, I need to understand your goals.",
                        reasoning=ReasoningBlock(
                            why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                            second_best="N/A", confidence_gap="N/A",
                        ),
                        profiler_needed=True,
                        route="REACT",
                        data_sources=["NeuralQuant Profiler"],
                        follow_up_questions=[],
                        metrics=[],
                        scenarios=[],
                        allocations=[],
                        comparisons=[],
                    )
                    return

                system_prompt = _SYSTEM_STRUCTURED
                if portfolio_intent:
                    system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
                    snap = _build_market_snapshot(req.market or "US")
                    if snap:
                        result_holder["user_msg"] = result_holder["user_msg"] + "\n\n" + snap
                    # Inject profile if present
                    if req.profile:
                        result_holder["user_msg"] = result_holder["user_msg"] + "\n\n" + _build_profile_prompt(req.profile)
                    messages[-1]["content"] = result_holder["user_msg"]

                # Inject profile context for all non-portfolio streaming queries
                if req.profile and not portfolio_intent:
                    result_holder["user_msg"] = result_holder["user_msg"] + "\n\n[INVESTOR PROFILE CONTEXT] " + _build_profile_prompt(req.profile)
                    messages[-1]["content"] = result_holder["user_msg"]

                # Force tool_use: model MUST call `respond_with_neuralquant_forecast`
                # with arguments matching the schema. No more markdown leakage.
                # 90s timeout prevents indefinite hangs on complex queries
                try:
                    response = await _call_anthropic_with_retry(
                        client,
                        model=query_model,
                        max_tokens=8000,
                        system=system_prompt,
                        tools=[_STRUCTURED_TOOL],
                        tool_choice={"type": "tool", "name": _STRUCTURED_TOOL["name"]},
                        messages=messages,
                        timeout=90.0,
                    )
                except asyncio.TimeoutError:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD", confidence=0, timeframe="Medium-term",
                        summary="Query timed out — the AI took too long to respond. Try a shorter question.",
                        reasoning=ReasoningBlock(why_this="N/A", why_not_alt="N/A", edge_summary="N/A", second_best="N/A", confidence_gap="N/A"),
                        route=route,
                    )
                    llm_done.set()
                    return

                parsed = _extract_tool_use_input(response)
                if parsed:
                    try:
                        parsed.setdefault("route", route)
                        parsed.setdefault("data_sources", [])
                        parsed.setdefault("follow_up_questions", [])
                        if "reasoning" not in parsed:
                            parsed["reasoning"] = {
                                "why_this": "Based on the highest ForeCast Score and strongest factor alignment",
                                "why_not_alt": "Alternative had lower scores on key factors",
                                "edge_summary": "Selected stock leads on composite score and factor quality",
                                "second_best": "N/A",
                                "confidence_gap": "N/A",
                            }
                        # Portfolio validation post-processing (before creating StructuredQueryResponse)
                        log.info("Portfolio intent check: %s, parsed keys: %s", portfolio_intent, list(parsed.keys()))
                        if portfolio_intent:
                            parsed["is_portfolio_response"] = True
                            log.info("Setting is_portfolio_response=True")
                            # Ensure SEBI disclaimer present
                            if not parsed.get("sebi_disclaimer") or "SEBI" not in parsed.get("sebi_disclaimer", "").upper():
                                parsed["sebi_disclaimer"] = (
                                    "This is AI-generated investment research, not SEBI-registered investment advice. "
                                    "Please consult a certified financial advisor before investing."
                                )
                            # Auto-fill portfolio fields from old format if missing
                            if not parsed.get("portfolio_stocks") and parsed.get("allocations"):
                                parsed["portfolio_stocks"] = []
                                for a in parsed["allocations"]:
                                    ticker = a.get("ticker", "")
                                    weight = a.get("weight", 0)
                                    rationale = a.get("rationale", "")
                                    # Extract entry price from rationale if present
                                    entry_match = re.search(r'Entry[:\s]+([^;\n]+)', rationale)
                                    entry_price = entry_match.group(1).strip() if entry_match else None
                                    # Extract target from rationale if present
                                    target_match = re.search(r'Target[:\s]+([^;\n]+)', rationale)
                                    target_price = target_match.group(1).strip() if target_match else None
                                    # Extract stop from rationale if present
                                    stop_match = re.search(r'Stop[:\s]+([^;\n]+)', rationale)
                                    stop_loss = stop_match.group(1).strip() if stop_match else None
                                    parsed["portfolio_stocks"].append({
                                        "ticker": ticker,
                                        "allocation_pct": weight,
                                        "rationale": rationale,
                                        "entry_price": entry_price,
                                        "target_price": target_price,
                                        "stop_loss": stop_loss,
                                    })
                            if not parsed.get("scenario_analysis") and parsed.get("scenarios"):
                                parsed["scenario_analysis"] = []
                                scenario_colors = {"Bull": "#22c55e", "Base": "#6366f1", "Bear": "#ef4444"}
                                for s in parsed["scenarios"]:
                                    label = s.get("label", "")
                                    prob = int(s.get("probability", 0) * 100)
                                    parsed["scenario_analysis"].append({
                                        "label": label,
                                        "probability_pct": prob,
                                        "outcome": s.get("target", ""),
                                        "description": s.get("thesis", ""),
                                        "color": scenario_colors.get(label, "#6366f1"),
                                    })
                            if not parsed.get("allocation_breakdown") and parsed.get("allocations"):
                                parsed["allocation_breakdown"] = []
                                for a in parsed["allocations"]:
                                    parsed["allocation_breakdown"].append({
                                        "label": a.get("ticker", ""),
                                        "percentage": a.get("weight", 0),
                                        "rationale": a.get("rationale", ""),
                                    })
                            if not parsed.get("market_context"):
                                parsed["market_context"] = []
                            if not parsed.get("action_prompts"):
                                parsed["action_prompts"] = []
                            # Allocation sum check
                            alloc = parsed.get("allocation_breakdown") or []
                            if alloc:
                                total = sum(float(a.get("percentage", 0)) for a in alloc)
                                if abs(total - 100.0) > 1.0:
                                    parsed.setdefault("data_quality_flags", [])
                                    parsed["data_quality_flags"].append(f"Allocation sums to {total:.1f}% (expected 100%)")
                            # Scenario count check
                            scenarios = parsed.get("scenario_analysis") or []
                            if len(scenarios) < 3:
                                parsed.setdefault("data_quality_flags", [])
                                parsed["data_quality_flags"].append("Scenario analysis incomplete")
                            # Validate portfolio stock data against real yfinance
                            if parsed.get("portfolio_stocks"):
                                corrected_stocks, corrected_summary, pf_corrections = await asyncio.to_thread(
                                    _validate_portfolio_stocks, parsed["portfolio_stocks"], req.market or "US", parsed.get("summary", "")
                                )
                                parsed["portfolio_stocks"] = corrected_stocks
                                if corrected_summary != parsed.get("summary", ""):
                                    parsed["summary"] = corrected_summary
                                if pf_corrections and parsed.get("summary"):
                                    parsed["summary"] += f" [Data verified: {'; '.join(pf_corrections)}]"
                                # Fill live prices for entry/target/stop_loss
                                filled_stocks, fill_notes = await asyncio.to_thread(
                                    _validate_and_fill_portfolio_prices, parsed["portfolio_stocks"], req.market or "US"
                                )
                                parsed["portfolio_stocks"] = filled_stocks
                                if fill_notes and parsed.get("summary"):
                                    parsed["summary"] += f" [Live prices verified: {'; '.join(fill_notes)}]"
                        result_holder["result"] = StructuredQueryResponse(**parsed)
                        # Validate LLM metrics against injected [VERIFIED] data
                        verified = _extract_verified_values(result_holder.get("platform_ctx"))
                        result_holder["result"] = _validate_response_metrics(result_holder["result"], verified)
                        # Attach stock summary from enrichment data
                        result_holder["result"].stock_summary = _build_stock_summary(
                            stream_ticker, req.market or "US",
                            result_holder.get("enrichment", {}),
                            result_holder.get("platform_ctx"),
                        )
                        # Persist conversation turn (best-effort, streaming)
                        if user_id_stream and req.session_key:
                            try:
                                await asyncio.to_thread(
                                    _save_conversation_turn, user_id_stream, req.session_key,
                                    "user", req.question, req.ticker, req.market or "US"
                                )
                                await asyncio.to_thread(
                                    _save_conversation_turn, user_id_stream, req.session_key,
                                    "assistant", result_holder["result"].summary, req.ticker, req.market or "US"
                                )
                            except Exception:
                                pass
                    except (ValidationError, Exception) as e:
                        log.warning("Tool-use structured output validation failed: %s", e)

                # Fallback path — if tool_use missed (extremely rare with tool_choice forced),
                # extract from any text block and run the markdown salvage parser.
                if "result" not in result_holder:
                    raw = ""
                    for block in response.content:
                        if getattr(block, "type", None) == "text":
                            raw = block.text
                            break
                    freeform_resp = _parse_query_response(raw, route)
                    result_holder["result"] = _structured_from_markdown(
                        raw, freeform_resp, route,
                        _build_stock_summary(stream_ticker, req.market or "US", result_holder.get("enrichment", {}), result_holder.get("platform_ctx")),
                    )
                    # Validate LLM metrics against injected [VERIFIED] data
                    verified = _extract_verified_values(result_holder.get("platform_ctx"))
                    result_holder["result"] = _validate_response_metrics(result_holder["result"], verified)
            except anthropic.APITimeoutError:
                result_holder["result"] = StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary="Query timed out — the AI took too long to respond. Try a shorter question.",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                )
            except Exception as exc:
                result_holder["result"] = StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary=f"Query failed: {str(exc)[:200]}",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                )
            finally:
                llm_done.set()

        llm_task = asyncio.create_task(_call_llm())
        llm_start = time.monotonic()
        # Emit thinking → generate phase transitions while LLM works
        sent_thinking = False
        sent_generate = False
        while not llm_done.is_set():
            yield 'data: {"status":"running"}\n\n'
            llm_elapsed = time.monotonic() - llm_start
            if not sent_thinking and llm_elapsed > 1.5:
                yield f'data: {_json.dumps({"status":"phase","phase":"thinking","label":_PHASE_LABELS["thinking"]})}\n\n'
                sent_thinking = True
            if not sent_generate and llm_elapsed > 12:
                yield f'data: {_json.dumps({"status":"phase","phase":"generate","label":_PHASE_LABELS["generate"]})}\n\n'
                sent_generate = True
            total_elapsed = time.monotonic() - query_start
            if total_elapsed > 180:                 # bumped 60s -> 180s total cap
                llm_task.cancel()
                result_holder.setdefault("result", StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary="Analysis timed out after 3 minutes. Try a shorter or more specific question.",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                ))
                llm_done.set()
                break
            try:
                await asyncio.wait_for(asyncio.shield(llm_done.wait()), timeout=4.0)
            except asyncio.TimeoutError:
                pass

        # Final phases: parse + render
        yield f'data: {_json.dumps({"status":"phase","phase":"parse","label":_PHASE_LABELS["parse"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"render","label":_PHASE_LABELS["render"]})}\n\n'

        if "result" in result_holder:
            yield f'data: {_json.dumps({"status":"done","result": result_holder["result"].model_dump()})}\n\n'
        else:
            yield f'data: {_json.dumps({"status":"error","message":"No result produced"})}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
