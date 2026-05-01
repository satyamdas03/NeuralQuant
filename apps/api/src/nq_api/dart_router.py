"""DART Query Router — tiered query classification and fast-path handlers."""
from __future__ import annotations

import asyncio
import logging
import math
import re
from typing import Literal

import yfinance as yf

from nq_api.schemas import QueryRequest, QueryResponse, AnalystResponse
from nq_api.cache import score_cache
from nq_api.universe import US_DEFAULT, IN_DEFAULT
from nq_api.data_builder import build_real_snapshot, fetch_real_macro, fetch_real_macro_in, _fund_cache
from nq_api.deps import get_signal_engine
from nq_api.score_builder import _score_to_1_10
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.routes.analyst import _fetch_finnhub_data

log = logging.getLogger(__name__)

Route = Literal["SNAP", "REACT", "DEEP"]

# ── Classification patterns ──────────────────────────────────────────────

# Force REACT regardless of other signals
_REACT_FORCERS = {
    "compare", "versus", "vs ", "portfolio", "allocate", "allocation",
    "best stock", "top stock", "top pick", "recommend", "should i buy",
    "should i sell", "which stock", "screener", "rank", "ranking",
    "difference between", "better than", "worse than", "pros and cons",
    "strengths and weaknesses", "name specific", "name shares", "name stocks",
    "invest", "suggest", "where to put", "return target", "target return",
    "top 3", "top 5", "top 10", "best pick", "best picks",
    "how do", "what are", "list of", "give me", "show me",
}

_SNAP_TRIGGERS = {
    "price", "current price", "trading at", "market cap", "pe ratio", "p/e",
    "pb ratio", "p/b", "dividend yield", "dividend", "yield", "beta",
    "52 week", "52-week", "fifty two", "high", "low", "volume", "change",
    "how much", "what is the price", "quote", "ticker info", "stock info",
    "company info", "summary", "quick", "live price", "today's price",
    "last price", "closing price", "open price", "day high", "day low",
}

_DEEP_TRIGGERS = {
    "deep dive", "full analysis", "comprehensive analysis", "detailed analysis",
    "thorough analysis", "factor breakdown", "regime aware", "regime-aware",
    "investment thesis", "bull case", "bear case", "analyst report",
    "para-debate", "paradebate", "institutional analysis", "regime analysis",
    "quality analysis", "momentum analysis", "value analysis",
    "fundamental analysis", "technical analysis", "risk analysis", "stress test",
    "breakdown", "due diligence", "dd on", "conviction", "thesis",
    "long thesis", "short thesis", "regime outlook", "factor outlook",
}

_SNAP_STOP_WORDS = {
    "why", "how will", "what if", "forecast", "predict", "scenario",
    "outlook", "trend", "future", "expect", "going to", "will it",
    "should i", "buy or", "sell or", "hold or", "recommendation",
    "analysis", "evaluate", "assess",
}


def classify_query(question: str, explicit_ticker: str | None = None) -> Route:
    """Classify a natural-language query into SNAP, REACT, or DEEP."""
    q = question.strip().lower()
    short_query = len(question.strip()) <= 60
    has_ticker = explicit_ticker is not None or _extract_ticker_from_question(question) is not None

    # 1. Force REACT for comparative / portfolio / screener queries
    if any(k in q for k in _REACT_FORCERS):
        return "REACT"

    # 2. Check for DEEP signals
    has_deep = any(k in q for k in _DEEP_TRIGGERS)
    if has_deep:
        # If it also looks like a comparison, stay REACT
        if any(k in q for k in {"compare", "versus", "vs ", "better", "worse"}):
            return "REACT"
        return "DEEP"

    # 3. Check for SNAP signals
    has_snap = any(k in q for k in _SNAP_TRIGGERS)
    has_uncertainty = any(k in q for k in _SNAP_STOP_WORDS)

    if has_snap and not has_uncertainty and (short_query or has_ticker):
        return "SNAP"

    # 4. Long, single-ticker queries without comparison → DEEP
    if len(question.strip()) > 120 and has_ticker and not any(k in q for k in _REACT_FORCERS):
        return "DEEP"

    # 5. Default to REACT
    return "REACT"


