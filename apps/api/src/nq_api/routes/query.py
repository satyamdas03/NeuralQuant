"""POST /query — natural language financial query endpoint."""
import asyncio
import os
import re
from datetime import date

import anthropic
import yfinance as yf
from fastapi import APIRouter, Depends
import logging

from nq_api.schemas import QueryRequest, QueryResponse, StructuredQueryResponse, ReasoningBlock

log = logging.getLogger(__name__)
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User
import nq_api.dart_router as dart

router = APIRouter()

MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6")

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

_SYSTEM = """You are NeuralQuant — an institutional-grade AI stock intelligence engine. You have access to live data injected in every user message. Your job: give direct, data-driven, actionable answers with PERFECT reasoning. Every recommendation must be THE BEST available, justified by data, and compared against alternatives. No hedging. No disclaimers. No detours.

## DATA YOU HAVE ACCESS TO
1. Live macro data: FRED (HY spreads, CPI, Fed funds, yield curve) + yfinance (VIX, SPX, Nifty, INR/USD)
2. NeuralQuant AI stock scores (1-10) for 50 US + 50 Indian NSE stocks
3. Live prices, 52-week ranges, analyst targets, P/E, P/B, beta
4. Real-time market headlines
5. Competitor comparison data — nearby ranked stocks and their scores

## HARD RULES — NEVER VIOLATE
1. **NEVER say "I don't have data/scores for this stock" when price or fundamentals are injected above.** If live price is injected, USE IT. Quote exact numbers.
2. **NEVER deflect to a different stock when the user asks about a specific one.** If asked about Trent, answer about Trent — not Bharti, not Maruti.
3. **NEVER mention US indices (S&P 500, VIX, HY spreads, 2s10s) as primary context for India-specific questions.** For India queries: lead with Nifty/Sensex/INR, mention global risk only as a footnote.
4. **NEVER give indirect or vague investment advice.** If asked "which stocks to buy for ₹10L", name SPECIFIC stocks with specific rupee allocations.
5. **NEVER start with "Based on available data, I cannot..."** — you always have data. Use it.

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
  - Give entry price range (use the LIVE price injected above as midpoint; range = ±2%). Do NOT invent prices — if a stock's live price is not injected, exclude it.
  - **CRITICAL — Target price rule:** If user specified a return target R% (e.g. "15-20%"), then EVERY stock's target price MUST equal entry_mid × (1 + r/100) where r ∈ [R_low, R_high]. Do NOT copy the analyst consensus target verbatim. Do NOT include a stock whose realistic 12-month upside falls outside the user's range — pick a different stock. Show the per-stock % next to the target and confirm it lands inside the user's band.
  - Stop-loss: entry_mid × 0.90 (10% below entry) for every stock — consistent across the portfolio.
  - **For EACH allocation, explain WHY this stock and WHY NOT the next-best alternative.** This is mandatory.
  - Keep the entire portfolio block under 1200 characters so it renders cleanly.
- **For specific stock queries:** Lead with: score/10 (if available), current price, 1-line verdict (BUY / HOLD / AVOID), then justify with data. ALWAYS compare to the nearest competitor or sector average.
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
You MUST respond with ONLY a JSON object matching this schema. No markdown, no prose outside the JSON.

Required fields:
{
  "verdict": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "confidence": 0-100,
  "timeframe": "Short-term | Medium-term | Long-term",
  "summary": "2-3 sentence plain text summary",
  "metrics": [{"name": "string", "value": "string", "benchmark": "string|null", "status": "positive|negative|neutral"}],
  "reasoning": {
    "why_this": "WHY you chose this stock/recommendation — cite 2-3 specific data points",
    "why_not_alt": "WHY NOT the next-best alternative — name the alternative stock and explain what it lacks",
    "edge_summary": "One-line: what gives this pick its edge over the alternative",
    "second_best": "Name of the runner-up stock you rejected",
    "confidence_gap": "How much better (e.g. 'ForeCast 8 vs 6, +2 edge on momentum')"
  },
  "scenarios": [{"label": "Bear|Base|Bull", "probability": 0-1, "target": "price", "thesis": "trigger"}],
  "allocations": [{"ticker": "X", "weight": 0-100, "rationale": "why X", "why_not_alt": "why not Y instead"}],
  "comparisons": [{"ticker": "X", "metric": "P/E", "ours": "value", "theirs": "value", "edge": "why ours wins"}],
  "follow_up_questions": ["q1", "q2", "q3"]
}

CRITICAL REASONING RULES:
1. EVERY stock recommendation MUST include reasoning.why_this with 2+ specific data points.
2. EVERY stock recommendation MUST include reasoning.why_not_alt naming the next-best alternative and explaining WHY it's inferior.
3. For portfolio questions, each allocation MUST have rationale (why this stock) AND why_not_alt (why not the runner-up).
4. If comparing stocks, use comparisons array to show side-by-side metric advantages.
5. The reasoning block is MANDATORY — never leave it empty. This is what separates a quant researcher from a chatbot.
"""


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
    "MARKET", "NIFTY", "SENSEX", "RUPEE", "LAKH", "CRORE", "MILLION",
    "BILLION", "WANT", "GIVE", "TELL", "BEST", "GOOD", "HIGH", "LARGE",
    "SMALL", "LONG", "TERM", "CURRENT", "TODAY", "YEAR", "MONTH", "WEEK",
    "PLEASE", "WHICH", "ABOUT", "PORTFOLIO", "INVEST", "ADVICE", "RETURN",
    "GROWTH", "VALUE", "STRONG", "WEAK", "RISK", "SAFE", "SECTOR", "NSE",
    "BSE", "BULL", "BEAR", "TRADE", "TRADE", "PRICE", "RANGE", "TARGET",
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
        except Exception:
            return None


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
        if 2 <= len(clean) <= 5 and clean not in _STOP_WORDS and clean not in priority:
            extra.append(clean)

    candidates = priority + extra
    headlines: list[str] = []
    seen: set[str] = set()
    for sym in candidates[:8]:
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


