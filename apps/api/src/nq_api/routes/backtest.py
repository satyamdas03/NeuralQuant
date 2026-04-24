"""Backtest endpoint (Pillar D).

Lightweight SMA-crossover backtester. backtrader is heavy and slow to install
in serverless cold starts, so we implement a pure-pandas vectorized backtest
that computes the same metrics (Sharpe, max drawdown, final return, trade count).

Gated by tier quota (backtest_per_day).
"""
from __future__ import annotations
from typing import Any, Literal
import asyncio
import math

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User

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