# ── Ticker extraction helpers ─────────────────────────────────────────────

_KNOWN_TICKERS = set(US_DEFAULT) | set(IN_DEFAULT)
_NSE_NAME_MAP_LOWER = {
    "trent": "TRENT.NS", "titan": "TITAN.NS", "zomato": "ZOMATO.NS",
    "nykaa": "NYKAA.NS", "paytm": "PAYTM.NS", "dmart": "DMART.NS",
    "zydus": "ZYDUSLIFE.NS", "dixon": "DIXON.NS", "irctc": "IRCTC.NS",
    "pidilite": "PIDILITIND.NS", "eicher": "EICHERMOT.NS",
    "bajaj finance": "BAJFINANCE.NS", "hdfc": "HDFCBANK.NS",
    "icici": "ICICIBANK.NS", "kotak": "KOTAKBANK.NS",
    "reliance": "RELIANCE.NS", "infosys": "INFY.NS",
    "wipro": "WIPRO.NS", "hcltech": "HCLTECH.NS",
    "sunpharma": "SUNPHARMA.NS", "drreddy": "DRREDDY.NS",
    "cipla": "CIPLA.NS", "maruti": "MARUTI.NS",
    "tata motors": "TATAMOTORS.NS", "tata steel": "TATASTEEL.NS",
    "tcs": "TCS.NS", "adani": "ADANIENT.NS", "hindalco": "HINDALCO.NS",
    "ongc": "ONGC.NS", "ntpc": "NTPC.NS", "powergrid": "POWERGRID.NS",
    "coal india": "COALINDIA.NS", "sbin": "SBIN.NS", "sbi": "SBIN.NS",
    "axis bank": "AXISBANK.NS", "indusind bank": "INDUSINDBK.NS",
    "bajaj finsv": "BAJAJFINSV.NS", "nestle": "NESTLEIND.NS",
    "asian paints": "ASIANPAINT.NS", "ultratech": "ULTRACEMCO.NS",
    "grasim": "GRASIM.NS", "tech mahindra": "TECHM.NS",
    "mphasis": "MPHASIS.NS", "persistent": "PERSISTENT.NS",
    "coforge": "COFORGE.NS", "tata power": "TATAPOWER.NS",
    "jsw energy": "JSWENERGY.NS", "polycab": "POLYCAB.NS",
    "bharti airtel": "BHARTIARTL.NS", "jsw steel": "JSWSTEEL.NS",
    "havells": "HAVELLS.NS", "voltas": "VOLTAS.NS",
    "crompton": "CROMPTON.NS", "abfrl": "ABFRL.NS",
    "minda": "MINDAIND.NS", "varun beverages": "VARUNBEV.NS",
    "jubilant foodworks": "JUBLFOOD.NS", "dominos": "JUBLFOOD.NS",
    "apollo hospital": "APOLLOHOSP.NS", "fortis": "FORTIS.NS",
    "max health": "MAXHEALTH.NS", "mankind": "MANKIND.NS",
    "alkem": "ALKEM.NS", "torrent pharma": "TORNTPHARM.NS",
    "deepak nitrite": "DEEPAKNTR.NS", "gland": "GLAND.NS",
    "laurus labs": "LAURUSLABS.NS",
}


def _extract_ticker_from_question(question: str) -> str | None:
    """Try to extract a known ticker from the question text."""
    q = question.upper()
    # Check explicit 1-5 char uppercase words that match known tickers
    for word in re.findall(r"\b[A-Z]{1,5}\b", q):
        if word in _KNOWN_TICKERS:
            return word
    # Check NSE name map
    for name, ticker in _NSE_NAME_MAP_LOWER.items():
        if re.search(r'\b' + re.escape(name.upper()) + r'\b', q):
            return ticker
    return None


