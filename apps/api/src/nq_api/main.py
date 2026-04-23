# apps/api/src/nq_api/main.py
from pathlib import Path
from dotenv import load_dotenv
# Load .env from apps/api/ regardless of CWD
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path, override=True)

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nq_api.routes import stocks, screener, analyst, query, market, auth, watchlists, sentiment, backtest, alerts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm real-data cache in a background thread so first requests are fast
    def _warm():
        try:
            from nq_api.data_builder import prewarm_cache
            from nq_api.universe import US_DEFAULT
            prewarm_cache(US_DEFAULT, "US")
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()
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


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
