"""POST /query — natural language financial query endpoint."""
import os
import re
from datetime import date

import anthropic
import yfinance as yf
from fastapi import APIRouter
from nq_api.schemas import QueryRequest, QueryResponse

router = APIRouter()

MODEL = "claude-sonnet-4-20250514"

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
    "INDIA":    ["INDA", "^BSESN"],
    "NSE":      ["INDA", "^BSESN"],
}

_SYSTEM = """You are NeuralQuant's financial intelligence assistant — an AI with access to:
1. Live macro data (FRED: HY spreads, CPI, Fed funds, yield curve; yfinance: VIX, SPX momentum)
2. NeuralQuant AI stock scores for 50 US stocks and 50 Indian (NSE) stocks — injected below when relevant
3. Live market prices, sector performance, and news headlines
4. 5-factor quantitative model: Quality, Momentum, Value (P/E+P/B), Low-Volatility, Short Interest

Rules:
1. ALWAYS use the injected live data. NEVER say "I don't have access" when data is provided below.
2. When NeuralQuant stock scores are injected, CITE THEM: "NeuralQuant rates NVDA 6/10 (medium confidence)"
3. When asked about a specific stock, use its injected score, factors, and confidence.
4. When asked "best stock" or "top pick", use the injected screener rankings.
5. For current events, use injected news headlines. Reference the date in your answer.
6. Be direct and quantitative. Financial professionals read this.
7. End every response with exactly 3 follow-up questions.

Response format:
ANSWER: [Your answer — cite NeuralQuant scores, live macro, and news headlines specifically]
DATA_SOURCES: [comma-separated list of what you used: NeuralQuant Screener / FRED Macro / Live News / etc.]
FOLLOW_UP:
- [Question 1]
- [Question 2]
- [Question 3]"""


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 8) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    # Always start with broad market + any user-specified ticker
    priority: list[str] = ["^GSPC", "SPY"]
    if ticker:
        priority.insert(0, ticker)

    # Detect sector keywords and inject the right ETFs/tickers
    q_upper = question.upper()
    for keyword, syms in _SECTOR_MAP.items():
        if keyword in q_upper:
            for s in syms:
                if s not in priority:
                    priority.append(s)

    # Also try any short words that look like real tickers (2-5 alpha chars, not stop-words)
    extra: list[str] = []
    for word in q_upper.split():
        clean = re.sub(r"[^A-Z]", "", word)
        if 2 <= len(clean) <= 5 and clean not in _STOP_WORDS and clean not in priority:
            extra.append(clean)

    candidates = priority + extra

    headlines: list[str] = []
    seen: set[str] = set()
    for sym in candidates[:8]:  # try up to 8 sources
        try:
            items = yf.Ticker(sym).news or []
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


_SCREENER_KEYWORDS = {
    "SCREENER", "BEST STOCK", "TOP STOCK", "RANK", "RANKING", "TOP PICK",
    "RECOMMEND", "BUY RIGHT NOW", "SHOULD I BUY", "WHICH STOCK",
    "NEURALQUANT", "YOUR PLATFORM", "YOUR SCREENER", "YOUR MODEL",
    # Additional patterns for natural-language "top picks" questions
    "TOP PICKS", "TOP 3", "TOP 5", "TOP 10", "BEST PICK", "BEST PICKS",
    "YOUR TOP", "STOCK PICKS", "STOCK PICK", "WHICH STOCKS",
}
_INDIA_KEYWORDS = {"INDIA", "INDIAN", "NSE", "BSE", "NIFTY", "SENSEX", "RUPEE"}


def _detect_tickers_in_question(question: str) -> list[str]:
    """Extract potential ticker symbols from the question text."""
    from nq_api.universe import US_DEFAULT, IN_DEFAULT
    known = set(US_DEFAULT) | set(IN_DEFAULT)
    found = []
    q_upper = question.upper()
    # Check all known tickers
    for t in known:
        if re.search(r'\b' + re.escape(t) + r'\b', q_upper):
            found.append(t)
    return found[:5]  # cap at 5