# ── SNAP handler ─────────────────────────────────────────────────────────

async def handle_snap(req: QueryRequest) -> QueryResponse:
    """Return fast factual response using cached or live data — no LLM call."""
    ticker = req.ticker
    if not ticker:
        ticker = _extract_ticker_from_question(req.question)

    if not ticker:
        return QueryResponse(
            answer="Please specify a ticker symbol for a quick factual answer.",
            data_sources=[],
            follow_up_questions=[
                "What is the price of AAPL?",
                "Show me TCS market cap",
                "What is HDFC Bank's P/E?",
            ],
            route="SNAP",
        )

    market = req.market or "US"
    ticker_upper = ticker.upper()

    # Try score cache first (sub-100ms) — tiered fallback like screener/stocks
    cached = None
    try:
        cached = await asyncio.to_thread(score_cache.read_one, ticker_upper, market, 300)
        if not cached:
            cached = await asyncio.to_thread(score_cache.read_one, ticker_upper, market, 86400)
            if cached:
                log.info("SNAP: serving stale cache (>%5min) for %s/%s", ticker_upper, market)
        if not cached:
            cached = await asyncio.to_thread(score_cache.read_one, ticker_upper, market, 999999999)
            if cached:
                log.warning("SNAP: serving very old cache for %s/%s", ticker_upper, market)
    except Exception as exc:
        log.warning("SNAP score_cache read failed for %s: %s", ticker_upper, exc)

    # Try in-memory fund cache for live price (instant)
    fund = _fund_cache.get(f"{ticker_upper}:{market}", {})

    if cached or fund:
        snap = _build_snap_from_cache(cached, fund, ticker_upper, market)
        if snap:
            return snap

    # Fallback: yfinance direct lookup
    try:
        snap = await asyncio.to_thread(_fetch_snap_yfinance, ticker_upper, market)
        if snap:
            return snap
    except Exception as exc:
        log.warning("SNAP yfinance fallback failed for %s: %s", ticker_upper, exc)

    return QueryResponse(
        answer=f"Quick data for {ticker_upper} is currently unavailable. Try again in a moment.",
        data_sources=["yfinance"],
        follow_up_questions=[
            f"Deep-dive analysis on {ticker_upper}",
            "Compare with peers",
            "Show screener top picks",
        ],
        route="SNAP",
    )


def _build_snap_from_cache(
    row: dict | None, fund: dict, ticker: str, market: str
) -> QueryResponse | None:
    """Format a score_cache row + fund_cache into a SNAP QueryResponse."""
    if not row and not fund:
        return None

    price = fund.get("current_price") if fund else None
    score = row.get("composite_score") if row else None
    pe = (row.get("pe_ttm") if row else None) or (fund.get("pe_ttm") if fund else None)
    pb = (row.get("pb_ratio") if row else None) or (fund.get("pb_ratio") if fund else None)
    beta = (row.get("beta") if row else None) or (fund.get("beta") if fund else None)
    mcap = fund.get("market_cap") if fund else None
    week52_high = fund.get("week52_high") if fund else None
    week52_low = fund.get("week52_low") if fund else None
    change_pct = fund.get("change_pct") if fund else None
    long_name = fund.get("long_name") if fund else ticker

    # If we have absolutely no useful data, return None so caller tries yfinance
    if price is None and score is None and pe is None and pb is None:
        return None

    score_10 = None
    if score is not None:
        score_10 = _score_to_1_10(float(score))

    is_india = market == "IN" or ticker.endswith(".NS") or ticker.endswith(".BO")
    cur = "Rs." if is_india else "$"

    lines = [f"**{long_name} ({ticker})** — NeuralQuant Quick Snapshot"]
    if score_10 is not None:
        lines.append(f"AI Score: {score_10}/10")
    if price is not None:
        price_str = f"Price: {cur}{price:,.2f}"
        if change_pct is not None:
            price_str += f" ({change_pct:+.2f}%)"
        lines.append(price_str)
    if mcap:
        if is_india:
            lines.append(f"Market Cap: {cur}{mcap/1e7:,.0f} Cr")
        else:
            lines.append(f"Market Cap: {cur}{mcap/1e9:,.1f}B")
    if pe is not None:
        lines.append(f"P/E (TTM): {pe:.1f}")
    if pb is not None:
        lines.append(f"P/B: {pb:.2f}")
    if beta is not None:
        lines.append(f"Beta: {beta:.2f}")
    if week52_low is not None and week52_high is not None:
        lines.append(f"52-Week Range: {cur}{week52_low:,.2f} – {cur}{week52_high:,.2f}")

    answer = "\n".join(lines)

    return QueryResponse(
        answer=answer,
        data_sources=["NeuralQuant Score Cache", "yfinance"],
        follow_up_questions=[
            f"Deep-dive analysis on {ticker}",
            f"How does {ticker} compare to its sector?",
            "What is the current market regime?",
        ],
        route="SNAP",
    )