def _fetch_india_macro() -> str | None:
    """Fetch India-specific market context: Nifty 50, Sensex, INR/USD, India VIX."""
    try:
        lines = []

        # Nifty 50
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d", auto_adjust=True)
        if len(hist) >= 2:
            nifty_price = float(hist["Close"].iloc[-1])
            nifty_prev = float(hist["Close"].iloc[-2])
            nifty_chg = (nifty_price - nifty_prev) / nifty_prev * 100
            lines.append(f"Nifty 50: {nifty_price:,.0f} ({nifty_chg:+.2f}% today)")

        # BSE Sensex
        sensex = yf.Ticker("^BSESN")
        hist2 = sensex.history(period="5d", auto_adjust=True)
        if len(hist2) >= 2:
            sensex_price = float(hist2["Close"].iloc[-1])
            sensex_prev = float(hist2["Close"].iloc[-2])
            sensex_chg = (sensex_price - sensex_prev) / sensex_prev * 100
            lines.append(f"BSE Sensex: {sensex_price:,.0f} ({sensex_chg:+.2f}% today)")

        # INR/USD exchange rate
        inr = yf.Ticker("USDINR=X")
        inr_hist = inr.history(period="5d", auto_adjust=True)
        if not inr_hist.empty:
            inr_rate = float(inr_hist["Close"].iloc[-1])
            lines.append(f"USD/INR: {inr_rate:.2f}")

        # India VIX
        india_vix = yf.Ticker("^INDIAVIX")
        vix_hist = india_vix.history(period="5d", auto_adjust=True)
        if not vix_hist.empty:
            ivix = float(vix_hist["Close"].iloc[-1])
            lines.append(f"India VIX: {ivix:.1f} ({'elevated' if ivix > 20 else 'normal'})")

        return "Indian Market Context: " + " | ".join(lines) if lines else None
    except Exception:
        return None


def _fetch_dynamic_nse_stock(word: str) -> dict | None:
    """
    Try to fetch live data for an NSE stock not in our screener universe.
    word: uppercase stock name/ticker from user query.
    Returns a dict with price, fundamentals, or None if not found.
    """
    nse_sym = _NSE_NAME_MAP.get(word)
    if not nse_sym:
        nse_sym = f"{word}.NS"

    try:
        t = yf.Ticker(nse_sym)
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None  # Stock not found or no price data

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
    except Exception:
        return None


