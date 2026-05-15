"""Data enrichment -- macro context, news, technical indicators, platform data."""
import logging
import re
from datetime import date as _date

import yfinance as yf
import pandas as pd

from nq_api.services.constants import (
    _SECTOR_MAP, _STOP_WORDS, _TICKER_STOP_WORDS,
    _INDIA_KEYWORDS, _SCREENER_KEYWORDS,
)

logger = logging.getLogger(__name__)
log = logging.getLogger(__name__)


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 8) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    from nq_api.data_builder import _get_yf_session

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
    from nq_api.data_builder import _yf_symbol
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
        pass  # Cache miss -- fall through to live fetch
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


def _fetch_india_macro() -> str | None:
    """Fetch India-specific market context: Nifty 50, Sensex, INR/USD, India VIX."""
    from nq_api.data_builder import _get_yf_session

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
                + (" [FRED-sourced]" if macro.fred_sourced else " [OpenBB-sourced]")
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


def _fetch_dynamic_nse_stock(word: str) -> dict | None:
    """
    Try to fetch live data for an NSE stock not in our screener universe.
    word: uppercase stock name/ticker from user query.
    Returns a dict with price, fundamentals, or None if not found.
    Tries yfinance first, falls back to FMP for price data.
    """
    from nq_api.services.constants import _NSE_NAME_MAP
    from nq_api.data_builder import _get_yf_session

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