def _fetch_snap_yfinance(ticker: str, market: str) -> QueryResponse | None:
    """Direct yfinance lookup for SNAP fallback."""
    sym = ticker
    if market == "IN" and "." not in ticker:
        sym = ticker + ".NS"

    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None

        is_india = market == "IN" or ticker.endswith(".NS") or ticker.endswith(".BO")
        cur = "Rs." if is_india else "$"

        name = info.get("longName") or ticker
        mcap = info.get("marketCap")
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        beta = info.get("beta")
        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low = info.get("fiftyTwoWeekLow")
        change_pct = info.get("regularMarketChangePercent")

        lines = [f"**{name} ({ticker})** — Live Snapshot"]
        price_str = f"Price: {cur}{price:,.2f}"
        if change_pct is not None:
            price_str += f" ({change_pct:+.2f}%)"
        lines.append(price_str)
        if mcap:
            if is_india:
                lines.append(f"Market Cap: {cur}{mcap/1e7:,.0f} Cr")
            else:
                lines.append(f"Market Cap: {cur}{mcap/1e9:,.1f}B")
        if pe:
            lines.append(f"P/E (TTM): {pe:.1f}")
        if pb:
            lines.append(f"P/B: {pb:.2f}")
        if beta:
            lines.append(f"Beta: {beta:.2f}")
        if week52_low and week52_high:
            lines.append(f"52-Week Range: {cur}{week52_low:,.2f} – {cur}{week52_high:,.2f}")

        return QueryResponse(
            answer="\n".join(lines),
            data_sources=["yfinance"],
            follow_up_questions=[
                f"NeuralQuant AI score for {ticker}",
                f"Should I buy {ticker}?",
                "Show me the top-ranked stocks",
            ],
            route="SNAP",
        )
    except Exception:
        return None


# ── DEEP handler ─────────────────────────────────────────────────────────


def _fetch_macro_in_with_timeout_dart() -> dict:
    """Fetch India macro data with timeout for DEEP route."""
    try:
        macro_in = fetch_real_macro_in()
        if macro_in is None:
            return {}
        return {
            "india_vix": round(macro_in.india_vix, 2),
            "nifty_vs_200ma": round(macro_in.nifty_vs_200ma * 100, 2),
            "nifty_return_1m": round(macro_in.nifty_return_1m * 100, 2),
            "inr_usd": round(macro_in.inr_usd, 2),
            "rbi_repo_rate": round(macro_in.rbi_repo_rate, 2),
            "sensex_close": round(macro_in.sensex_close, 0),
        }
    except Exception:
        return {}


