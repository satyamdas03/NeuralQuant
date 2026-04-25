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

from nq_api.routes import stocks, screener, analyst, query, market, auth, watchlists, sentiment, backtest, alerts, newsdesk, smart_money
from nq_api.routes.checkout import router as checkout_router
from nq_api.routes.webhooks_stripe import router as stripe_webhook_router
from nq_api.routes.referrals import router as referral_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    # On Render, skip heavy prewarm — caches populate lazily on first request.
    # Prewarm threads with yfinance + asyncio.run() cause OOM/crash on cold starts.
    on_render = bool(os.environ.get("RENDER"))

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

        def _warm_smart_money():
            try:
                from nq_api.routes.smart_money import refresh_cache_in_thread
                refresh_cache_in_thread()
            except Exception as exc:
                log.warning("Smart-money prewarm failed: %s", exc)

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
        threading.Timer(10.0, _warm_smart_money).start()
        threading.Timer(20.0, _warm_news).start()
    else:
        log.info("Render detected — skipping prewarm, caches will populate lazily")
    yield


app = FastAPI(title="NeuralQuant API", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://neuralquant.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
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
app.include_router(smart_money.router)
app.include_router(checkout_router)
app.include_router(stripe_webhook_router)
app.include_router(referral_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