def _enrich_with_platform_data(question: str, market: str) -> str | None:
    """
    Fetch NeuralQuant's own stock scores + live prices when the question needs them.
    Uses score_cache (instant) + _fetch_one (2-5s per stock) instead of
    build_real_snapshot (30-120s for full universe).
    """
    from nq_api.data_builder import _fetch_one
    from nq_api.cache import score_cache
    from nq_api.services.parsing import _detect_tickers_in_question

    q_upper = question.upper()
    parts: list[str] = []
    target_market = "IN" if any(k in q_upper for k in _INDIA_KEYWORDS) else market

    needs_screener = any(k in q_upper for k in _SCREENER_KEYWORDS)
    in_universe_tickers, out_of_universe_words = _detect_tickers_in_question(question, target_market)

    # Auto-detect IN market when all in-universe tickers are Indian (no India keywords needed)
    if target_market != "IN" and in_universe_tickers:
        from nq_api.universe import IN_DEFAULT
        in_set = set(IN_DEFAULT)
        if all(t in in_set for t in in_universe_tickers):
            target_market = "IN"
            log.info("Auto-detected IN market from tickers: %s", in_universe_tickers)
    needs_stock_scores = (
        in_universe_tickers
        or out_of_universe_words
        or any(k in q_upper for k in ["IS A BUY", "IS A SELL", "COMPARE", "VERSUS", "VS ", "OVERVALUED", "SHORT INTEREST"])
    )

    if not needs_screener and not needs_stock_scores:
        return None

    try:
        # Pre-fetch FMP batch quotes for all detected tickers (single API call, ~200ms)
        # Falls back gracefully -- returns {} if FMP disabled or fails
        fmp_prices: dict[str, dict] = {}
        try:
            from nq_data.fmp import get_fmp_client
            fmp_client = get_fmp_client()
            if fmp_client._enabled:
                # Ensure IN tickers have .NS suffix -- FMP requires it for NSE stocks
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
                lines = [f"NeuralQuant {target_market} Screener -- Top 20 (cached scores). LIVE PRICES for top 5 -- USE THESE, NOT training data:"]
                for i, row in enumerate(cached[:20]):
                    t = row.get("ticker", "")
                    sc = int(row.get("composite_score", 0.5) * 10)
                    pe = row.get("pe_ttm")
                    gpm = row.get("gross_profit_margin")
                    momentum = row.get("momentum_percentile")
                    quality = row.get("quality_percentile")
                    value = row.get("value_percentile")
                    # Fetch live price for top stocks (first N)
                    # IN: FMP batch quotes first (fast, already pre-fetched), _fetch_one only as fallback
                    # US: _fetch_one first (FMP direct, sub-2s)
                    n_live = 3 if target_market == "IN" else 5
                    if i < n_live:
                        price = None
                        chg = 0
                        if target_market == "IN":
                            # Try FMP batch quotes first for IN -- yfinance unreliable on Render
                            fmp_fb = (fmp_prices.get(t)
                                      or fmp_prices.get(f"{t}.NS")
                                      or fmp_prices.get(f"{t}.BO")
                                      or {})
                            if fmp_fb.get("price"):
                                price = fmp_fb["price"]
                                chg = fmp_fb.get("change_pct", 0) or 0
                            if not price:
                                fund = _fetch_one(t, target_market, fast_pe=True)
                                price = fund.get("current_price")
                                chg = fund.get("change_pct", 0)
                        else:
                            fund = _fetch_one(t, target_market, fast_pe=False)
                            price = fund.get("current_price")
                            chg = fund.get("change_pct", 0)
                            # FMP batch-quote fallback
                            if not price:
                                fmp_fb = (fmp_prices.get(t) or {})
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
                lines.append("IMPORTANT: Live prices for top 5, rest cached. Do NOT use prices from training data -- stocks may have split (e.g. NVDA 10:1 in June 2024). [VERIFIED] values are from live data and MUST be used exactly.")
                parts.append("\n".join(lines))
            else:
                # No cache -- fetch top 5 stocks only (fast)
                from nq_api.universe import UNIVERSE_BY_MARKET
                top_tickers = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])[:5]
                lines = [f"NeuralQuant {target_market} -- Quick scan (live prices):"]
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
            lines = [f"CRITICAL -- LIVE MARKET DATA AS OF {today_str} -- USE THESE EXACT PRICES, NOT YOUR TRAINING DATA:"]
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
                # FMP batch-quote fallback -- critical for IN stocks where yfinance fails on cloud IPs
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
                missing_fields = fund.get("_is_synthetic", set())
                def _marker(field_name: str) -> str:
                    """All displayed values are real (FMP or yfinance). Missing fields not shown."""
                    return "[VERIFIED]" if field_name not in missing_fields else "[UNAVAILABLE]"
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
                        if mcap >= 1e13: detail_parts.append(f"Mcap=Rs.{mcap/1e13:.1f}L Cr {mcap_marker}")
                        elif mcap >= 1e11: detail_parts.append(f"Mcap=Rs.{mcap/1e11:.1f}K Cr {mcap_marker}")
                        else: detail_parts.append(f"Mcap=Rs.{mcap/1e7:.0f} Cr {mcap_marker}")
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
            lines.append("⚠ MANDATORY: ALL values marked [VERIFIED] are REAL live data (FMP primary, yfinance fallback) for TODAY. Fields not shown are unavailable -- do NOT invent them. P/E, Beta, Price, Market Cap change after earnings, splits, and volatility shifts. Your training data is WRONG for these values. ALWAYS quote the EXACT [VERIFIED] values shown above.")
            parts.append("\n".join(lines))

        # Inject competitor comparison for specific stocks
        if in_universe_tickers and needs_stock_scores:
            try:
                from nq_api.data_builder import _fetch_yf_info_cached

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
                                        f"-- Quality {peer.get('quality_percentile', 0):.0%} "
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


def _enrich_snap_structured(req) -> tuple[list, "ReasoningBlock", str]:
    """Build metrics and reasoning from score cache for SNAP responses."""
    from nq_api.cache import score_cache
    from nq_api.score_builder import _score_to_1_10
    from nq_api.schemas import MetricItem, ReasoningBlock

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
                    why_not_alt = f"{alt_ticker} scores {alt_10}/10 -- selected stock has {'higher' if score_10 >= alt_10 else 'comparable'} composite score"
                    confidence_gap = f"ForeCast {score_10} vs {alt_10}, {'+' if score_10 >= alt_10 else ''}{score_10 - alt_10} edge"
                    edge_summary = f"ForeCast {score_10}/10 vs {alt_ticker}'s {alt_10}/10"
                    break
        except Exception:
            pass

    return metrics, ReasoningBlock(
        why_this=why_this, why_not_alt=why_not_alt,
        edge_summary=edge_summary, second_best=second_best, confidence_gap=confidence_gap,
    ), verdict
