# apps/api/src/nq_api/main.py
import asyncio
from pathlib import Path
from dotenv import load_dotenv
# Load .env from apps/api/ regardless of CWD
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path, override=True)

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)

# Redact secrets/PII (apikey=, Bearer, emails) from all logs ASAP, and silence
# httpx URL logging that printed apikey= query strings.
from nq_api.logging_redaction import install_log_redaction
install_log_redaction()

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from nq_api.config import CORS_ORIGINS, CORS_ORIGIN_REGEX, FRONTEND_URL
from nq_api.routes import stocks, screener, analyst, query, market, auth, watchlists, sentiment, backtest, alerts, newsdesk, team, broker, trade, live, live_dashboard
from nq_api.routes.terminal import router as terminal_router
from nq_api.routes.auth_webhook import router as auth_webhook_router
from nq_api.routes.market_wrap import router as market_wrap_router
from nq_api.routes.livekit_token import router as livekit_token_router
from nq_api.slack.router import router as slack_router
from nq_api.routes.checkout import router as checkout_router
from nq_api.routes.checkout_stripe import router as checkout_stripe_router
from nq_api.routes.webhooks_paypal import router as paypal_webhook_router
from nq_api.routes.webhooks_stripe import router as stripe_webhook_router
from nq_api.routes.referrals import router as referral_router
from nq_api.routes.session import router as session_router
from nq_api.routes.cron import router as cron_router
from nq_api.routes.share import router as share_router
from nq_api.routes.analytics import router as analytics_router
from nq_api.routes.analytics_track import router as analytics_track_router
from nq_api.routes.astra_portfolio import router as astra_portfolio_router
from nq_api.routes.mobile import router as mobile_router
from nq_api.routes.testing import router as testing_router


