"""Backtest endpoint (Pillar D).

Lightweight SMA-crossover backtester. backtrader is heavy and slow to install
in serverless cold starts, so we implement a pure-pandas vectorized backtest
that computes the same metrics (Sharpe, max drawdown, final return, trade count).

Gated by tier quota (backtest_per_day).
"""
from __future__ import annotations
import logging
from typing import Any, Literal
import asyncio
import math

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


class BacktestRequest(BaseModel):
    ticker: str
    market: Literal["US", "IN"] = "US"
    strategy: Literal["sma_crossover"] = "sma_crossover"
    fast: int = Field(20, ge=2, le=200)
    slow: int = Field(50, ge=5, le=400)
    period: Literal["1y", "2y", "5y", "10y", "max"] = "2y"
    initial_capital: float = 10_000.0


class BacktestPoint(BaseModel):
    date: str
    equity: float


class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    final_equity: float
    total_return_pct: float
    buy_hold_return_pct: float
    sharpe: float
    max_drawdown_pct: float
    n_trades: int
    n_days: int
    equity_curve: list[BacktestPoint]


def _sma_crossover(prices: pd.Series, fast: int, slow: int) -> pd.Series:
    """Return 1 (long) / 0 (flat) signal based on SMA crossover. Shift(1) to avoid lookahead."""
    sma_f = prices.rolling(fast).mean()
    sma_s = prices.rolling(slow).mean()
    raw = (sma_f > sma_s).astype(int)
    return raw.shift(1).fillna(0).astype(int)


def _metrics(equity: pd.Series, signal: pd.Series) -> dict[str, float]:
    rets = equity.pct_change().fillna(0)
    # Sharpe: annualized, 252 trading days
    if rets.std() > 0:
        sharpe = float(rets.mean() / rets.std() * math.sqrt(252))
    else:
        sharpe = 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    mdd = float(drawdown.min() * 100) if len(drawdown) else 0.0
    # trade count = number of signal flips
    trades = int((signal.diff().abs() == 1).sum())
    return {"sharpe": round(sharpe, 3), "max_drawdown_pct": round(mdd, 2), "n_trades": trades}


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    user: User = Depends(enforce_tier_quota("backtest")),
) -> BacktestResponse:
    if req.fast >= req.slow:
        raise HTTPException(status_code=400, detail="fast must be < slow")

    result = await asyncio.to_thread(_run_backtest_sync, req)
    if isinstance(result, HTTPException):
        raise result
    return result