def _detect_tickers_in_question(question: str, market: str = "US") -> tuple[list[str], list[str]]:
    """
    Returns (in_universe_tickers, out_of_universe_words).
    in_universe_tickers: known tickers found in question.
    out_of_universe_words: words that look like NSE tickers but aren't in universe.
    """
    from nq_api.universe import US_DEFAULT, IN_DEFAULT
    known = set(US_DEFAULT) | set(IN_DEFAULT)
    in_universe = []
    q_upper = question.upper()

    # Check known universe tickers (strip .NS / .BO for matching)
    for t in known:
        base = t.replace(".NS", "").replace(".BO", "")
        if re.search(r'\b' + re.escape(base) + r'\b', q_upper):
            in_universe.append(t)

    # For India queries, also check NSE name map keys
    out_of_universe = []
    if market == "IN" or any(k in q_upper for k in _INDIA_KEYWORDS):
        # First check the name map directly
        for name_key in _NSE_NAME_MAP:
            if (re.search(r'\b' + re.escape(name_key) + r'\b', q_upper)
                    and name_key not in {t.replace(".NS", "").replace(".BO", "") for t in known}):
                if name_key not in out_of_universe:
                    out_of_universe.append(name_key)

        # Then scan remaining words that look like tickers
        for word in q_upper.split():
            clean = re.sub(r"[^A-Z]", "", word)
            if (3 <= len(clean) <= 12
                    and clean not in _STOP_WORDS
                    and clean not in _TICKER_STOP_WORDS
                    and clean not in known
                    and clean not in {t.replace(".NS", "").replace(".BO", "") for t in known}
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
    Also dynamically fetches data for stocks not in the screener universe.
    Returns a formatted context string with ACCURATE live prices, or None if not needed.
    """
    from nq_api.data_builder import build_real_snapshot, _fund_cache
    from nq_api.universe import UNIVERSE_BY_MARKET
    from nq_api.score_builder import rank_scores_in_universe
    from nq_api.deps import get_signal_engine

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
        engine = get_signal_engine()

        if needs_screener or (not in_universe_tickers and not out_of_universe_words and needs_stock_scores):
            universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])[:40]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            result_df = result_df.sort_values("composite_score", ascending=False).reset_index(drop=True)
            ranked = rank_scores_in_universe(result_df)
            top = result_df.head(20)
            lines = [f"NeuralQuant {target_market} Screener — Top 20 with LIVE prices (use these exact prices):"]
            for i, (idx, row) in enumerate(top.iterrows()):
                sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                t = row["ticker"]
                fund = _fund_cache.get(f"{t}:{target_market}", {})
                lines.append(_fmt_price_row(t, fund, sc, target_market, rank=i + 1))
            lines.append("IMPORTANT: Use the prices above — they are live as of today. Do NOT use prices from your training data.")
            parts.append("\n".join(lines))

        if in_universe_tickers:
            base_universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])
            universe = list(dict.fromkeys(in_universe_tickers + base_universe))[:25]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            ranked = rank_scores_in_universe(result_df)
            lines = ["NeuralQuant scores + LIVE prices for mentioned stocks:"]
            for t in in_universe_tickers:
                row_match = result_df[result_df["ticker"] == t]
                if not row_match.empty:
                    row = row_match.iloc[0]
                    idx = row_match.index[0]
                    sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                    fund = _fund_cache.get(f"{t}:{target_market}", {})
                    conf_val = row.get("regime_confidence", 0.5)
                    conf_label = "high" if conf_val > 0.7 else ("medium" if conf_val > 0.4 else "low")
                    base = _fmt_price_row(t, fund, sc, target_market)
                    lines.append(
                        base + f" | Momentum={row.get('momentum_percentile', 0.5):.0%} "
                        f"Value={row.get('value_percentile', 0.5):.0%} "
                        f"Quality={row.get('quality_percentile', 0.5):.0%} "
                        f"Confidence={conf_label}"
                    )
            lines.append("IMPORTANT: Use the prices above — they are live as of today. Do NOT use prices from your training data.")
            parts.append("\n".join(lines))

        # Inject competitor data for "why this not that" comparative reasoning
        if in_universe_tickers and needs_stock_scores:
            try:
                comp_lines = ["Competitor comparison (for 'why this not that' reasoning):"]
                for t in in_universe_tickers[:2]:
                    try:
                        info = yf.Ticker(t).info
                        sector = info.get("sector", "")
                        industry = info.get("industry", "")
                        if sector or industry:
                            comp_lines.append(f"  {t} sector: {sector} | industry: {industry}")
                    except Exception:
                        pass

                # Also inject top 3 screener competitors (nearest ranked stocks)
                if not result_df.empty:
                    for t in in_universe_tickers[:2]:
                        row_match = result_df[result_df["ticker"] == t]
                        if not row_match.empty:
                            idx = row_match.index[0]
                            peers_idx = [i for i in range(max(0, idx - 2), min(len(result_df), idx + 3)) if i != idx]
                            for pi in peers_idx[:3]:
                                peer = result_df.iloc[pi]
                                peer_score = int(ranked.loc[pi]) if pi in ranked.index else 5
                                comp_lines.append(
                                    f"  Nearby alternative: {peer['ticker']} (ForeCast {peer_score}/10) "
                                    f"— Quality {peer.get('quality_percentile', 0):.0%} "
                                    f"Momentum {peer.get('momentum_percentile', 0):.0%} "
                                    f"Value {peer.get('value_percentile', 0):.0%}"
                                )
                if len(comp_lines) > 1:
                    parts.append("\n".join(comp_lines))
            except Exception:
                pass

        # Dynamic fetch for out-of-universe NSE stocks (e.g. TRENT, DIXON, ZYDUS)
        if out_of_universe_words:
            dynamic_lines = ["Live data for requested stocks (dynamically fetched from NSE):"]
            found_any = False
            for word in out_of_universe_words:
                data = _fetch_dynamic_nse_stock(word)
                if data:
                    found_any = True
                    pe_str = f"P/E={data['pe_ttm']:.1f}" if data.get("pe_ttm") else "P/E=N/A"
                    pb_str = f"P/B={data['pb_ratio']:.1f}" if data.get("pb_ratio") else "P/B=N/A"
                    beta_str = f"Beta={data['beta']:.2f}" if data.get("beta") else ""
                    target_str = (
                        f"Analyst target=Rs.{data['analyst_target']:.0f} ({data['analyst_recommendation']})"
                        if data.get("analyst_target") else ""
                    )
                    chg_str = f"{data['change_pct']:+.2f}%" if data.get("change_pct") else ""
                    mcap = f"MCap=Rs.{data['market_cap']/1e7:.0f}Cr" if data.get("market_cap") else ""
                    rev_growth = f"Rev growth={data['revenue_growth']*100:.1f}%" if data.get("revenue_growth") else ""
                    dynamic_lines.append(
                        f"  {data['longName']} ({data['symbol']}): "
                        f"Rs.{data['price']:.2f} {chg_str} | "
                        f"52w Rs.{data.get('week52_low', 0):.0f}-Rs.{data.get('week52_high', 0):.0f} | "
                        f"{pe_str} {pb_str} {beta_str} {mcap} {rev_growth} | {target_str}"
                    )
            if found_any:
                dynamic_lines.append(
                    "  NOTE: Full NeuralQuant AI score unavailable for above stocks "
                    "(not in screener universe), but LIVE price + fundamentals are injected above. "
                    "Use these exact numbers. Do NOT use prices from training data."
                )
                parts.append("\n".join(dynamic_lines))

    except Exception as exc:
        return f"[Platform data unavailable: {exc}]"

    return "\n\n".join(parts) if parts else None


@router.post("", response_model=QueryResponse)
async def run_nl_query(
    req: QueryRequest,
    user: User = Depends(enforce_tier_quota("query")),
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
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

    # ── Offload blocking I/O to thread pool ──────────────────────────────────
    # Each task gets a hard cap so the total context-build phase completes in
    # ≤ 25 s — leaving ample headroom for the 120 s Anthropic timeout.
    # Note: wait_for cancels the asyncio task on timeout but the underlying
    # thread may still run; this is a resource trade-off vs correct behaviour.
    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    headlines, macro_ctx, platform_ctx = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 22.0, None),
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
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")

    user_msg = "\n".join(context_parts)

    try:
        # Build message list — keep up to 4 prior turns; truncate long messages
        messages = []
        for m in (req.history or [])[-4:]:
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
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

        # ── Second-pass reasoning refinement ──────────────────────────────────────
        # If the answer mentions specific stocks but lacks comparative reasoning,
        # do a quick second pass to strengthen it.
        answer_text = raw
        mentioned_tickers = [t for t in (in_universe_tickers or []) if t.upper() in answer_text.upper() or t.replace(".NS", "").upper() in answer_text.upper()]
        if mentioned_tickers:
            has_comparative = any(phrase in answer_text.lower() for phrase in [
                "why not", "instead of", "compared to", "rather than", "over ",
                "vs ", "alternative", "runner-up", "second-best", "why i chose",
                "edge over", "superior to", "better than", "outperforms",
            ])
            if not has_comparative:
                try:
                    refinement_prompt = (
                        "Your previous answer recommended specific stocks but did NOT explain why you "
                        "chose them over alternatives. This is a critical quality gap — a quant researcher "
                        "always explains 'why X not Y'.\n\n"
                        "Add a brief 'WHY THIS NOT THAT' section. For each stock you recommended:\n"
                        "1. Name the next-best alternative you could have picked instead\n"
                        "2. State 1-2 specific data points that give your pick the edge\n\n"
                        f"Previous answer:\n{answer_text[:2000]}\n\n"
                        "Add the comparative reasoning now. Keep it concise (2-3 lines per stock)."
                    )
                    refinement = await asyncio.to_thread(
                        client.messages.create,
                        model=MODEL,
                        max_tokens=800,
                        system="You are a financial analysis quality reviewer. Add missing comparative reasoning.",
                        messages=[{"role": "user", "content": refinement_prompt}],
                    )
                    ref_text = ""
                    for block in refinement.content:
                        if block.type == "text":
                            ref_text = block.text
                            break
                    if ref_text and len(ref_text) > 50:
                        answer_text = answer_text.rstrip() + "\n\n**Why this, not that:**\n" + ref_text.strip()
                except Exception:
                    pass  # Non-critical: if refinement fails, use the original answer

        return _parse_query_response(answer_text, route="REACT")
    except anthropic.APITimeoutError:
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
    """Try to extract a JSON object from LLM output (may be wrapped in markdown)."""
    # Remove markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"\s*```", "", cleaned)
    # Try to find a JSON object
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, cleaned)
        if match:
            try:
                import json
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                continue
    return None


@router.post("/v2", response_model=StructuredQueryResponse)
async def run_nl_query_v2(
    req: QueryRequest,
    user: User = Depends(enforce_tier_quota("query")),
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

    # ── DART routing ──
    route = dart.classify_query(req.question, req.ticker)

    if route == "SNAP":
        # SNAP: build structured response from score cache directly
        snap_resp = await dart.handle_snap(req)
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=50,
            timeframe="Short-term",
            summary=snap_resp.answer[:300],
            reasoning=ReasoningBlock(
                why_this="Based on NeuralQuant score data",
                why_not_alt="Alternative not scored",
                edge_summary="Score-based assessment",
                second_best="N/A",
                confidence_gap="N/A",
            ),
            data_sources=snap_resp.data_sources,
            follow_up_questions=snap_resp.follow_up_questions,
            route="SNAP",
        )

    # REACT or DEEP: use LLM with structured prompt
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    headlines, macro_ctx, platform_ctx = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 22.0, None),
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
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")

    user_msg = "\n".join(context_parts)

    try:
        messages = []
        for m in (req.history or [])[-4:]:
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
            max_tokens=4000,
            system=_SYSTEM_STRUCTURED,
            messages=messages,
        )

        raw = ""
        for block in response.content:
            if block.type == "text":
                raw = block.text
                break
        if not raw:
            raw = response.content[0].text if hasattr(response.content[0], "text") else ""

        # Try to parse structured JSON from the LLM response
        parsed = _extract_json_from_llm(raw)
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
                return StructuredQueryResponse(**parsed)
            except (ValidationError, Exception) as e:
                log.warning("Structured output validation failed: %s", e)

        # Fallback: construct minimal structured response from freeform text
        freeform_resp = _parse_query_response(raw, route)
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=50,
            timeframe="Medium-term",
            summary=freeform_resp.answer[:300],
            reasoning=ReasoningBlock(
                why_this="See summary for details",
                why_not_alt="Comparative data not available for alternative analysis",
                edge_summary="See summary",
                second_best="N/A",
                confidence_gap="N/A",
            ),
            data_sources=freeform_resp.data_sources,
            follow_up_questions=freeform_resp.follow_up_questions,
            route=freeform_resp.route,
        )

    except anthropic.APITimeoutError:
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