def _enrich_with_platform_data(question: str, market: str) -> str | None:
    """
    Fetch NeuralQuant's own stock scores + movers when the question needs them.
    Returns a formatted context string, or None if not needed.
    """
    from nq_api.data_builder import build_real_snapshot, fetch_fundamentals_batch
    from nq_api.universe import UNIVERSE_BY_MARKET
    from nq_signals.engine import SignalEngine
    from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe
    from nq_api.deps import get_signal_engine

    q_upper = question.upper()
    parts: list[str] = []

    # Determine which market to use for screener
    target_market = "IN" if any(k in q_upper for k in _INDIA_KEYWORDS) else market

    # Check if question asks about the screener / best stocks
    needs_screener = any(k in q_upper for k in _SCREENER_KEYWORDS)
    # Detect specific ticker mentions
    mentioned_tickers = _detect_tickers_in_question(question)
    # Check if it asks about "buy/sell/hold" a stock or a comparison
    needs_stock_scores = (
        mentioned_tickers
        or any(k in q_upper for k in ["IS A BUY", "IS A SELL", "COMPARE", "VERSUS", "VS ", "OVERVALUED", "SHORT INTEREST"])
    )

    if not needs_screener and not needs_stock_scores and not mentioned_tickers:
        return None  # No platform data needed

    try:
        engine = get_signal_engine()

        if needs_screener or (not mentioned_tickers and needs_stock_scores):
            # Run screener for top 10
            universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])[:20]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            # Sort by composite_score descending so head(10) gives the true top 10
            result_df = result_df.sort_values("composite_score", ascending=False).reset_index(drop=True)
            ranked = rank_scores_in_universe(result_df)
            top = result_df.head(10)
            lines = [f"NeuralQuant {target_market} Screener — Top 10 stocks right now:"]
            for i, (idx, row) in enumerate(top.iterrows()):
                # Use .loc[idx] not .iloc[idx] — idx is a label after reset_index
                sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                q = row.get("quality_percentile", 0.5)
                m = row.get("momentum_percentile", 0.5)
                v = row.get("value_percentile", 0.5)
                si = row.get("short_interest_percentile", 0.5)
                lines.append(
                    f"  #{i+1} {row['ticker']}: {sc}/10 score | "
                    f"Quality={q:.0%} Momentum={m:.0%} Value={v:.0%} LowSI={si:.0%} | "
                    f"Confidence: {row.get('regime_confidence', 0.5):.0%}"
                )
            parts.append("\n".join(lines))

        if mentioned_tickers:
            # Fetch scores for specifically mentioned tickers
            # Use full universe so percentile ranks are meaningful
            base_universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])
            universe = list(dict.fromkeys(mentioned_tickers + base_universe))[:25]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            ranked = rank_scores_in_universe(result_df)
            lines = [f"NeuralQuant scores for mentioned stocks:"]
            for t in mentioned_tickers:
                row_match = result_df[result_df["ticker"] == t]
                if not row_match.empty:
                    row = row_match.iloc[0]
                    idx = row_match.index[0]
                    sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                    conf_label = "high" if row.get("regime_confidence", 0.5) > 0.7 else ("medium" if row.get("regime_confidence", 0.5) > 0.4 else "low")
                    lines.append(
                        f"  {t}: {sc}/10 (composite={row['composite_score']:.3f}) | "
                        f"Quality={row.get('quality_percentile', 0.5):.0%} "
                        f"Momentum={row.get('momentum_percentile', 0.5):.0%} "
                        f"Value={row.get('value_percentile', 0.5):.0%} "
                        f"LowVol={row.get('low_vol_percentile', 0.5):.0%} "
                        f"LowSI={row.get('short_interest_percentile', 0.5):.0%} | "
                        f"Regime: {row.get('regime_id', 1)} | P/E={row.get('pe_ttm', 'N/A')} P/B={row.get('pb_ratio', 'N/A'):.1f} Beta={row.get('beta', 'N/A'):.2f}"
                    )
            parts.append("\n".join(lines))

        # Also inject live prices for mentioned tickers
        if mentioned_tickers:
            try:
                import yfinance as yf
                price_lines = ["Live prices:"]
                for t in mentioned_tickers[:3]:
                    try:
                        info = yf.Ticker(t).info
                        price = info.get("currentPrice") or info.get("regularMarketPrice")
                        high52 = info.get("fiftyTwoWeekHigh")
                        low52 = info.get("fiftyTwoWeekLow")
                        target = info.get("targetMeanPrice")
                        if price:
                            price_lines.append(
                                f"  {t}: ${price:.2f} | 52w range ${low52:.2f}–${high52:.2f}"
                                + (f" | Analyst target ${target:.2f}" if target else "")
                            )
                    except Exception:
                        pass
                if len(price_lines) > 1:
                    parts.append("\n".join(price_lines))
            except Exception:
                pass

    except Exception as exc:
        return f"[Platform data unavailable: {exc}]"

    return "\n\n".join(parts) if parts else None


@router.post("", response_model=QueryResponse)
def run_nl_query(req: QueryRequest) -> QueryResponse:
    # BUG-007: validate non-empty question
    if not req.question or len(req.question.strip()) < 3:
        return QueryResponse(
            answer="Please enter a question (at least 3 characters).",
            data_sources=[],
            follow_up_questions=["What is the current VIX?", "Which stocks are top ranked?", "What is the Fed funds rate?"],
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return QueryResponse(
            answer="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            data_sources=[],
            follow_up_questions=[],
        )
    client = anthropic.Anthropic(api_key=api_key)

    today = date.today().strftime("%B %d, %Y")
    headlines = _fetch_relevant_news(req.question, req.ticker)

    # Inject live macro snapshot
    from nq_api.data_builder import fetch_real_macro
    try:
        macro = fetch_real_macro()
        macro_ctx = (
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
    except Exception:
        macro_ctx = None

    # BUG-002 fix: inject NeuralQuant's own stock scores + prices when relevant
    platform_ctx = _enrich_with_platform_data(req.question, req.market)

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
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")

    user_msg = "\n".join(context_parts)

    try:
        # Build message list — prepend up to 6 prior turns for multi-turn chat
        messages = [{"role": m.role, "content": m.content} for m in req.history[-6:]]
        messages.append({"role": "user", "content": user_msg})
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_SYSTEM,
            messages=messages,
        )
        raw = response.content[0].text
        return _parse_query_response(raw)
    except Exception as exc:
        return QueryResponse(
            answer=f"Query failed: {str(exc)[:100]}",
            data_sources=[],
            follow_up_questions=[],
        )


def _parse_query_response(raw: str) -> QueryResponse:
    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|\Z)", raw, re.I | re.S | re.M)
    answer = answer_match.group(1).strip() if answer_match else raw[:500]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|\Z)", raw, re.I | re.S | re.M)
    sources = [s.strip() for s in sources_match.group(1).split(",")] if sources_match else []

    followup_match = re.search(r"FOLLOW_UP:(.*)", raw, re.I | re.S | re.M)
    followups = []
    if followup_match:
        followups = [
            re.sub(r"^[-*•]\s*|\d+\.\s*", "", q.strip()).strip()
            for q in followup_match.group(1).strip().splitlines()
            if q.strip() and q.strip() not in ("-", "*", "•")
        ]

    return QueryResponse(
        answer=answer[:2000],
        data_sources=sources[:5],
        follow_up_questions=followups[:3],
    )