def _build_analyst_context(ticker: str, market: str, engine) -> dict:
    """Synchronous context builder — runs in a thread pool."""
    from nq_api.universe import UNIVERSE_BY_MARKET
    universe = list(UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]))
    if ticker not in universe:
        universe = [ticker] + universe[:19]

    snapshot = build_real_snapshot(universe, market)
    result_df = engine.compute(snapshot)
    macro = fetch_real_macro()

    # India macro data (only when market=IN)
    macro_in = _fetch_macro_in_with_timeout_dart() if market == "IN" else {}

    # Regime label — use India VIX thresholds for IN market
    if market == "IN" and macro_in:
        vix_for_regime = macro_in.get("india_vix", 15.0)
    else:
        vix_for_regime = macro.vix

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    if market == "IN":
        if vix_for_regime < 14:
            regime_label = "Risk-On"
        elif vix_for_regime < 20:
            regime_label = "Late-Cycle"
        else:
            regime_label = "Bear"
    else:
        regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}
        regime_label = regime_labels.get(regime_id, "Risk-On")

    context = {
        "market": market,
        "regime_label": regime_label,
        "vix": round(macro.vix, 2),
        "spx_return_1m": round(macro.spx_return_1m * 100, 2),
        "spx_vs_200ma": round(macro.spx_vs_200ma * 100, 2),
        "hy_spread_oas": round(macro.hy_spread_oas, 1),
        "ism_pmi": round(macro.ism_pmi, 1),
        "yield_spread_2y10y": round(macro.yield_spread_2y10y, 3),
        "yield_10y": round(macro.yield_10y, 2),
        "yield_2y": round(macro.yield_2y, 2),
        "cpi_yoy": round(macro.cpi_yoy, 2),
        "fed_funds_rate": round(macro.fed_funds_rate, 2),
        "fred_sourced": macro.fred_sourced,
        **macro_in,
    }

    matching = result_df[result_df["ticker"] == ticker]
    if not matching.empty:
        row = matching.iloc[0]
        def _r(key, cast=float, default=None):
            v = row.get(key)
            if v is None or (isinstance(v, float) and not math.isfinite(v)):
                return default
            try:
                return cast(v)
            except (TypeError, ValueError):
                return default

        context.update({
            "sector": str(row.get("sector", "") or "") or None,
            "composite_score": round(_r("composite_score", default=0.5), 4),
            "quality_percentile": round(_r("quality_percentile", default=0.5), 3),
            "momentum_percentile": round(_r("momentum_percentile", default=0.5), 3),
            "value_percentile": round(_r("value_percentile", default=0.5), 3),
            "low_vol_percentile": round(_r("low_vol_percentile", default=0.5), 3),
            "short_interest_percentile": round(_r("short_interest_percentile", default=0.5), 3),
            "short_interest_pct": round(_r("short_interest_pct"), 4) if _r("short_interest_pct") is not None else None,
            "momentum_raw": round(_r("momentum_raw"), 4) if _r("momentum_raw") is not None else None,
            "gross_profit_margin": round(_r("gross_profit_margin"), 3) if _r("gross_profit_margin") is not None else None,
            "piotroski": int(row.get("piotroski", 5)),
            "pe_ttm": round(_r("pe_ttm"), 1) if _r("pe_ttm") is not None else None,
            "pb_ratio": round(_r("pb_ratio"), 2) if _r("pb_ratio") is not None else None,
            "beta": round(_r("beta"), 2) if _r("beta") is not None else None,
            "realized_vol_1y": round(_r("realized_vol_1y"), 3) if _r("realized_vol_1y") is not None else None,
            "current_price": round(_r("current_price"), 2) if _r("current_price") is not None else None,
            "analyst_target_mean": round(_r("analyst_target"), 2) if _r("analyst_target") is not None else None,
            "market_cap": _r("market_cap") if _r("market_cap") is not None else None,
            "insider_cluster_score": round(_r("insider_cluster_score"), 2) if _r("insider_cluster_score") is not None else None,
            "accruals_ratio": round(_r("accruals_ratio"), 4) if _r("accruals_ratio") is not None else None,
            "revenue_growth_yoy": round(_r("revenue_growth_yoy"), 4) if _r("revenue_growth_yoy") is not None else None,
            "debt_equity": round(_r("debt_equity"), 2) if _r("debt_equity") is not None else None,
        })

    # Sector median comparison (for agent context)
    sector = context.get("sector", "")
    if sector and sector != "Unknown":
        try:
            from nq_api.cache.score_cache import read_sector_median
            sector_medians = read_sector_median(sector, market)
            if sector_medians:
                for k, v in sector_medians.items():
                    if v is not None:
                        context[f"sector_median_{k}"] = round(v, 3)
        except Exception:
            pass

    # Finnhub enrichment (technical indicators, insider, news sentiment)
    finnhub_data = _fetch_finnhub_data(ticker, market)
    if finnhub_data:
        if finnhub_data.get("insider_cluster_score") is not None:
            context["insider_cluster_score"] = finnhub_data.pop("insider_cluster_score")
        if finnhub_data.get("insider_summary"):
            context["insider_summary"] = finnhub_data.pop("insider_summary")
        if finnhub_data.get("insider_net_buy_ratio") is not None:
            context["insider_net_buy_ratio"] = finnhub_data.pop("insider_net_buy_ratio")
        if finnhub_data.get("news_sentiment_label"):
            context["news_sentiment"] = finnhub_data.pop("news_sentiment_label")
            context["news_sentiment_score"] = finnhub_data.pop("news_sentiment_score")
            context["news_buzz"] = finnhub_data.pop("news_buzz")
        for k, v in finnhub_data.items():
            if k not in context:
                context[k] = v

    return context


