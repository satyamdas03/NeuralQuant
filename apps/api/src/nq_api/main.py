# apps/api/src/nq_api/main.py
from pathlib import Path
from dotenv import load_dotenv
# Load .env from apps/api/ regardless of CWD
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path, override=True)

import logging
import threading
import time
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nq_api.config import CORS_ORIGINS, CORS_ORIGIN_REGEX, FRONTEND_URL
from nq_api.routes import stocks, screener, analyst, query, market, auth, watchlists, sentiment, backtest, alerts, newsdesk, team, broker
from nq_api.routes.auth_webhook import router as auth_webhook_router
from nq_api.routes.market_wrap import router as market_wrap_router
from nq_api.slack.router import router as slack_router
from nq_api.routes.checkout import router as checkout_router
from nq_api.routes.webhooks_stripe import router as stripe_webhook_router
from nq_api.routes.referrals import router as referral_router


def _run_pending_migrations():
    """Apply pending SQL migrations via Supabase REST (no direct DB needed)."""
    import asyncio
    try:
        from nq_api.db_migrate import run_pending
        asyncio.run(run_pending())
    except Exception as exc:
        log.warning("Migration runner failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    # On Render, skip heavy prewarm — caches populate lazily on first request.
    # Prewarm threads with yfinance + asyncio.run() cause OOM/crash on cold starts.
    on_render = bool(os.environ.get("RENDER"))

    # Run pending DB migrations before warming caches
    _run_pending_migrations()

    # Lightweight prewarm: fetch macro data (2 yfinance calls) even on Render
    # so first analyst request isn't slow. Full universe prewarm is still skipped.
    def _warm_macro():
        try:
            from nq_api.data_builder import fetch_real_macro
            fetch_real_macro()
            log.info("Macro prewarm complete")
        except Exception as exc:
            log.warning("Macro prewarm failed: %s", exc)

    threading.Thread(target=_warm_macro, daemon=True).start()

    if not on_render:
        def _warm():
            try:
                from nq_api.data_builder import prewarm_cache
                from nq_api.universe import US_DEFAULT
                prewarm_cache(US_DEFAULT, "US")
            except Exception as exc:
                log.warning("Cache prewarm failed: %s", exc)

        def _warm_news():
            try:
                from nq_api.routes.newsdesk import _fetch_yf_news, _sentiment_score, _sentiment_label, _category, _extract_tickers, _relative_time, _compute_trending
                import nq_api.routes.newsdesk as _nd
                sources = ["^GSPC", "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
                all_items = []
                for sym in sources:
                    try:
                        all_items.extend(_fetch_yf_news(sym, 8))
                    except Exception:
                        pass
                if all_items and _nd._news_cache is None:
                    enriched = []
                    for item in all_items[:20]:
                        title = item.get("title", "")
                        if not title:
                            continue
                        score = _sentiment_score(title)
                        enriched.append({
                            "title": title,
                            "publisher": item.get("publisher", ""),
                            "url": item.get("url", ""),
                            "time": _relative_time(item.get("time")),
                            "category": _category(title),
                            "tickers": _extract_tickers(title),
                            "sentiment": _sentiment_label(score),
                        })
                    if enriched:
                        avg = sum(_sentiment_score(h["title"]) for h in enriched) / len(enriched)
                        _nd._news_cache = {
                            "sentiment": "bullish" if avg >= 0.25 else "bearish" if avg <= -0.25 else "neutral",
                            "headlines": enriched[:20],
                            "trending": _compute_trending(enriched),
                        }
                        _nd._news_ts = time.time()
                        log.info("News prewarm: %d headlines cached", len(enriched))
            except Exception as exc:
                log.warning("News prewarm failed: %s", exc)

        threading.Thread(target=_warm, daemon=True).start()
        threading.Timer(20.0, _warm_news).start()

        # Background: refresh score_cache if empty or stale (for dashboard + screener)
        def _refresh_score_cache():
            try:
                from nq_api.cache.score_cache import read_top, upsert_scores, age_seconds
                age = age_seconds("US")
                if age is not None and age < 86400:
                    log.info("score_cache fresh (%d min old), skipping refresh", age // 60)
                    return
                log.info("score_cache stale or empty (age=%s), refreshing...", age)
                from nq_api.data_builder import build_real_snapshot
                from nq_api.universe import UNIVERSE_BY_MARKET
                from nq_api.deps import get_signal_engine
                from nq_api.score_builder import row_to_ai_score
                import pandas as pd
                for mkt in ("US", "IN"):
                    tickers = UNIVERSE_BY_MARKET.get(mkt, UNIVERSE_BY_MARKET["US"])
                    snapshot = build_real_snapshot(tickers, mkt)
                    if snapshot is None or snapshot.fundamentals.empty:
                        continue
                    engine = get_signal_engine()
                    result_df = engine.compute(snapshot)
                    if result_df is None or result_df.empty:
                        continue
                    rows = []
                    for _, row in result_df.iterrows():
                        rows.append({
                            "ticker": row.get("ticker", ""),
                            "market": mkt,
                            "sector": row.get("sector", ""),
                            "composite_score": float(row.get("composite_score", 0)),
                            "rank_score": int(row.get("rank_score", 0)),
                            "value_percentile": float(row.get("value_percentile", 0.5)),
                            "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
                            "quality_percentile": float(row.get("quality_percentile", 0.5)),
                            "low_vol_percentile": float(row.get("low_vol_percentile", 0.5)),
                            "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
                            "pe_ttm": float(row.get("pe_ttm", 0)) if pd.notna(row.get("pe_ttm")) else 0,
                            "market_cap": float(row.get("market_cap", 0)) if pd.notna(row.get("market_cap")) else 0,
                            "current_price": float(row.get("current_price", 0)) if pd.notna(row.get("current_price")) else 0,
                            "analyst_target": float(row.get("analyst_target", 0)) if pd.notna(row.get("analyst_target")) else 0,
                            "momentum_raw": float(row.get("momentum_raw", 0)) if pd.notna(row.get("momentum_raw")) else 0,
                            "gross_profit_margin": float(row.get("gross_profit_margin", 0)) if pd.notna(row.get("gross_profit_margin")) else 0,
                            "piotroski": float(row.get("piotroski", 0)) if pd.notna(row.get("piotroski")) else 0,
                            "pb_ratio": float(row.get("pb_ratio", 0)) if pd.notna(row.get("pb_ratio")) else 0,
                            "beta": float(row.get("beta", 0)) if pd.notna(row.get("beta")) else 0,
                            "realized_vol_1y": float(row.get("realized_vol_1y", 0)) if pd.notna(row.get("realized_vol_1y")) else 0,
                            "short_interest_pct": float(row.get("short_interest_pct", 0)) if pd.notna(row.get("short_interest_pct")) else 0,
                            "insider_cluster_score": float(row.get("insider_cluster_score", 0)) if pd.notna(row.get("insider_cluster_score")) else 0,
                            "accruals_ratio": float(row.get("accruals_ratio", 0)) if pd.notna(row.get("accruals_ratio")) else 0,
                            "revenue_growth_yoy": float(row.get("revenue_growth_yoy", 0)) if pd.notna(row.get("revenue_growth_yoy")) else 0,
                            "debt_equity": float(row.get("debt_equity", 0)) if pd.notna(row.get("debt_equity")) else 0,
                        })
                    count = upsert_scores(rows)
                    log.info("score_cache refreshed for %s: %d rows upserted", mkt, count)
            except Exception as exc:
                log.warning("score_cache refresh failed: %s", exc)

        threading.Timer(30.0, _refresh_score_cache).start()
    else:
        # On Render: background cache refresh with small subset (avoid OOM/timeout)
        def _render_cache_refresh():
            try:
                from nq_api.cache.score_cache import read_top, upsert_scores, age_seconds
                age_us = age_seconds("US")
                age_in = age_seconds("IN")
                # Skip refresh if BOTH markets are fresh (< 1 hour)
                us_fresh = age_us is not None and age_us < 3600
                in_fresh = age_in is not None and age_in < 3600
                if us_fresh and in_fresh:
                    log.info("Render: score_cache fresh (US %d min, IN %d min), skipping",
                             age_us // 60 if age_us else 0, age_in // 60 if age_in else 0)
                    return
                log.info("Render: score_cache stale (US age=%s, IN age=%s), refreshing top-50...", age_us, age_in)
                from nq_api.data_builder import build_real_snapshot
                from nq_api.universe import UNIVERSE_BY_MARKET
                from nq_api.deps import get_signal_engine
                import pandas as pd
                for mkt in ("US", "IN"):
                    # Skip markets that are already fresh
                    mkt_age = age_us if mkt == "US" else age_in
                    if mkt_age is not None and mkt_age < 3600:
                        log.info("Render: %s score_cache fresh (%d min), skipping", mkt, mkt_age // 60)
                        continue
                    all_tickers = UNIVERSE_BY_MARKET.get(mkt, UNIVERSE_BY_MARKET["US"])
                    # Take top 50 to cover popular tickers (was 20 — missed mid-cap India)
                    tickers = all_tickers[:50]
                    try:
                        snapshot = build_real_snapshot(tickers, mkt)
                    except Exception as e:
                        log.warning("Render: build_real_snapshot failed for %s: %s", mkt, e)
                        continue
                    if snapshot is None or snapshot.fundamentals.empty:
                        continue
                    engine = get_signal_engine()
                    result_df = engine.compute(snapshot)
                    if result_df is None or result_df.empty:
                        continue
                    rows = []
                    for _, row in result_df.iterrows():
                        rows.append({
                            "ticker": row.get("ticker", ""),
                            "market": mkt,
                            "sector": row.get("sector", ""),
                            "composite_score": float(row.get("composite_score", 0)),
                            "rank_score": int(row.get("rank_score", 0)),
                            "value_percentile": float(row.get("value_percentile", 0.5)),
                            "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
                            "quality_percentile": float(row.get("quality_percentile", 0.5)),
                            "low_vol_percentile": float(row.get("low_vol_percentile", 0.5)),
                            "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
                            "pe_ttm": float(row.get("pe_ttm", 0)) if pd.notna(row.get("pe_ttm")) else 0,
                            "market_cap": float(row.get("market_cap", 0)) if pd.notna(row.get("market_cap")) else 0,
                            "current_price": float(row.get("current_price", 0)) if pd.notna(row.get("current_price")) else 0,
                            "analyst_target": float(row.get("analyst_target", 0)) if pd.notna(row.get("analyst_target")) else 0,
                            "momentum_raw": float(row.get("momentum_raw", 0)) if pd.notna(row.get("momentum_raw")) else 0,
                            "gross_profit_margin": float(row.get("gross_profit_margin", 0)) if pd.notna(row.get("gross_profit_margin")) else 0,
                            "piotroski": float(row.get("piotroski", 0)) if pd.notna(row.get("piotroski")) else 0,
                            "pb_ratio": float(row.get("pb_ratio", 0)) if pd.notna(row.get("pb_ratio")) else 0,
                            "beta": float(row.get("beta", 0)) if pd.notna(row.get("beta")) else 0,
                            "realized_vol_1y": float(row.get("realized_vol_1y", 0)) if pd.notna(row.get("realized_vol_1y")) else 0,
                            "short_interest_pct": float(row.get("short_interest_pct", 0)) if pd.notna(row.get("short_interest_pct")) else 0,
                            "insider_cluster_score": float(row.get("insider_cluster_score", 0)) if pd.notna(row.get("insider_cluster_score")) else 0,
                            "accruals_ratio": float(row.get("accruals_ratio", 0)) if pd.notna(row.get("accruals_ratio")) else 0,
                            "revenue_growth_yoy": float(row.get("revenue_growth_yoy", 0)) if pd.notna(row.get("revenue_growth_yoy")) else 0,
                            "debt_equity": float(row.get("debt_equity", 0)) if pd.notna(row.get("debt_equity")) else 0,
                        })
                    count = upsert_scores(rows)
                    log.info("Render: score_cache refreshed for %s: %d rows", mkt, count)
            except Exception as exc:
                log.warning("Render: score_cache refresh failed: %s", exc)

        threading.Timer(30.0, _render_cache_refresh).start()
        log.info("Render detected — score_cache refresh scheduled (top-50 per market)")

    # Pre-warm enrichment cache for top tickers (RSI/MACD/ATR/insider/news)
    # Runs after 45s delay to avoid conflicting with score_cache refresh
    _TOP_ENRICHMENT_TICKERS_US = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
        "UNH", "JNJ", "WMT", "XOM", "PG", "MA", "HD", "CVX", "MRK", "AVGO",
        "ABBV", "KO", "PEP", "COST", "CSCO", "ADBE", "NFLX", "CRM", "AMD", "INTC",
        "CMCSA", "NKE", "DIS", "PYPL", "VZ", "T", "PFE", "ABT", "TMO",
        "ORCL", "QCOM", "TXN", "LLY", "BMY", "UPS", "COP", "LOW", "IBM",
    ]
    _TOP_ENRICHMENT_TICKERS_IN = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
        "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
        "ASIANPAINT", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE",
        "TITAN", "NESTLEIND", "POWERGRID",
    ]

    def _warm_enrichment():
        """Pre-fetch RSI/MACD/ATR/insider/news for top tickers. Cache in Supabase (1h TTL)."""
        try:
            from nq_api.cache.score_cache import read_enrichment, write_enrichment
            from nq_api.routes.analyst import _fetch_finnhub_data
            warmed = 0
            total = len(_TOP_ENRICHMENT_TICKERS_US) + len(_TOP_ENRICHMENT_TICKERS_IN)
            for ticker in _TOP_ENRICHMENT_TICKERS_US:
                # Skip if already cached
                if read_enrichment(ticker, "US"):
                    warmed += 1
                    continue
                try:
                    data = _fetch_finnhub_data(ticker, "US")
                    if data:
                        write_enrichment(ticker, "US", data)
                        warmed += 1
                except Exception as exc:
                    log.debug("Enrichment prewarm failed for %s: %s", ticker, exc)
            # India tickers — Finnhub free tier has limited IN coverage, skip gracefully
            for ticker in _TOP_ENRICHMENT_TICKERS_IN:
                if read_enrichment(ticker, "IN"):
                    warmed += 1
                    continue
                try:
                    data = _fetch_finnhub_data(ticker, "IN")
                    if data:
                        write_enrichment(ticker, "IN", data)
                        warmed += 1
                except Exception as exc:
                    log.debug("Enrichment prewarm IN failed for %s: %s", ticker, exc)
            log.info("Enrichment prewarm complete: %d/%d tickers cached", warmed, total)
        except Exception as exc:
            log.warning("Enrichment prewarm failed: %s", exc)

    threading.Timer(45.0, lambda: threading.Thread(target=_warm_enrichment, daemon=True).start()).start()

    # Start Slack agent system (graceful: no crash if tokens missing)
    from nq_api.slack.app import start_slack_handler, stop_slack_handler
    from nq_api.slack.scheduler import start_scheduler, stop_scheduler
    try:
        await start_slack_handler()
        await start_scheduler()
    except Exception as exc:
        log.warning("Slack agent system startup failed (non-fatal): %s", exc)

    yield

    # Shutdown Slack handler and scheduler
    try:
        await stop_scheduler()
        await stop_slack_handler()
    except Exception as exc:
        log.warning("Slack agent system shutdown error (non-fatal): %s", exc)


app = FastAPI(title="NeuralQuant API", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(stocks.router,   prefix="/stocks",   tags=["stocks"])
app.include_router(screener.router, prefix="/screener", tags=["screener"])
app.include_router(analyst.router,  prefix="/analyst",  tags=["analyst"])
app.include_router(query.router,    prefix="/query",     tags=["query"])
app.include_router(market.router,   prefix="/market",   tags=["market"])
app.include_router(auth.router)         # /auth/me
app.include_router(watchlists.router)   # /watchlist
app.include_router(sentiment.router, prefix="/sentiment", tags=["sentiment"])
app.include_router(backtest.router,  prefix="/backtest",  tags=["backtest"])
app.include_router(alerts.router)
app.include_router(newsdesk.router)
app.include_router(checkout_router)
app.include_router(stripe_webhook_router)
app.include_router(referral_router)
app.include_router(slack_router)
app.include_router(team.router)
app.include_router(broker.router)
app.include_router(auth_webhook_router)
app.include_router(market_wrap_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