async def _run_pending_migrations():
    """Apply pending SQL migrations via Supabase REST (no direct DB needed)."""
    try:
        from nq_api.db_migrate import run_pending
        await run_pending()
    except Exception as exc:
        log.warning("Migration runner failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    # Re-apply log redaction after uvicorn has installed its handlers.
    install_log_redaction()
    # On Render, skip heavy prewarm — caches populate lazily on first request.
    # Prewarm threads with yfinance + asyncio.run() cause OOM/crash on cold starts.
    on_render = bool(os.environ.get("RENDER"))

    # Run pending DB migrations before warming caches
    await _run_pending_migrations()

    # ── Warm Anthropic connection on startup ────────────────────────────────
    # The first Anthropic API call incurs TCP+TLS handshake overhead (2-5s).
    # By sending a tiny warmup request on startup, we eliminate this latency
    # from the first user query. Non-blocking: runs in a daemon thread.
    def _warm_anthropic():
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key and not os.environ.get("USE_BEDROCK", "").lower() == "true":
                from nq_api.services.anthropic_helpers import _query_client
                client, model = _query_client(api_key)
                # The _query_client already fires a warmup ping in a daemon thread
                log.info("Anthropic client prewarm initiated (model=%s)", model)
            else:
                log.info("Anthropic prewarm skipped (no API key or using Bedrock)")
        except Exception as exc:
            log.warning("Anthropic prewarm failed (non-fatal): %s", exc)

    threading.Thread(target=_warm_anthropic, daemon=True, name="anthropic-startup-warmup").start()

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
        # On Render: use quantfactor fast path (no yfinance).
        # Always rebuild on cold start — a fresh cache from a previous deploy
        # may contain buggy data that the new code would fix. The quantfactor
        # path takes ~30s and runs in a delayed thread so it won't block requests.
        def _render_cache_refresh():
            try:
                from nq_api.cache.score_cache import age_seconds
                from nq_api.jobs.nightly_score import run_market
                age_us = age_seconds("US")
                age_in = age_seconds("IN")
                log.info("Render: cold-start score_cache rebuild (US age=%s, IN age=%s)",
                         f"{age_us // 60}min" if age_us else "none",
                         f"{age_in // 60}min" if age_in else "none")
                for mkt in ("US", "IN"):
                    count = run_market(mkt)
                    log.info("Render: score_cache rebuilt for %s: %d rows", mkt, count)
            except Exception as exc:
                log.warning("Render: score_cache refresh failed: %s", exc)

        threading.Timer(30.0, _render_cache_refresh).start()
        log.info("Render detected — score_cache cold-start rebuild scheduled (top-50 per market)")

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

    # Pre-warm quantfactor cache (Supabase REST call, ~500ms, avoids cold-start latency)
    def _warm_quantfactor():
        try:
            from nq_api.cache.quantfactor_cache import get_quantfactor_scores
            # Load both US and IN markets by querying a known ticker from each
            get_quantfactor_scores("AAPL", "US")
            get_quantfactor_scores("RELIANCE", "IN")
            log.info("QuantFactor cache prewarm complete")
        except Exception as exc:
            log.warning("QuantFactor cache prewarm failed (non-fatal): %s", exc)

    threading.Thread(target=_warm_quantfactor, daemon=True, name="quantfactor-warmup").start()

    # Pre-warm stock_meta for top tickers so first request after cold start is fast
    _TOP_META_TICKERS_US = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "XOM",
        "JNJ", "WMT", "PG", "MA", "HD", "CVX", "MRK", "AVGO", "ABBV", "KO",
        "PEP", "COST", "CSCO", "ADBE", "NFLX", "CRM", "AMD", "INTC", "NKE", "DIS",
    ]
    _TOP_META_TICKERS_IN = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
        "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
        "ASIANPAINT", "MARUTI", "SUNPHARMA", "BAJFINANCE", "TITAN",
    ]

    def _warm_stock_meta():
        """Pre-fetch stock meta for top tickers — warms yfinance sessions internally."""
        try:
            from nq_api.routes.stocks import _fetch_stock_meta
            warmed = 0
            total = len(_TOP_META_TICKERS_US) + len(_TOP_META_TICKERS_IN)
            for ticker in _TOP_META_TICKERS_US:
                try:
                    data = _fetch_stock_meta(ticker, "US")
                    if isinstance(data, dict):
                        warmed += 1
                except Exception as exc:
                    log.debug("Meta prewarm failed for %s: %s", ticker, exc)
            for ticker in _TOP_META_TICKERS_IN:
                try:
                    data = _fetch_stock_meta(ticker, "IN")
                    if isinstance(data, dict):
                        warmed += 1
                except Exception as exc:
                    log.debug("Meta prewarm IN failed for %s: %s", ticker, exc)
            log.info("Stock meta prewarm complete: %d/%d tickers warmed", warmed, total)
        except Exception as exc:
            log.warning("Stock meta prewarm failed: %s", exc)

    threading.Timer(60.0, lambda: threading.Thread(target=_warm_stock_meta, daemon=True).start()).start()

    # Start Slack agent system (graceful: no crash if tokens missing)
    from nq_api.slack.app import start_slack_handler, stop_slack_handler
    from nq_api.slack.scheduler import start_scheduler, stop_scheduler
    try:
        await start_slack_handler()
        await start_scheduler()
    except Exception as exc:
        log.warning("Slack agent system startup failed (non-fatal): %s", exc)

    # Start OpenBB keep-warm background task (prevents Render cold starts)
    from nq_api.routes.terminal import _keep_warm
    asyncio.create_task(_keep_warm(), name="openbb_keep_warm")

    # Start in-process cron scheduler (replaces GHA nightly workflows)
    from nq_api.routes.cron import start_scheduled_jobs
    await start_scheduled_jobs()

    # Safety: warn if live trading is enabled
    if os.environ.get("TRADE_ENABLED", "false").lower() == "true":
        dry = os.environ.get("DRY_RUN", "true").lower()
        paper = os.environ.get("ALPACA_PAPER", "true").lower()
        if dry == "false" and paper == "false":
            log.warning("LIVE TRADING ENABLED — real-money orders will execute. DRY_RUN=false, ALPACA_PAPER=false")
        elif dry == "false":
            log.info("Paper trading enabled (DRY_RUN=false, ALPACA_PAPER=true)")
        else:
            log.info("Trade pipeline enabled but DRY_RUN=true — orders simulated")

    yield

    # Shutdown Slack handler and scheduler
    try:
        await stop_scheduler()
        await stop_slack_handler()
    except Exception as exc:
        log.warning("Slack agent system shutdown error (non-fatal): %s", exc)


