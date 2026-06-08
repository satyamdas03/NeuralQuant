"""Data enrichment -- macro context, news, technical indicators, platform data."""
import logging
import re
import threading
import time
from datetime import date as _date

import yfinance as yf
import pandas as pd

from nq_api.services.constants import (
    _SECTOR_MAP, _STOP_WORDS, _TICKER_STOP_WORDS,
    _INDIA_KEYWORDS, _SCREENER_KEYWORDS,
)

logger = logging.getLogger(__name__)
log = logging.getLogger(__name__)

# ── In-memory platform data cache ────────────────────────────────────────────
# Caches _enrich_with_platform_data results for 10 minutes per (ticker_hint, market).
# This avoids re-running expensive _fetch_one / FMP calls for repeated queries
# about the same stock within a short window (e.g., conversation follow-ups).
_PLATFORM_CACHE: dict[str, tuple[float, str]] = {}  # key -> (timestamp, result_str)
_PLATFORM_CACHE_TTL = 600  # 10 minutes
_PLATFORM_CACHE_LOCK = threading.Lock()
_PLATFORM_CACHE_MAX = 200  # max entries to prevent unbounded growth


def _fmt_mcap(mcap, market: str) -> str:
    """Format market cap for display in competitor context."""
    if mcap is None:
        return "N/A"
    cur = "Rs." if market == "IN" else "$"
    try:
        mcap = float(mcap)
    except (TypeError, ValueError):
        return "N/A"
    if market == "IN":
        if mcap >= 1e13:
            return f"{cur}{mcap/1e13:.1f}L Cr"
        elif mcap >= 1e11:
            return f"{cur}{mcap/1e11:.1f}K Cr"
        else:
            return f"{cur}{mcap/1e7:.0f} Cr"
    else:
        if mcap >= 1e12:
            return f"{cur}{mcap/1e12:.1f}T"
        elif mcap >= 1e9:
            return f"{cur}{mcap/1e9:.1f}B"
        else:
            return f"{cur}{mcap/1e6:.0f}M"


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 8) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    from nq_api.data_builder import _get_yf_session
    import os as _os
    _is_render = bool(_os.environ.get("RENDER"))

    # On Render: yfinance hangs on cloud IPs — skip entirely, use Finnhub news instead
    if _is_render:
        return []

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
    """Fetch Finnhub news with full summaries + article body extraction for richer Ask AI context."""
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
            url = a.get("url", "")
            title = a.get("title", "")
            summary = a.get("summary", "")
            source = a.get("source", "")

            # Attempt to fetch full article body from URL
            body = _fetch_article_body(url) if url else ""

            results.append({
                "title": title,
                "summary": summary,
                "body": body,
                "source": source,
                "url": url,
            })
        return results
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return []


def _fetch_article_body(url: str, timeout: float = 5.0, max_len: int = 2000) -> str:
    """Fetch and extract readable text from a news article URL.

    Uses httpx for fast fetching + basic HTML tag stripping.
    Returns empty string on any failure (paywall, timeout, etc.).
    Intentionally lightweight — no heavy NLP deps.
    """
    import re as _re
    try:
        import httpx
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; QuantAlpha/2.0)"},
            )
            if resp.status_code != 200:
                return ""
            html = resp.text
            if not html or len(html) < 200:
                return ""
    except Exception:
        return ""

    # Strip scripts, styles, and HTML tags
    try:
        text = _re.sub(r"<script[^>]*>.*?</script>", "", html, flags=_re.DOTALL | _re.IGNORECASE)
        text = _re.sub(r"<style[^>]*>.*?</style>", "", text, flags=_re.DOTALL | _re.IGNORECASE)
        text = _re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = _re.sub(r"&nbsp;", " ", text)
        text = _re.sub(r"&amp;", "&", text)
        text = _re.sub(r"&lt;", "<", text)
        text = _re.sub(r"&gt;", ">", text)
        text = _re.sub(r"&quot;", "\"", text)
        text = _re.sub(r"&#\d+;", " ", text)
        text = _re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""

    if len(text) < 100:
        return ""
    return text[:max_len]