def _build_context_from_cache(ticker: str, market: str) -> dict | None:
    """Fast path: build analyst context from Supabase score_cache."""
    cached = None
    try:
        # Tier 1: fresh cache (≤15 min)
        cached = score_cache.read_one(ticker, market, max_age_seconds=900)
        if not cached:
            # Tier 2: stale cache (≤24 h) — nightly GHA data
            cached = score_cache.read_one(ticker, market, max_age_seconds=86400)
            if cached:
                log.info("DEEP context: serving stale cache (>%15min) for %s/%s", ticker, market)
        if not cached:
            # Tier 3: any age — better than no data
            cached = score_cache.read_one(ticker, market, max_age_seconds=999999999)
            if cached:
                log.warning("DEEP context: serving very old cache for %s/%s", ticker, market)
    except Exception:
        return None
    if not cached:
        return None

    try:
        macro = fetch_real_macro()
        # India macro data (only when market=IN)
        macro_in = _fetch_macro_in_with_timeout_dart() if market == "IN" else {}

        # Regime label — use India VIX thresholds for IN market
        if market == "IN" and macro_in:
            vix_for_regime = macro_in.get("india_vix", 15.0)
        else:
            vix_for_regime = macro.vix

        regime_id = cached.get("regime_id", 1)
        if market == "IN":
            if vix_for_regime < 14:
                regime_label = "Risk-On"
            elif vix_for_regime < 20:
                regime_label = "Late-Cycle"
            else:
                regime_label = "Bear"
        else:
            regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}
            regime_label = regime_labels.get(regime_id, "Risk-On")

        def _c(key, default=0.0):
            """Get cached value, returning None if missing (not default)."""
            v = cached.get(key)
            if v is None or v == 0 and key not in cached:
                return None
            return v

        context = {
            "market": market,
            "regime_label": regime_label,
            "vix": round(macro.vix, 2),
            "spx_return_1m": round(macro.spx_return_1m * 100, 2),
            "spx_vs_200ma": round(macro.spx_vs_200ma * 100, 2),
            "hy_spread_oas": round(macro.hy_spread_oas, 1),
            "ism_pmi": round(macro.ism_pmi, 1),
            "yield_spread_2y10y": round(macro.yield_spread_2y10y, 3),
            "yield_10y": round(macro.yield_10y, 2),
            "yield_2y": round(macro.yield_2y, 2),
            "cpi_yoy": round(macro.cpi_yoy, 2),
            "fed_funds_rate": round(macro.fed_funds_rate, 2),
            "fred_sourced": macro.fred_sourced,
            **macro_in,
            # Stock-specific fields from cache
            "sector": cached.get("sector") or "Unknown",
            "composite_score": round(float(cached.get("composite_score", 0.5)), 4),
            "quality_percentile": round(float(cached.get("quality_percentile", 0.5)), 3),
            "momentum_percentile": round(float(cached.get("momentum_percentile", 0.5)), 3),
            "value_percentile": round(float(cached.get("value_percentile", 0.5)), 3),
            "low_vol_percentile": round(float(cached.get("low_vol_percentile", 0.5)), 3),
            "short_interest_percentile": round(float(cached.get("short_interest_percentile", 0.5)), 3),
            "pe_ttm": round(float(cached.get("pe_ttm")), 1) if cached.get("pe_ttm") is not None else None,
            "current_price": round(float(cached.get("current_price")), 2) if cached.get("current_price") is not None else None,
            "analyst_target_mean": round(float(cached.get("analyst_target")), 2) if cached.get("analyst_target") is not None else None,
            "market_cap": float(cached.get("market_cap")) if cached.get("market_cap") is not None else None,
            # Fields added by migration 005 — may be None if migration not yet run
            "momentum_raw": round(float(cached["momentum_raw"]), 4) if cached.get("momentum_raw") is not None else None,
            "gross_profit_margin": round(float(cached["gross_profit_margin"]), 3) if cached.get("gross_profit_margin") is not None else None,
            "piotroski": int(cached["piotroski"]) if cached.get("piotroski") is not None else None,
            "pb_ratio": round(float(cached["pb_ratio"]), 2) if cached.get("pb_ratio") is not None else None,
            "beta": round(float(cached["beta"]), 2) if cached.get("beta") is not None else None,
            "realized_vol_1y": round(float(cached["realized_vol_1y"]), 3) if cached.get("realized_vol_1y") is not None else None,
            "short_interest_pct": round(float(cached["short_interest_pct"]), 4) if cached.get("short_interest_pct") is not None else None,
            "insider_cluster_score": round(float(cached["insider_cluster_score"]), 2) if cached.get("insider_cluster_score") is not None else None,
            "accruals_ratio": round(float(cached["accruals_ratio"]), 4) if cached.get("accruals_ratio") is not None else None,
            "revenue_growth_yoy": round(float(cached["revenue_growth_yoy"]), 4) if cached.get("revenue_growth_yoy") is not None else None,
            "debt_equity": round(float(cached["debt_equity"]), 2) if cached.get("debt_equity") is not None else None,
        }

        # Sector median comparison (for agent context)
        sector = context.get("sector", "")
        if sector and sector != "Unknown":
            try:
                from nq_api.cache.score_cache import read_sector_median
                sector_medians = read_sector_median(sector, market)
                if sector_medians:
                    for k, v in sector_medians.items():
                        if v is not None:
                            context[f"sector_median_{k}"] = round(v, 3)
            except Exception:
                pass

        # Finnhub enrichment (technical indicators, insider, news sentiment)
        finnhub_data = _fetch_finnhub_data(ticker, market)
        if finnhub_data:
            if finnhub_data.get("insider_cluster_score") is not None:
                context["insider_cluster_score"] = finnhub_data.pop("insider_cluster_score")
            if finnhub_data.get("insider_summary"):
                context["insider_summary"] = finnhub_data.pop("insider_summary")
            if finnhub_data.get("insider_net_buy_ratio") is not None:
                context["insider_net_buy_ratio"] = finnhub_data.pop("insider_net_buy_ratio")
            if finnhub_data.get("news_sentiment_label"):
                context["news_sentiment"] = finnhub_data.pop("news_sentiment_label")
                context["news_sentiment_score"] = finnhub_data.pop("news_sentiment_score")
                context["news_buzz"] = finnhub_data.pop("news_buzz")
            for k, v in finnhub_data.items():
                if k not in context:
                    context[k] = v

        return context
    except Exception as e:
        log.warning("cache context build failed for %s: %s", ticker, e)
        return None