# Swagger/OpenAPI docs leak the full API surface (every route, params, auth
# scheme). Keep them OFF in prod; opt in locally with ENABLE_DOCS=true.
_docs_enabled = os.environ.get("ENABLE_DOCS", "").lower() == "true"
app = FastAPI(
    title="NeuralQuant API",
    version="4.0.2",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Log validation errors for debugging
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    log.warning("[422] Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)

# ── Global NaN/Inf JSON sanitizer (bug 110 class) ────────────────────────────
# Last line of defense: no route can 500 on non-finite floats in a JSON body.
import json as _json
import math as _math
from starlette.middleware.base import BaseHTTPMiddleware


def _clean_nonfinite(obj):
    if isinstance(obj, float):
        return None if (_math.isnan(obj) or _math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _clean_nonfinite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nonfinite(v) for v in obj]
    return obj


class NaNSanitizerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        ctype = resp.headers.get("content-type", "")
        if not ctype.startswith("application/json"):
            return resp
        body = b""
        async for chunk in resp.body_iterator:
            body += chunk
        # Preserve the original headers (CORS, cache, cookies) — rebuilding the
        # response without them strips Access-Control-Allow-Origin and the
        # browser then blocks every JSON call. Content-length/type are re-set.
        passthrough = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in ("content-length", "content-type")
        }
        try:
            cleaned = _json.dumps(_clean_nonfinite(_json.loads(body)))
            from starlette.responses import Response as _Resp
            return _Resp(cleaned, status_code=resp.status_code,
                         headers=passthrough, media_type="application/json")
        except Exception:
            from starlette.responses import Response as _Resp
            return _Resp(body, status_code=resp.status_code,
                         headers=passthrough, media_type=ctype)


app.add_middleware(NaNSanitizerMiddleware)

# ── Visitor tracking (IP-based unique visitors per day) ─────────────────────
import hashlib
from starlette.requests import Request
from starlette.responses import Response

_visitor_store: dict[str, set[str]] = {}  # date_str -> set of ip_hashes


@app.middleware("http")
async def track_visitors(request: Request, call_next):
    response: Response = await call_next(request)
    # Skip health checks, static assets, webhooks
    path = request.url.path
    if path.startswith(("/docs", "/openapi", "/redoc", "/auth/webhook", "/webhooks")):
        return response
    try:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        today = time.strftime("%Y-%m-%d")
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        if today not in _visitor_store:
            _visitor_store[today] = set()
        _visitor_store[today].add(ip_hash)
        # Prune old dates (keep last 7)
        if len(_visitor_store) > 7:
            oldest = sorted(_visitor_store.keys())[:-7]
            for d in oldest:
                del _visitor_store[d]
    except Exception:
        pass
    return response


# ── Security headers on the API origin ───────────────────────────────────────
# The Vercel web origin sets these, but the API is directly reachable too.
# Registered last so it is the OUTERMOST middleware — headers survive the
# NaN sanitizer rebuild and apply to every response.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
    )
    return response


@app.get("/stats/visitors")
def visitor_stats():
    """Return unique visitor counts per day."""
    return {date: len(ips) for date, ips in sorted(_visitor_store.items())}

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
app.include_router(checkout_stripe_router)
app.include_router(paypal_webhook_router)
app.include_router(stripe_webhook_router)
app.include_router(referral_router)
app.include_router(slack_router)
app.include_router(team.router)
app.include_router(trade.router,   prefix="/trade",    tags=["trade"])
app.include_router(live.router)
app.include_router(live_dashboard.router)
app.include_router(broker.router)
app.include_router(auth_webhook_router)
app.include_router(market_wrap_router)
app.include_router(terminal_router, prefix="/terminal", tags=["terminal"])
app.include_router(livekit_token_router)
app.include_router(session_router)
app.include_router(cron_router)
app.include_router(share_router)
app.include_router(analytics_router)
app.include_router(analytics_track_router)
app.include_router(astra_portfolio_router)
app.include_router(mobile_router)
app.include_router(testing_router)

