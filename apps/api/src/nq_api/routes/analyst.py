"""POST /analyst — runs PARA-DEBATE and returns full analyst report.

/analyst        — standard JSON response (for backward compat; legacy path)
/analyst/stream — Server-Sent Events streaming response (preferred)
                  Sends keep-alive pings every 10s so Render never drops the
                  idle connection during the 60–120 s multi-agent debate.
"""
import asyncio
import json
import logging
import os
import time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import yfinance as yf
from nq_api.schemas import AnalystRequest, AnalystResponse, AgentOutput
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.deps import get_current_user_optional
from nq_api.auth.models import User
from nq_api.cache import score_cache
from nq_api.data_builder import _yf_symbol
logger = logging.getLogger(__name__)

log = logging.getLogger(__name__)
router = APIRouter()


def _safe_float(val, default=0.0):
    """Convert val to float, treating None and missing keys as default."""
    if val is None:
        return float(default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return float(default)

def _is_ollama() -> bool:
    """Runtime Ollama detection — avoids module-level env var issues in uvicorn."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


# Hard timeouts — ensures customers never wait >2min total
# Longer when using Ollama (local models are slower than Anthropic API)
# Evaluated at runtime, not import time, so load_dotenv works correctly
def _phase_timeouts():
    if _is_ollama():
        return 60, 420  # 7 agents sequentially at ~60s each
    return 45, 180  # Phase 1: context build (45s), Phase 2: debate (3 min for Sonnet)
MACRO_FETCH_TIMEOUT = 15


def _fetch_macro_with_timeout() -> dict:
    """Fetch macro data with a hard timeout — returns defaults on failure."""
    import concurrent.futures
    from nq_api.data_builder import fetch_real_macro

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fetch_real_macro)
            macro = future.result(timeout=MACRO_FETCH_TIMEOUT)
    except (concurrent.futures.TimeoutError, Exception) as exc:
        log.warning("Macro fetch timed out or failed (%s), using defaults", exc)
        macro = None

    if macro is None:
        return {
            "vix": 18.0, "spx_return_1m": 0.01, "spx_vs_200ma": 0.02,
            "hy_spread_oas": 350.0, "ism_pmi": 51.0,
            "yield_spread_2y10y": 0.10, "yield_10y": 4.2, "yield_2y": 4.1,
            "cpi_yoy": 3.0, "fed_funds_rate": 5.25, "fred_sourced": False,
        }

    return {
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
    }


def _fetch_macro_in_with_timeout() -> dict:
    """Fetch India macro data with a hard timeout — returns defaults on failure."""
    import concurrent.futures
    from nq_api.data_builder import fetch_real_macro_in

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fetch_real_macro_in)
            macro_in = future.result(timeout=MACRO_FETCH_TIMEOUT)
    except (concurrent.futures.TimeoutError, Exception) as exc:
        log.warning("India macro fetch timed out or failed (%s), using defaults", exc)
        macro_in = None

    if macro_in is None:
        return {
            "india_vix": 15.0, "nifty_vs_200ma": 2.0,
            "nifty_return_1m": 1.0, "inr_usd": 83.0,
            "rbi_repo_rate": 6.50, "sensex_close": 72000.0,
        }

    return {
        "india_vix": round(macro_in.india_vix, 2),
        "nifty_vs_200ma": round(macro_in.nifty_vs_200ma * 100, 2),
        "nifty_return_1m": round(macro_in.nifty_return_1m * 100, 2),
        "inr_usd": round(macro_in.inr_usd, 2),
        "rbi_repo_rate": round(macro_in.rbi_repo_rate, 2),
        "sensex_close": round(macro_in.sensex_close, 0),
    }


def _build_analyst_context(ticker: str, market: str) -> dict:
    """Fast context builder: fetch data for ONE ticker only, not the full universe.

    On cold start, building the full 503-ticker universe takes 2-5 minutes.
    The analysts only need the target ticker's fundamentals + macro data,
    so we fetch just that ticker (1-3 yfinance calls, ~2-5s total).
    Percentiles are estimated from raw values since we don't have the universe.
    """
    from nq_api.data_builder import _fetch_one

    # 1. Macro data (cached after first call; 15s timeout handled by caller)
    macro = _fetch_macro_with_timeout()
    # 1b. India macro data (only when market=IN)
    macro_in = _fetch_macro_in_with_timeout() if market == "IN" else {}

    # 2. Fundamentals for just the requested ticker (1-3 yfinance calls, ~2-5s)
    fund = _fetch_one(ticker, market)

    # 3. Regime from macro (VIX-based heuristic — use India VIX for IN market)
    if market == "IN" and macro_in:
        vix = macro_in.get("india_vix", 15.0)
    else:
        vix = macro.get("vix", 18.0)
    if market == "IN":
        # India VIX thresholds are lower (typically 10-25 range)
        if vix < 14:
            regime_label = "Risk-On"
        elif vix < 20:
            regime_label = "Late-Cycle"
        else:
            regime_label = "Bear"
    else:
        if vix < 20:
            regime_label = "Risk-On"
        elif vix < 30:
            regime_label = "Late-Cycle"
        else:
            regime_label = "Bear"

    # 4. Build context from the single ticker's data
    # Percentiles are estimated from raw values since we don't rank the full universe.
    gpm = _safe_float(fund.get("gross_profit_margin"), 0.5)
    mom = _safe_float(fund.get("momentum_raw"), 0.0)
    vol = _safe_float(fund.get("realized_vol_1y"), 0.20)
    si  = _safe_float(fund.get("short_interest_pct"), 0.02)

    # Rough composite: quality 30%, momentum 25%, value 20%, low-vol 15%, short-int 10%
    quality_p = min(1.0, max(0.0, gpm))  # gross margin ≈ quality percentile
    momentum_p = min(1.0, max(0.0, 0.5 + mom * 0.5))  # map momentum to 0-1
    value_p = 1.0 / max(0.5, _safe_float(fund.get("pe_ttm"), 20.0) / 20.0)  # lower PE = higher value
    lowvol_p = 1.0 / max(0.5, vol / 0.15)  # lower vol = higher low-vol score
    shortint_p = 1.0 - min(1.0, si * 5)  # lower SI = higher score

    composite = (0.30 * quality_p + 0.25 * momentum_p + 0.20 * value_p
                 + 0.15 * lowvol_p + 0.10 * shortint_p)

    # Additional stock-specific fields agents reference
    try:
        info = yf.Ticker(_yf_symbol(ticker, market)).info or {}
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        info = {}

    context = {
        "market": market,
        "regime_label": regime_label,
        **macro,
        **macro_in,
        "composite_score":           round(composite, 4),
        "quality_percentile":        round(quality_p, 3),
        "momentum_percentile":       round(momentum_p, 3),
        "value_percentile":          round(value_p, 3),
        "low_vol_percentile":        round(lowvol_p, 3),
        "low_short_interest_rank":   round(shortint_p, 3),
        "short_interest_pct":        round(si * 100, 2),
        "momentum_raw":              round(mom, 4),
        "gross_profit_margin":       round(gpm, 3),
        "roe":                       round(_safe_float(fund.get("roe"), 0.12), 3),
        "accruals_ratio":            round(_safe_float(fund.get("accruals_ratio"), 0.0), 3),
        "piotroski":                 int(_safe_float(fund.get("piotroski"), 5)),
        "pe_ttm":                    round(_safe_float(fund.get("pe_ttm"), 20.0), 1),
        "pb_ratio":                  round(_safe_float(fund.get("pb_ratio"), 2.0), 2),
        "beta":                      round(_safe_float(fund.get("beta"), 1.0), 2),
        "realized_vol_1y":           round(vol, 3),
        # Price / valuation fields agents reference
        "price":                     fund.get("current_price"),
        "change_pct":                fund.get("change_pct", 0.0),
        "market_cap":                fund.get("market_cap"),
        "sector":                    info.get("sector", ""),
        "week52_high":               fund.get("week52_high"),
        "week52_low":                fund.get("week52_low"),
        "analyst_target_mean":       fund.get("analyst_target"),
        # Adversarial / enrichment fields
        "debt_equity":               round(float(info.get("debtToEquity", 100.0)) / 100, 2) if info.get("debtToEquity") else None,
        "revenue_growth":            round(float(info.get("revenueGrowth", 0.0)) * 100, 1) if info.get("revenueGrowth") else None,
        "insider_cluster_score":      _compute_insider_score(info, fund) or 0.5,
    }

    # Sector median comparison (for agent context)
    sector = context.get("sector", "")
    if sector and sector != "Unknown":
        try:
            from nq_api.cache.score_cache import read_sector_median
            sector_medians = read_sector_median(sector, market)
            if sector_medians:
                # Prefix keys to avoid collision
                for k, v in sector_medians.items():
                    if v is not None:
                        context[f"sector_median_{k}"] = round(v, 3)
        except Exception as e:
            logger.debug("Non-critical enrichment failed: %s", e)
            pass  # Sector medians are best-effort enrichment

    # Post-hoc algorithmic guardrails — override LLM stances when data is unambiguous
    context["_fundamental_red_flags"] = _fundamental_red_flags(context)

    return context



def _merge_enrichment(context: dict, enrichment: dict) -> None:
    """Merge enrichment data into analyst context (mutates in-place)."""
    if not enrichment:
        return
    if enrichment.get("insider_cluster_score") is not None:
        context["insider_cluster_score"] = enrichment.pop("insider_cluster_score")
    if enrichment.get("insider_summary"):
        context["insider_summary"] = enrichment.pop("insider_summary")
    if enrichment.get("insider_net_buy_ratio") is not None:
        context["insider_net_buy_ratio"] = enrichment.pop("insider_net_buy_ratio")
    if enrichment.get("news_sentiment_label"):
        context["news_sentiment"] = enrichment.pop("news_sentiment_label")
        context["news_sentiment_score"] = enrichment.pop("news_sentiment_score")
        context["news_buzz"] = enrichment.pop("news_buzz")
    for k, v in enrichment.items():
        if k not in context:
            context[k] = v

def _compute_insider_score(info: dict, fund: dict) -> float | None:
    """Insider cluster score (0=bearish, 1=bullish).

    Tries yfinance info for insider transaction data. Falls back to neutral.
    This is the baseline — enrichment from EDGAR/Finnhub overrides it later.
    """
    if isinstance(info, dict):
        insider_pct = info.get("heldPercentInsiders")
        if insider_pct is not None:
            pct = float(insider_pct)
            if pct > 0.25:
                return round(min(pct, 1.0), 3)
            elif pct < 0.05:
                return round(max(pct, 0.0), 3)
    return None  # Let enrichment merge override; defaults to 0.5 if neither provides value


def _fetch_finnhub_data(ticker: str, market: str) -> dict:
    """Fetch technical indicators, insider sentiment, and news sentiment.

    Uses Finnhub API when available, automatically falls back to:
      - yfinance OHLCV for technical indicators (RSI/MACD/ATR/SMA)
      - SEC EDGAR Form 4 for insider sentiment
      - yfinance headlines + FinBERT/VADER for news sentiment

    Returns empty dict on failure (graceful fallback).
    """
    try:
        from nq_data.finnhub import get_finnhub_client
        client = get_finnhub_client()
    except Exception as exc:
        log.warning("Finnhub client init failed: %s", exc)
        return {}

    result: dict = {}

    # Technical indicators (RSI, MACD, ATR, SMA, volume)
    # Uses Finnhub candles → falls back to yfinance OHLCV automatically
    try:
        indicators = client.get_indicators(ticker)
        if indicators:
            result["rsi_14"] = indicators.get("rsi_14")
            result["macd_line"] = indicators.get("macd_line")
            result["macd_signal"] = indicators.get("macd_signal")
            result["macd_hist"] = indicators.get("macd_hist")
            result["atr_14"] = indicators.get("atr_14")
            result["sma_50"] = indicators.get("sma_50")
            result["sma_200"] = indicators.get("sma_200")
            result["price_vs_sma50"] = indicators.get("price_vs_sma50")
            result["price_vs_sma200"] = indicators.get("price_vs_sma200")
            result["volume_today"] = indicators.get("volume_today")
            result["volume_20d_avg"] = indicators.get("volume_20d_avg")
            result["volume_ratio"] = indicators.get("volume_ratio")
            result["finnhub_price"] = indicators.get("current_price")
    except Exception as exc:
        log.warning("Indicators failed for %s: %s", ticker, exc)

    # Insider sentiment
    # Uses Finnhub → falls back to SEC EDGAR Form 4 automatically
    try:
        insider = client.get_insider_sentiment(ticker)
        if insider:
            result["insider_cluster_score"] = insider.get("cluster_score")
            result["insider_net_buy_ratio"] = insider.get("net_buy_ratio")
            result["insider_summary"] = insider.get("summary")
    except Exception as exc:
        log.warning("Insider sentiment failed for %s: %s", ticker, exc)

    # News sentiment
    # Uses Finnhub → falls back to yfinance headlines + FinBERT/VADER automatically
    try:
        news_sent = client.get_news_sentiment(ticker)
        if news_sent:
            result["news_sentiment_label"] = news_sent.get("sentiment_label")
            result["news_sentiment_score"] = news_sent.get("sentiment_score")
            result["news_buzz"] = news_sent.get("buzz_score")
            result["news_bullish_pct"] = news_sent.get("bullish_pct")
            result["news_bearish_pct"] = news_sent.get("bearish_pct")
    except Exception as exc:
        log.warning("News sentiment failed for %s: %s", ticker, exc)

    if result:
        log.info("Enrichment for %s: %d fields", ticker, len(result))
    else:
        log.warning("Enrichment returned empty for %s", ticker)

    return result


def _fundamental_red_flags(ctx: dict) -> list[str]:
    """Detect BEAR signals in the data — severe ones trigger algorithmic override,
    moderate ones are passed to HEAD ANALYST as additional context."""
    flags = []
    roe = _safe_float(ctx.get("roe"), 0.12)
    pe = _safe_float(ctx.get("pe_ttm"), 20.0)
    gpm = _safe_float(ctx.get("gross_profit_margin"), 0.5)
    de = ctx.get("debt_equity")
    revenue_growth = ctx.get("revenue_growth")
    piotroski = int(_safe_float(ctx.get("piotroski"), 5))
    mcap = ctx.get("market_cap")

    # SEVERE red flags — trigger algorithmic override (unambiguous BEAR signals)
    if roe < 0:
        flags.append(f"SEVERE|NEGATIVE_ROE: ROE at {roe*100:.1f}% — company destroying shareholder value")
    if piotroski < 3:
        flags.append(f"SEVERE|WEAK_FSCORE: Piotroski {piotroski}/9 below 3 — poor financial health")
    if revenue_growth is not None and _safe_float(revenue_growth, 0) < -10:
        flags.append(f"SEVERE|SHRINKING_REVENUE: Revenue declining at {_safe_float(revenue_growth, 0):.1f}%")

    # MODERATE red flags — advisory, don't override but inform HEAD ANALYST
    if pe > 35:
        flags.append(f"MODERATE|EXTREME_P/E: P/E at {pe:.1f}x exceeds 35x threshold")
    if pe > 25 and roe < 0.10:
        flags.append(f"MODERATE|OVERVALUED_LOW_RETURN: P/E {pe:.1f}x with ROE only {roe*100:.1f}%")
    if gpm < 0.25:
        flags.append(f"MODERATE|WEAK_MARGIN: Gross margin at {gpm*100:.1f}% below 25%")
    # D/E >2.0 — skip for mega-caps where extreme D/E is usually a buyback artifact
    if de is not None and _safe_float(de, 0) > 2.0:
        mcap_val = _safe_float(mcap, 0)
        de_val = _safe_float(de, 0)
        if not (mcap_val > 50e9 and de_val > 20 and roe > 0.15):
            flags.append(f"MODERATE|HIGH_DEBT: Debt/Equity at {de_val:.1f} exceeds 2.0")

    return flags


def _build_context_from_cache(ticker: str, market: str) -> dict | None:
    """Fast path: build analyst context from Supabase score_cache (sub-100ms)."""
    try:
        cached = score_cache.read_one(ticker, market, max_age_seconds=900)
        if not cached:
            cached = score_cache.read_one(ticker, market, max_age_seconds=86400)
            if cached:
                log.info("analyst: serving stale cache (>%15min) for %s/%s", ticker, market)
        if not cached:
            cached = score_cache.read_one(ticker, market, max_age_seconds=999999999)
            if cached:
                log.warning("analyst: serving very old cache for %s/%s", ticker, market)
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return None
    if not cached:
        return None

    try:
        macro = _fetch_macro_with_timeout()
        macro_in = _fetch_macro_in_with_timeout() if market == "IN" else {}
        regime_id = cached.get("regime_id", 1)
        regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

        # Enrich cache data with yfinance info for fields agents reference
        from nq_api.data_builder import _fetch_one
        fund = _fetch_one(ticker, market)
        try:
            info = yf.Ticker(_yf_symbol(ticker, market)).info or {}
        except Exception as e:
            logger.debug("Non-critical enrichment failed: %s", e)
            info = {}

        context = {
            "market": market,
            "regime_label": regime_labels.get(regime_id, "Risk-On"),
            **macro,
            **macro_in,
            "composite_score":           round(_safe_float(cached.get("composite_score"), 0.5), 4),
            "quality_percentile":        round(_safe_float(cached.get("quality_percentile"), 0.5), 3),
            "momentum_percentile":       round(_safe_float(cached.get("momentum_percentile"), 0.5), 3),
            "value_percentile":          round(_safe_float(cached.get("value_percentile"), 0.5), 3),
            "low_vol_percentile":        round(_safe_float(cached.get("low_vol_percentile"), 0.5), 3),
            "low_short_interest_rank":   round(_safe_float(cached.get("short_interest_percentile"), 0.5), 3),
            "short_interest_pct":        round(_safe_float(cached.get("short_interest_pct"), 0.02) * 100, 2),
            "momentum_raw":              round(_safe_float(cached.get("momentum_raw"), 0.0), 4),
            "gross_profit_margin":       round(_safe_float(cached.get("gross_profit_margin")), 3) if cached.get("gross_profit_margin") is not None else None,
            "roe":                       round(_safe_float(fund.get("roe"), 0.12), 3),
            "accruals_ratio":            round(_safe_float(fund.get("accruals_ratio"), 0.0), 3),
            "piotroski":                 int(_safe_float(cached.get("piotroski"), 5)),
            "pe_ttm":                    round(_safe_float(cached.get("pe_ttm"), 20.0), 1),
            "pb_ratio":                  round(_safe_float(cached.get("pb_ratio"), 2.0), 2),
            "beta":                      round(_safe_float(cached.get("beta"), 1.0), 2),
            "realized_vol_1y":           round(_safe_float(cached.get("realized_vol_1y"), 0.20), 3),
            "price":                     fund.get("current_price"),
            "change_pct":                fund.get("change_pct", 0.0),
            "market_cap":                fund.get("market_cap"),
            "sector":                    info.get("sector", ""),
            "week52_high":               fund.get("week52_high"),
            "week52_low":                fund.get("week52_low"),
            "analyst_target_mean":       fund.get("analyst_target"),
            "debt_equity":               round(_safe_float(info.get("debtToEquity"), 100.0) / 100, 2) if info.get("debtToEquity") is not None else None,
            "revenue_growth":            round(_safe_float(info.get("revenueGrowth"), 0.0) * 100, 1) if info.get("revenueGrowth") is not None else None,
            "insider_cluster_score":      _compute_insider_score(info, fund) or 0.5,
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

        # Same algorithmic guardrails as _build_analyst_context
        context["_fundamental_red_flags"] = _fundamental_red_flags(context)
        return context
    except Exception as e:
        log.warning("cache context build failed for %s: %s", ticker, e)
        return None


@router.post("", response_model=AnalystResponse)
async def run_analyst(
    req: AnalystRequest,
    user: User | None = Depends(get_current_user_optional),
) -> AnalystResponse:
    ticker = req.ticker.upper()

    # Cache-first: try building context from score_cache (fast, avoids blocking event loop)
    context = await asyncio.to_thread(_build_context_from_cache, ticker, req.market)

    if context is None:
        # Slow path: fetch just the one ticker's data (2-5s, not 503 tickers)
        context = await asyncio.to_thread(_build_analyst_context, ticker, req.market)

    # Enrichment with timeout (yfinance/VADER/EDGAR)
    try:
        enrichment = await asyncio.wait_for(
            asyncio.to_thread(_fetch_finnhub_data, ticker, req.market),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        log.warning("Enrichment timed out for %s", ticker)
        enrichment = {}
    except Exception as exc:
        log.warning("Enrichment failed for %s: %s", ticker, exc)
        enrichment = {}
    if enrichment:
        _merge_enrichment(context, enrichment)

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=ticker, market=req.market, context=context)


@router.post("/stream")
async def run_analyst_stream(
    req: AnalystRequest,
    user: User | None = Depends(get_current_user_optional),
) -> StreamingResponse:
    """SSE variant of /analyst.

    Sends keep-alive pings every 8 s from the very first byte — including
    while context is being built — so Render's 30 s idle-connection timeout
    never fires.  The frontend reads the stream and renders the result when
    status=done.

    SSE event format:
      data: {"status":"running"}   — keep-alive tick (ignored by UI)
      data: {"status":"done","result":{...AnalystResponse...}}
      data: {"status":"error","message":"..."}
      data: [DONE]                 — stream closed
    """
    ticker = req.ticker.upper()
    market = req.market

    async def generate():
        # ── Phase 1: build context while streaming keep-alive pings ──
        # This prevents Render's proxy from dropping the connection during
        # the 10-30 s context-building phase (yfinance calls for 20+ tickers).
        context: dict | None = None
        context_error: str | None = None

        async def _build():
            nonlocal context, context_error
            try:
                ctx = await asyncio.to_thread(_build_context_from_cache, ticker, market)
                if ctx is None:
                    ctx = await asyncio.to_thread(_build_analyst_context, ticker, market)
                context = ctx
                # Enrichment with timeout
                try:
                    enrichment_data = await asyncio.wait_for(
                        asyncio.to_thread(_fetch_finnhub_data, ticker, market),
                        timeout=20.0,
                    )
                except (asyncio.TimeoutError, Exception):
                    enrichment_data = {}
                else:
                    if enrichment_data:
                        _merge_enrichment(ctx, enrichment_data)
            except Exception as exc:
                log.exception("PARA-DEBATE context build failed for %s", ticker)
                context_error = str(exc)

        build_task = asyncio.create_task(_build())
        phase1_start = time.monotonic()
        PHASE1_TIMEOUT, PHASE2_TIMEOUT = _phase_timeouts()

        while not build_task.done():
            yield 'data: {"status":"running"}\n\n'
            elapsed = time.monotonic() - phase1_start
            if elapsed > PHASE1_TIMEOUT:
                build_task.cancel()
                context_error = f"Context build timed out after {PHASE1_TIMEOUT}s"
                break
            try:
                await asyncio.wait_for(asyncio.shield(build_task), timeout=8.0)
            except asyncio.TimeoutError:
                pass

        if context_error:
            yield f'data: {json.dumps({"status": "error", "message": context_error})}\n\n'
            yield "data: [DONE]\n\n"
            return

        if context is None:
            yield f'data: {json.dumps({"status": "error", "message": "Failed to build context"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # ── Phase 2: run 7-agent debate while streaming keep-alive pings ──
        result_holder: dict = {}
        done_event = asyncio.Event()

        async def _run_debate() -> None:
            try:
                orch = ParaDebateOrchestrator()
                result_holder["result"] = await asyncio.wait_for(
                    orch.analyse(ticker=ticker, market=market, context=context),
                    timeout=PHASE2_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.warning("PARA-DEBATE timed out after %ds for %s", PHASE2_TIMEOUT, ticker)
                result_holder["timeout"] = True
            except Exception as exc:
                log.exception("PARA-DEBATE stream failed for %s", ticker)
                result_holder["error"] = str(exc)
            finally:
                done_event.set()

        asyncio.create_task(_run_debate())
        phase2_start = time.monotonic()

        while not done_event.is_set():
            yield 'data: {"status":"running"}\n\n'
            # Hard cap: if Phase 2 exceeds PHASE2_TIMEOUT + 30s buffer, give up
            elapsed = time.monotonic() - phase2_start
            if elapsed > PHASE2_TIMEOUT + 30:
                done_event.set()
                result_holder.setdefault("timeout", True)
                break
            try:
                await asyncio.wait_for(asyncio.shield(done_event.wait()), timeout=8.0)
            except asyncio.TimeoutError:
                pass

        if result_holder.get("timeout"):
            # Return a partial/fallback result so the UI shows something useful
            partial = AnalystResponse(
                ticker=ticker,
                head_analyst_verdict="TIMEOUT",
                investment_thesis=f"PARA-DEBATE timed out after {PHASE2_TIMEOUT}s. "
                                 "Market context was built but the multi-agent debate "
                                 "could not complete in time. Try again or use AI Score for a quick read.",
                bull_case="Analysis incomplete — review AI Score pillars instead.",
                bear_case="Debate did not finish — risk factors may be understated.",
                risk_factors=["Partial analysis — treat with caution."],
                agent_outputs=[],
                consensus_score=float(context.get("composite_score", 0.5)),
            )
            yield f'data: {json.dumps({"status": "done", "result": partial.model_dump()})}\n\n'
        elif "error" in result_holder:
            yield f'data: {json.dumps({"status": "error", "message": result_holder["error"]})}\n\n'
        else:
            resp: AnalystResponse = result_holder.get("result")
            if resp:
                yield f'data: {json.dumps({"status": "done", "result": resp.model_dump()})}\n\n'
            else:
                yield f'data: {json.dumps({"status": "error", "message": "No result produced"})}\n\n'
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


@router.get("/envcheck")
async def envcheck():
    """Runtime check: confirms model availability and config at request time."""
    from nq_api.agents.base import FAST_MODEL, MODEL, _is_ollama as _base_is_ollama, _resolve_model, _validated_models
    from nq_api.agents.orchestrator import _is_ollama as _orch_is_ollama
    resolved_fast = _resolve_model(FAST_MODEL, MODEL)
    return {
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "NOT SET"),
        "NQ_FAST_MODEL": os.environ.get("NQ_FAST_MODEL", "NOT SET"),
        "FAST_MODEL_CONFIG": FAST_MODEL,
        "FAST_MODEL_RESOLVED": resolved_fast,
        "MODEL": MODEL,
        "BASE_IS_OLLAMA": _base_is_ollama(),
        "ORCH_IS_OLLAMA": _orch_is_ollama(),
        "MODEL_VALIDATIONS": dict(_validated_models),
    }