def _synthesize_analyst_response(resp: AnalystResponse) -> QueryResponse:
    """Convert AnalystResponse into a QueryResponse."""
    lines = [
        f"**{resp.ticker} — {resp.head_analyst_verdict}**",
        "",
        f"Consensus Score: {resp.consensus_score:.2f}/1.0",
        "",
        f"**Investment Thesis:**\n{resp.investment_thesis}",
        "",
        f"**Bull Case:**\n{resp.bull_case}",
        "",
        f"**Bear Case:**\n{resp.bear_case}",
    ]
    if resp.risk_factors:
        lines.extend(["", "**Key Risk Factors:**"])
        for rf in resp.risk_factors:
            lines.append(f"- {rf}")

    if resp.agent_outputs:
        lines.extend(["", "**Agent Perspectives:**"])
        for ao in resp.agent_outputs:
            lines.append(f"- **{ao.agent}** ({ao.stance}, {ao.conviction}): {ao.thesis}")

    answer = "\n".join(lines)

    followups = [
        f"What is the live price of {resp.ticker}?",
        f"Compare {resp.ticker} with its top peer",
        "What is the current market regime outlook?",
    ]

    return QueryResponse(
        answer=answer,
        data_sources=["NeuralQuant PARA-DEBATE", "FRED Macro", "Live Fundamentals", "yfinance"],
        follow_up_questions=followups,
        route="DEEP",
    )