from nq_api.routes.hermes import router as hermes_router  # noqa: E402
app.include_router(hermes_router)


@app.get("/health")
def health():
    """Liveness + data-freshness in one call (bug class: stale cache invisible)."""
    age_hours = None
    rows = None
    try:
        from nq_api.cache.score_cache import _supabase_rest
        data = _supabase_rest(
            "score_cache", "GET",
            {"select": "computed_at", "order": "computed_at.desc", "limit": "1"},
        )
        if isinstance(data, list) and data and data[0].get("computed_at"):
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(data[0]["computed_at"].replace("Z", "+00:00"))
            age_hours = round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 1)
        # Row count via PostgREST Content-Range header (helper doesn't expose it)
        import httpx
        sb_url = os.environ.get("SUPABASE_URL", "")
        sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if sb_url and sb_key:
            r = httpx.head(
                f"{sb_url}/rest/v1/score_cache?select=ticker",
                headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                         "Prefer": "count=exact", "Range": "0-0"},
                timeout=3.0,
            )
            cr = r.headers.get("content-range", "")
            if "/" in cr and cr.split("/")[-1].isdigit():
                rows = int(cr.split("/")[-1])
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "4.1.0",
        "score_cache_age_hours": age_hours,
        "score_cache_rows": rows,
        "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
    }