def _fetch_enrichment(ticker: str | None, market: str = "US") -> dict:
    """Fetch technical indicators + insider + news sentiment for Ask AI.
    Cache-first: reads from enrichment_cache (1h TTL) before live fetch.
    Falls back to stale cache when Finnhub is rate-limited.
    Stale cache is capped at 24h max age to avoid serving very old prices."""
    _MAX_STALE_AGE_SECONDS = 86400  # 24 hours — avoid serving days-old price data
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
        # Finnhub returned empty (rate-limited). Try stale cache with age guard.
        try:
            stale = read_enrichment_stale(ticker, market)
            if stale:
                # Check staleness — enrichment_cache has a cached_at field we can inspect
                # read_enrichment_stale already removes metadata fields, but we can check
                # the age by seeing if any price-like values are wildly off
                log.warning('Ask AI enrichment stale cache fallback for %s/%s: %d fields (may be >1h old)',
                            ticker, market, len(stale))
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
                log.warning('Ask AI enrichment stale cache fallback (after error) for %s/%s: %d fields',
                            ticker, market, len(stale))
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

    Results are cached in-memory for 10 minutes per (ticker_hint, market) to
    avoid re-running expensive enrichment on conversation follow-ups.
    """
    from nq_api.data_builder import _fetch_one
    from nq_api.cache import score_cache
    from nq_api.services.parsing import _detect_tickers_in_question

    # ── In-memory cache check ──────────────────────────────────────────────
    # Build a cache key from the question's detected tickers + market.
    # This avoids re-running expensive _fetch_one / FMP calls for the same
    # stock within a 10-minute window (e.g., conversation follow-ups).
    _cache_tickers, _ = _detect_tickers_in_question(question, market)
    _cache_key = f"{','.join(sorted(_cache_tickers))}:{market}:{question[:60].upper()}"
    with _PLATFORM_CACHE_LOCK:
        if _cache_key in _PLATFORM_CACHE:
            _ts, _cached_result = _PLATFORM_CACHE[_cache_key]
            if time.time() - _ts < _PLATFORM_CACHE_TTL:
                log.info("Platform data cache HIT for key=%s (age=%ds)", _cache_key[:40], int(time.time() - _ts))
                return _cached_result

    # On Render cloud, _fetch_one uses yfinance internally which is frequently
    # rate-limited on cloud IPs. Skip it and rely on FMP batch quotes only.
    import os as _os
    _is_render = bool(_os.environ.get("RENDER"))

    # ── Timing instrumentation ──────────────────────────────────────────────
    _t0 = time.monotonic()

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
                    ns_tickers = [
                        t if "." in t else f"{t}.NS" for t in all_tickers
                    ]
                    bo_tickers = [t.replace(".NS", ".BO") for t in ns_tickers]
                    all_tickers = ns_tickers + bo_tickers
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
                # Pre-fetch FMP batch quotes for top 5 screener stocks (bypasses _fetch_one cache)
                if not fmp_prices and fmp_client._enabled:
                    try:
                        top_tickers = [row.get("ticker", "") for row in cached[:5] if row.get("ticker")]
                        if top_tickers:
                            fmp_prices = fmp_client.get_batch_quotes(top_tickers) or {}
                    except Exception:
                        pass
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
                    n_live = 5  # all markets get live prices for top 5
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
                            if not price and not _is_render:
                                fund = _fetch_one(t, target_market, fast_pe=True)
                                price = fund.get("current_price")
                                chg = fund.get("change_pct") or 0
                        else:
                            if not _is_render:
                                fund = _fetch_one(t, target_market, fast_pe=False)
                                price = fund.get("current_price")
                                chg = fund.get("change_pct") or 0
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
                    if _is_render:
                        # On Render: skip _fetch_one (yfinance rate-limited), use FMP batch quotes
                        fmp_fb = (fmp_prices.get(t)
                                  or fmp_prices.get(f"{t}.NS")
                                  or fmp_prices.get(f"{t}.BO")
                                  or {})
                        price = fmp_fb.get("price")
                        chg = fmp_fb.get("change_pct", 0) or 0
                        fund = {"current_price": price, "change_pct": chg, "_is_real": bool(price)}
                    else:
                        fund = _fetch_one(t, target_market, fast_pe=False)
                    if fund.get("_is_real"):
                        price = fund.get("current_price")
                        chg = fund.get("change_pct") or 0
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
            for t in in_universe_tickers[:10]:
                if _is_render:
                    # On Render: use FMP batch quotes only, skip _fetch_one (yfinance)
                    fmp_fb = (fmp_prices.get(t)
                              or fmp_prices.get(f"{t}.NS")
                              or fmp_prices.get(f"{t}.BO")
                              or {})
                    fund = {"current_price": fmp_fb.get("price"), "change_pct": fmp_fb.get("change_pct", 0) or 0, "pe_ttm": None, "_is_real": bool(fmp_fb.get("price"))}
                else:
                    fund = _fetch_one(t, target_market, fast_pe=False)
                cached_row = cache_map.get(t, {})
                sc = int(cached_row.get("composite_score", 0.5) * 10) if cached_row else "N/A"
                price = fund.get("current_price")
                chg = fund.get("change_pct") or 0
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
                if chg is not None: detail_parts.append(f"CHANGE={chg:+.1f}%")
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
                # ── Expanded analyst enrichment fields (20+ field expansion) ──
                analyst_target_high = fund.get("analyst_target_high")
                analyst_target_low = fund.get("analyst_target_low")
                roic = fund.get("roic")
                short_ratio = fund.get("short_ratio")
                avg_vol = fund.get("avg_volume")
                institutional_pct = fund.get("institutional_ownership")
                insider_pct = fund.get("insider_pct")
                fwd_pe = fund.get("forward_pe")
                rev_growth = fund.get("revenue_growth_yoy")
                profit_margin = fund.get("profit_margin")
                operating_margin = fund.get("operating_margin")
                dividend_yield = fund.get("dividend_yield")
                ev_ebitda = fund.get("ev_ebitda")
                peg = fund.get("trailing_peg_ratio") or fund.get("peg_ratio")
                fcf = fund.get("free_cashflow")
                num_analysts = fund.get("number_of_analyst_opinions")
                fifty_day_avg = fund.get("fifty_day_average")
                two_hundred_day_avg = fund.get("two_hundred_day_average")
                if analyst_target_high: detail_parts.append(f"AnalystTargetHigh={cur}{analyst_target_high:,.0f} {_marker('analyst_target_high')}")
                if analyst_target_low: detail_parts.append(f"AnalystTargetLow={cur}{analyst_target_low:,.0f} {_marker('analyst_target_low')}")
                if roic is not None: detail_parts.append(f"ROIC={float(roic)*100:.1f}% {_marker('roic')}")
                if short_ratio is not None: detail_parts.append(f"ShortRatio={float(short_ratio):.1f} {_marker('short_ratio')}")
                if avg_vol: detail_parts.append(f"AvgVol={int(avg_vol):,} {_marker('avg_volume')}")
                if institutional_pct is not None: detail_parts.append(f"Institutional={float(institutional_pct)*100:.0f}% {_marker('institutional_ownership')}")
                if insider_pct is not None: detail_parts.append(f"Insider={float(insider_pct)*100:.0f}% {_marker('insider_pct')}")
                if fwd_pe: detail_parts.append(f"FwdP/E={float(fwd_pe):.1f} {_marker('forward_pe')}")
                if rev_growth is not None: detail_parts.append(f"RevGrowthYoY={float(rev_growth):.1f}% {_marker('revenue_growth_yoy')}")
                if profit_margin is not None: detail_parts.append(f"NetMargin={float(profit_margin)*100:.1f}% {_marker('profit_margin')}")
                if operating_margin is not None: detail_parts.append(f"OpMargin={float(operating_margin)*100:.1f}% {_marker('operating_margin')}")
                if dividend_yield is not None: detail_parts.append(f"DivYield={float(dividend_yield):.2f}% {_marker('dividend_yield')}")
                if ev_ebitda: detail_parts.append(f"EV/EBITDA={float(ev_ebitda):.1f} {_marker('ev_ebitda')}")
                if peg: detail_parts.append(f"PEG={float(peg):.2f} {_marker('peg_ratio')}")
                if fcf: detail_parts.append(f"FCF={int(fcf):,} {_marker('free_cashflow')}")
                if num_analysts: detail_parts.append(f"NumAnalysts={int(num_analysts)} {_marker('number_of_analyst_opinions')}")
                if fifty_day_avg: detail_parts.append(f"SMA50={float(fifty_day_avg):,.2f} {_marker('fifty_day_average')}")
                if two_hundred_day_avg: detail_parts.append(f"SMA200={float(two_hundred_day_avg):,.2f} {_marker('two_hundred_day_average')}")
                momentum = cached_row.get("momentum_percentile")
                quality = cached_row.get("quality_percentile")
                if momentum: detail_parts.append(f"Momentum={momentum:.0%}")
                if quality: detail_parts.append(f"Quality={quality:.0%}")
                # Label with full name + exchange for IN stocks so LLM recognizes the entity
                label = t
                if target_market == "IN":
                    exchange_sym = f"{t}.NS" if "." not in t else t
                    long_name = fund.get("long_name") or ""
                    label = f"{t} (NSE: {exchange_sym})"
                    if long_name and long_name != t:
                        label = f"{long_name} -- {label}"
                lines.append(f"  {label}: {' | '.join(detail_parts)}")
            lines.append("")
            lines.append("⚠ MANDATORY: ALL values marked [VERIFIED] are REAL live data (FMP primary, yfinance fallback) for TODAY. Fields not shown are unavailable -- do NOT invent them. P/E, Beta, Price, Market Cap change after earnings, splits, and volatility shifts. Your training data is WRONG for these values. ALWAYS quote the EXACT [VERIFIED] values shown above.")
            parts.append("\n".join(lines))

        # Inject competitor comparison with deep fundamentals + FMP peers
        if in_universe_tickers and needs_stock_scores:
            try:
                from nq_api.data_builder import _fetch_yf_info_cached
                from nq_api.cache import score_cache as _sc_comp
                from nq_data.fmp import get_fmp_client as _get_fmp

                comp_lines = ["Competitor deep-dive:"]
                primary_ticker = in_universe_tickers[0] if in_universe_tickers else None

                # Primary stock sector/industry context
                for t in in_universe_tickers[:2]:
                    if _is_render:
                        # On Render: skip _fetch_yf_info_cached (yfinance hangs on cloud IPs)
                        # Use FMP profile data already in fmp_prices
                        fmp_fb = (fmp_prices.get(t)
                                  or fmp_prices.get(f"{t}.NS")
                                  or fmp_prices.get(f"{t}.BO")
                                  or {})
                        if fmp_fb.get("sector"):
                            comp_lines.append(f"  {t} sector: {fmp_fb.get('sector', '')} | industry: {fmp_fb.get('industry', '')}")
                        continue
                    try:
                        info = _fetch_yf_info_cached(t)
                        if info.get("_cached_ok"):
                            sector = info.get("sector", "")
                            industry = info.get("industry", "")
                            if sector or industry:
                                comp_lines.append(f"  {t} sector: {sector} | industry: {industry}")
                    except Exception:
                        pass

                # ── FMP stock peers: industry-based alternatives ──
                fmp_peer_tickers: list[str] = []
                if primary_ticker:
                    try:
                        fmp = _get_fmp_client()
                        if fmp._enabled:
                            raw_peers = fmp.get_stock_peers(primary_ticker)
                            if raw_peers:
                                # Normalise: strip .NS/.BO for IN, keep as-is for US
                                for p in raw_peers[:5]:
                                    p_clean = p.replace(".NS", "").replace(".BO", "") if target_market == "IN" else p
                                    if p_clean.upper() != primary_ticker.upper():
                                        fmp_peer_tickers.append(p_clean)
                                fmp_peer_tickers = fmp_peer_tickers[:3]  # max 3 peers
                    except Exception:
                        log.debug("FMP stock_peers lookup failed for %s", primary_ticker)

                # Show FMP peers with live metrics + brief comparison
                if fmp_peer_tickers:
                    comp_lines.append(f"  Industry peers (FMP): {', '.join(fmp_peer_tickers)}")
                    # Batch-quote FMP peers for fast price/P/E
                    fmp_peer_quotes: dict[str, dict] = {}
                    try:
                        fmp = _get_fmp_client()
                        if fmp._enabled and fmp_peer_tickers:
                            peer_syms = list(fmp_peer_tickers)
                            if target_market == "IN":
                                peer_syms = [t if "." in t else f"{t}.NS" for t in peer_syms]
                            fmp_peer_quotes = fmp.get_batch_quotes(peer_syms) or {}
                    except Exception:
                        pass
                    # Primary stock metrics for comparison
                    primary_data = None
                    try:
                        if not _is_render:
                            primary_data = _fetch_one(primary_ticker, target_market)
                    except Exception:
                        pass
                    # On Render: use FMP batch quotes for primary stock data
                    if not primary_data:
                        fmp_q = (fmp_prices.get(primary_ticker)
                                 or fmp_prices.get(f"{primary_ticker}.NS")
                                 or fmp_peer_quotes.get(primary_ticker)
                                 or {})
                        if fmp_q.get("price"):
                            primary_data = {"current_price": fmp_q["price"], "pe_ttm": fmp_q.get("pe"), "market_cap": fmp_q.get("market_cap")}
                    primary_pe = primary_data.get("pe_ttm") if primary_data else None
                    primary_mcap = primary_data.get("market_cap") if primary_data else None
                    primary_price = primary_data.get("current_price") if primary_data else None

                    for pt in fmp_peer_tickers:
                        if _is_render:
                            peer_metrics = None  # skip _fetch_one on Render
                        else:
                            peer_metrics = _fetch_one(pt, target_market) if pt not in (in_universe_tickers or []) else None
                        if not peer_metrics:
                            # Try FMP batch quotes fallback
                            fmp_q = (fmp_peer_quotes.get(pt)
                                     or fmp_peer_quotes.get(f"{pt}.NS")
                                     or fmp_peer_quotes.get(f"{pt}.BO")
                                     or {})
                            if fmp_q.get("price"):
                                p_price = fmp_q.get("price")
                                p_pe = fmp_q.get("pe")
                                p_mcap = fmp_q.get("market_cap")
                                comparison = ""
                                cur = "Rs." if target_market == "IN" else "$"
                                if p_pe and primary_pe:
                                    comparison = f" vs primary P/E {primary_pe:.1f}" if primary_pe else ""
                                comp_lines.append(
                                    f"  {pt}: Price={cur}{p_price:,.2f}"
                                    f" | P/E={p_pe:.1f if p_pe else 'N/A'}"
                                    f" | MCap={_fmt_mcap(p_mcap, target_market)}"
                                    f"{comparison}"
                                )
                            continue
                        # Full metrics from _fetch_one
                        p_price = peer_metrics.get("current_price")
                        p_pe = peer_metrics.get("pe_ttm")
                        p_mcap = peer_metrics.get("market_cap")
                        p_roe = peer_metrics.get("roe")
                        p_margin = peer_metrics.get("gross_profit_margin")
                        cur = "Rs." if target_market == "IN" else "$"
                        comp_parts = [f"ForeCast=N/A"]
                        if p_price:
                            comp_parts.append(f"Price={cur}{p_price:,.2f}")
                        if p_pe is not None:
                            comp_parts.append(f"P/E={p_pe:.1f}")
                        if p_mcap:
                            comp_parts.append(f"MCap={_fmt_mcap(p_mcap, target_market)}")
                        if p_roe is not None:
                            comp_parts.append(f"ROE={p_roe:.1%}" if isinstance(p_roe, float) and p_roe < 1 else f"ROE={p_roe}")
                        # Brief comparison vs primary
                        comparisons = []
                        if p_pe and primary_pe:
                            pe_diff = p_pe - primary_pe
                            comparisons.append(f"P/E {'higher' if pe_diff > 0 else 'lower'} by {abs(pe_diff):.1f}")
                        if p_mcap and primary_mcap:
                            if primary_mcap > 0:
                                cap_ratio = p_mcap / primary_mcap
                                comparisons.append(f"market cap {cap_ratio:.1f}x primary")
                        if comparisons:
                            comp_parts.append(f"({', '.join(comparisons)})")
                        comp_lines.append(f"  {pt}: {' | '.join(comp_parts)} [VERIFIED]")

                # Show nearby alternatives from cache with deep fundamentals (screener-ranked)
                cached_all = _sc_comp.read_top(target_market, 50, max_age_seconds=300)
                if not cached_all:
                    cached_all = _sc_comp.read_top(target_market, 50, max_age_seconds=86400)
                if not cached_all:
                    cached_all = _sc_comp.read_top(target_market, 50, max_age_seconds=999999999)
                if cached_all:
                    cache_map = {r.get("ticker"): r for r in cached_all}
                    primary_rank = next((i for i, r in enumerate(cached_all) if r.get("ticker") == primary_ticker), -1)
                    # Pick top 2 peers (rank-1 and rank+1 around the primary)
                    peer_indices = []
                    for offset in [-1, 1]:
                        pi = primary_rank + offset
                        if 0 <= pi < len(cached_all) and pi != primary_rank:
                            peer_indices.append(pi)
                    for pi in peer_indices[:2]:
                        peer = cached_all[pi]
                        peer_ticker = peer.get("ticker", "?")
                        # Skip if already shown as FMP peer
                        if peer_ticker in fmp_peer_tickers:
                            continue
                        peer_sc = int(peer.get("composite_score", 0.5) * 10)
                        comp_lines.append(
                            f"  Alternative: {peer_ticker} (ForeCast {peer_sc}/10)"
                            f" -- Quality {peer.get('quality_percentile', 0):.0%}"
                            f" Momentum {peer.get('momentum_percentile', 0):.0%}"
                        )
                        # Deep fundamentals for peer (skip _fetch_one on Render — use FMP batch quotes instead)
                        try:
                            if _is_render:
                                # On Render: skip _fetch_one, use FMP batch quotes
                                fmp_fb_peer = (fmp_prices.get(peer_ticker)
                                               or fmp_prices.get(f"{peer_ticker}.NS")
                                               or fmp_prices.get(f"{peer_ticker}.BO")
                                               or {})
                                if fmp_fb_peer.get("price"):
                                    peer_data = {
                                        "current_price": fmp_fb_peer.get("price"),
                                        "pe_ttm": fmp_fb_peer.get("pe"),
                                        "pb_ratio": None, "beta": None,
                                        "market_cap": fmp_fb_peer.get("market_cap"),
                                        "roe": None, "gross_profit_margin": None,
                                    }
                                else:
                                    peer_data = None
                            else:
                                peer_data = _fetch_one(peer_ticker, target_market)
                            if peer_data and not peer_data.get("long_name", "").startswith("Empty"):
                                comp_lines.append(
                                    f"    {peer_ticker} deep: "
                                    f"Price=${peer_data.get('current_price', 'N/A')} "
                                    f"P/E={peer_data.get('pe_ttm', 'N/A')} "
                                    f"P/B={peer_data.get('pb_ratio', 'N/A')} "
                                    f"Beta={peer_data.get('beta', 'N/A')} "
                                    f"MCap={peer_data.get('market_cap', 'N/A')} "
                                    f"ROE={peer_data.get('roe', 'N/A')} "
                                    f"Margin={peer_data.get('gross_profit_margin', 'N/A')}"
                                )
                        except Exception:
                            pass  # Skip peer fundamentals on error
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
        log.exception("_enrich_with_platform_data failed: %s", exc)
        return f"[Platform data unavailable: {exc}]"

    result = "\n\n".join(parts) if parts else None
    _elapsed = time.monotonic() - _t0
    if result:
        log.info("PLATFORM_CTX length=%d chars, parts=%d, elapsed=%.1fs", len(result), len(parts), _elapsed)
    else:
        log.warning("PLATFORM_CTX is EMPTY/NONE — parts=%d, elapsed=%.1fs", len(parts), _elapsed)

    # ── Store in-memory cache ──────────────────────────────────────────────
    if result:
        with _PLATFORM_CACHE_LOCK:
            _PLATFORM_CACHE[_cache_key] = (time.time(), result)
            # Evict oldest entries if cache is too large
            if len(_PLATFORM_CACHE) > _PLATFORM_CACHE_MAX:
                oldest_key = min(_PLATFORM_CACHE, key=lambda k: _PLATFORM_CACHE[k][0])
                del _PLATFORM_CACHE[oldest_key]

    return result


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