async def handle_deep(req: QueryRequest) -> QueryResponse:
    """Trigger PARA-DEBATE and synthesize the result into a QueryResponse."""
    ticker = req.ticker
    if not ticker:
        ticker = _extract_ticker_from_question(req.question)

    if not ticker:
        return QueryResponse(
            answer="Please specify a ticker symbol for a deep-dive analysis.",
            data_sources=[],
            follow_up_questions=[
                "Deep dive on AAPL",
                "Full analysis of RELIANCE.NS",
                "What is the current regime?",
            ],
            route="DEEP",
        )

    market = req.market or "US"
    ticker_upper = ticker.upper()
    engine = get_signal_engine()

    # Cache-first context build
    context = await asyncio.to_thread(_build_context_from_cache, ticker_upper, market)
    if context is None:
        # On Render, skip yfinance (rate-limited) — return error instead of 25s hang
        import os
        if os.environ.get("RENDER"):
            log.warning("DEEP: cache empty for %s/%s on Render, skipping rate-limited yfinance", ticker_upper, market)
            return QueryResponse(
                answer=f"Deep-dive analysis for {ticker_upper} is being refreshed. Please retry in 1-2 minutes.",
                data_sources=["NeuralQuant PARA-DEBATE"],
                follow_up_questions=[
                    f"Quick snapshot of {ticker_upper}",
                    f"Compare {ticker_upper} with peers",
                    "Show top-ranked stocks",
                ],
                route="DEEP",
            )
        context = await asyncio.to_thread(_build_analyst_context, ticker_upper, market, engine)

    orch = ParaDebateOrchestrator()
    try:
        analyst_resp = await orch.analyse(ticker=ticker_upper, market=market, context=context)
        return _synthesize_analyst_response(analyst_resp)
    except Exception as exc:
        log.exception("DEEP route PARA-DEBATE failed for %s: %s", ticker_upper, exc)
        return QueryResponse(
            answer=(
                f"Deep-dive analysis for {ticker_upper} is temporarily unavailable. "
                "Please try again shortly."
            ),
            data_sources=["NeuralQuant PARA-DEBATE"],
            follow_up_questions=[
                f"Quick snapshot of {ticker_upper}",
                f"Compare {ticker_upper} with peers",
                "Show top-ranked stocks",
            ],
            route="DEEP",
        )