@app.get("/health/smoke")
async def health_smoke(x_cron_secret: str | None = Header(default=None)):
    """Deep health check — tests all critical dependencies in parallel.
    Protected by CRON_SECRET header (same as /cron/* endpoints)."""
    import os, time
    from datetime import datetime, timezone

    _secret = os.environ.get("CRON_SECRET", "")
    if _secret and x_cron_secret != _secret:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="invalid CRON_SECRET")

    checks: dict[str, dict] = {}
    failures: list[str] = []

    async def _check(name: str, coro):
        t0 = time.monotonic()
        try:
            result = await coro
            elapsed = int((time.monotonic() - t0) * 1000)
            result["latency_ms"] = elapsed
            checks[name] = result
            if not result.get("ok"):
                failures.append(f"{name}: {result.get('error', 'unknown')}")
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            checks[name] = {"ok": False, "latency_ms": elapsed, "error": str(exc)}
            failures.append(f"{name}: {exc}")

    # ── Individual check coroutines ─────────────────────────────────────

    async def _check_supabase():
        from nq_api.cache.score_cache import _supabase_rest
        data = await asyncio.to_thread(
            _supabase_rest, "score_cache", "GET",
            {"select": "computed_at", "order": "computed_at.desc", "limit": "1"},
        )
        if isinstance(data, list) and data:
            return {"ok": True, "last_computed": data[0].get("computed_at")}
        return {"ok": False, "error": "no score_cache rows"}

    async def _check_fmp():
        def _fmp_quote():
            from nq_data.fmp import get_fmp_client
            fmp = get_fmp_client()
            return fmp.get_quote("AAPL")
        result = await asyncio.wait_for(asyncio.to_thread(_fmp_quote), timeout=8.0)
        if result and (isinstance(result, dict) and result.get("price")):
            return {"ok": True, "aapl_price": result.get("price")}
        return {"ok": False, "error": "no price in FMP quote"}

    async def _check_anthropic():
        def _anthropic_ping():
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return {"ok": False, "error": "ANTHROPIC_API_KEY not set"}
            client = anthropic.Anthropic(api_key=api_key, timeout=10.0)
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
            return {"ok": True, "model": resp.model}
        return await asyncio.wait_for(asyncio.to_thread(_anthropic_ping), timeout=15.0)

    async def _check_market_overview():
        from nq_api.routes.market import _market_overview_sync
        result = await asyncio.wait_for(asyncio.to_thread(_market_overview_sync, "US"), timeout=8.0)
        indices = result.get("indices", []) if isinstance(result, dict) else []
        if indices:
            return {"ok": True, "indices_count": len(indices)}
        return {"ok": False, "error": "no indices returned"}

    async def _check_stock_meta(ticker: str, market: str):
        """Hit /stocks/{ticker}/meta internally via httpx."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.get(
                    f"http://127.0.0.1:10000/stocks/{ticker}/meta",
                    params={"market": market},
                )
            if r.status_code == 200:
                data = r.json()
                # IN stocks may lack current_price on Render (yfinance blocked),
                # so check for any meaningful fundamental field
                key_fields = ("current_price", "pe_ttm", "pb_ratio", "beta", "sector", "name")
                present = [k for k in key_fields if data.get(k) is not None]
                if present:
                    return {"ok": True, "fields_present": present}
                return {"ok": False, "error": "no meaningful fields in meta"}
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _check_screener_preview():
        from nq_api.cache.score_cache import read_top
        rows = await asyncio.wait_for(asyncio.to_thread(read_top, "US", 8), timeout=5.0)
        return {"ok": bool(rows), "results_count": len(rows) if rows else 0}

    async def _check_score_cache_age():
        from nq_api.cache.score_cache import _supabase_rest
        data = await asyncio.to_thread(
            _supabase_rest, "score_cache", "GET",
            {"select": "computed_at", "order": "computed_at.desc", "limit": "1"},
        )
        if isinstance(data, list) and data:
            last = data[0].get("computed_at")
            if last:
                dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age = int((datetime.now(timezone.utc) - dt).total_seconds())
                return {"ok": age < 7200, "age_seconds": age}
        return {"ok": False, "age_seconds": None}

    async def _check_stock_snapshot():
        from nq_api.cache.score_cache import _supabase_rest
        data = await asyncio.to_thread(
            _supabase_rest, "stock_snapshot", "GET",
            {"select": "id", "limit": "0"},
        )
        # PostgREST doesn't return count with limit=0, use prefer count
        # Fallback: just try to read 1 row
        data2 = await asyncio.to_thread(
            _supabase_rest, "stock_snapshot", "GET",
            {"select": "ticker", "limit": "1"},
        )
        has_rows = isinstance(data2, list)
        return {"ok": has_rows}

    # ── Run all checks in parallel ──────────────────────────────────────
    await asyncio.gather(
        _check("supabase", _check_supabase()),
        _check("fmp_api", _check_fmp()),
        _check("anthropic_api", _check_anthropic()),
        _check("market_overview", _check_market_overview()),
        _check("stock_meta_aapl", _check_stock_meta("AAPL", "US")),
        _check("stock_meta_tcs", _check_stock_meta("TCS", "IN")),
        _check("screener_preview", _check_screener_preview()),
        _check("score_cache", _check_score_cache_age()),
        _check("stock_snapshot", _check_stock_snapshot()),
    )

    # Determine overall status
    ok_count = sum(1 for c in checks.values() if c.get("ok"))
    total = len(checks)
    if ok_count == total:
        status = "ok"
    elif ok_count == 0:
        status = "down"
    else:
        status = "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "failures": failures,
        "summary": f"{ok_count}/{total} checks passed",
    }


@app.get("/health/score-cache")
def health_score_cache():
    """Return score-cache freshness. 503 if stale >2h."""
    from nq_api.cache.score_cache import _supabase_rest
    data = _supabase_rest(
        "score_cache",
        "GET",
        {"select": "computed_at", "order": "computed_at.desc", "limit": "1"},
    )
    count_data = _supabase_rest(
        "score_cache",
        "GET",
        {"select": "count()"},
    )
    rows = None
    if isinstance(count_data, list) and count_data:
        rows = count_data[0].get("count")

    if isinstance(data, list) and data:
        last = data[0].get("computed_at")
        if last:
            from datetime import datetime, timezone, timedelta
            try:
                dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
                stale = age_seconds > 7200  # 2 hours
                return {
                    "status": "stale" if stale else "ok",
                    "last_computed": last,
                    "age_seconds": int(age_seconds),
                    "rows": rows,
                }
            except Exception:
                pass
    return {"status": "stale", "last_computed": None, "age_seconds": None, "rows": rows}