def _run_backtest_sync(req: BacktestRequest) -> BacktestResponse | HTTPException:
    """Blocking backtest compute — runs in thread pool."""
    import yfinance as yf

    yf_symbol = f"{req.ticker.upper()}.NS" if req.market == "IN" else req.ticker.upper()
    df = yf.download(yf_symbol, period=req.period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return HTTPException(status_code=404, detail=f"no price data for {req.ticker}")

    # yfinance may return MultiIndex cols when multiple tickers; flatten.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    close = df["Close"].dropna()
    if len(close) < req.slow + 10:
        return HTTPException(status_code=400, detail=f"insufficient price history ({len(close)} days)")

    signal = _sma_crossover(close, req.fast, req.slow)
    daily_ret = close.pct_change().fillna(0)
    strat_ret = daily_ret * signal
    equity = (1 + strat_ret).cumprod() * req.initial_capital

    bh_return = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
    total_return = float((equity.iloc[-1] / req.initial_capital - 1) * 100)
    m = _metrics(equity, signal)

    # Downsample curve to <=200 points for payload size
    step = max(1, len(equity) // 200)
    curve = [
        BacktestPoint(date=str(d.date()), equity=round(float(v), 2))
        for d, v in zip(equity.index[::step], equity.values[::step])
    ]

    return BacktestResponse(
        ticker=req.ticker.upper(),
        strategy=req.strategy,
        final_equity=round(float(equity.iloc[-1]), 2),
        total_return_pct=round(total_return, 2),
        buy_hold_return_pct=round(bh_return, 2),
        sharpe=m["sharpe"],
        max_drawdown_pct=m["max_drawdown_pct"],
        n_trades=m["n_trades"],
        n_days=len(close),
        equity_curve=curve,
    )


# ═══════════════════════════════════════════════════════════════════
# Accuracy Endpoint — walk-forward validation results
# ═══════════════════════════════════════════════════════════════════


class AccuracyResponse(BaseModel):
    hit_rate_at_7plus: float
    hit_rate_at_5plus: float
    baseline_hit_rate: float
    mean_return_top_decile: float
    mean_return_bottom_decile: float
    top_minus_bottom_spread: float
    sharpe_top_quartile: float
    max_drawdown_top_quartile: float
    win_rate_top_quartile: float
    observation_count: int
    period_start: str
    period_end: str
    avg_stocks_per_period: float
    methodology: str
    comparison: str
    note: str


@router.get("/accuracy", response_model=AccuracyResponse)
def get_accuracy() -> AccuracyResponse:
    """
    Returns walk-forward backtest accuracy metrics for NeuralQuant ForeCast scores.

    Hit rate = % of stocks with positive forward 3-month return at each score threshold.
    This is the same metric competitors (Danelfin: 70%, Trade Ideas: 65%) publish.
    """
    try:
        from nq_signals.backtest import run_walk_forward
        import yfinance as yf

        rows = _score_cache_rows()
        if not rows or len(rows) < 50:
            return _accuracy_default("Insufficient score cache data (need 50+ stocks)")

        score_history = pd.DataFrame(rows)
        score_history["date"] = pd.to_datetime(
            score_history.get("last_updated", score_history.get("scored_at", pd.Timestamp.now()))
        )
        score_history["ticker"] = score_history["ticker"].str.upper()

        tickers = score_history["ticker"].unique()[:100]
        prices = yf.download(tickers.tolist(), period="6mo", progress=False)
        if prices is None or prices.empty:
            return _accuracy_default("Failed to fetch price data")

        if isinstance(prices.columns, pd.MultiIndex):
            prices = prices.stack(level=1, future_stack=True).reset_index()
            prices.rename(columns={"Close": "close", "level_0": "date"}, inplace=True)
        else:
            prices = prices.reset_index()
            prices.rename(columns={"Close": "close"}, inplace=True)

        if "ticker" not in prices.columns:
            prices["ticker"] = tickers[0]

        prices["date"] = pd.to_datetime(prices["date"])

        result = run_walk_forward(score_history, prices, forward_months=3)

        return AccuracyResponse(
            hit_rate_at_7plus=round(result.hit_rate_at_7plus * 100, 1),
            hit_rate_at_5plus=round(result.hit_rate_at_5plus * 100, 1),
            baseline_hit_rate=round(result.baseline_hit_rate * 100, 1),
            mean_return_top_decile=round(result.mean_return_top_decile * 100, 1),
            mean_return_bottom_decile=round(result.mean_return_bottom_decile * 100, 1),
            top_minus_bottom_spread=round(result.top_minus_bottom_spread * 100, 1),
            sharpe_top_quartile=round(result.sharpe_top_quartile, 2),
            max_drawdown_top_quartile=round(result.max_drawdown_top_quartile * 100, 1),
            win_rate_top_quartile=round(result.win_rate_top_quartile * 100, 1),
            observation_count=result.observation_count,
            period_start=result.period_start,
            period_end=result.period_end,
            avg_stocks_per_period=result.avg_stocks_per_period,
            methodology="Walk-forward: each month-end, composite scores predict forward 3-month returns. Hit rate = % of stocks with positive return at given score threshold.",
            comparison="Danelfin: 70% at AI Score >=7 | Trade Ideas: 65% claimed | Prospero: ~54-60%",
            note="Scores use free-tier data (15-min delayed). Publish date: " + pd.Timestamp.now().strftime("%Y-%m-%d"),
        )
    except Exception as e:
        logger.warning("Backtest accuracy: %s", e)
        return _accuracy_default(str(e))


def _score_cache_rows() -> list[dict]:
    """Fetch score cache rows from Supabase."""
    try:
        import httpx
        import os
        supabase_url = os.environ.get("SUPABASE_URL", "")
        anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not supabase_url or not anon_key:
            return []
        resp = httpx.get(
            f"{supabase_url}/rest/v1/score_cache?select=*&limit=500",
            headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def _accuracy_default(reason: str) -> AccuracyResponse:
    return AccuracyResponse(
        hit_rate_at_7plus=0.0,
        hit_rate_at_5plus=0.0,
        baseline_hit_rate=0.0,
        mean_return_top_decile=0.0,
        mean_return_bottom_decile=0.0,
        top_minus_bottom_spread=0.0,
        sharpe_top_quartile=0.0,
        max_drawdown_top_quartile=0.0,
        win_rate_top_quartile=0.0,
        observation_count=0,
        period_start="",
        period_end="",
        avg_stocks_per_period=0.0,
        methodology="Walk-forward validation",
        comparison="Competitor benchmark",
        note=f"Unavailable: {reason}",
    )
