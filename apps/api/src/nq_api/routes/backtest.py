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

from nq_api.auth.rate_limit import enforce_guest_quota
from nq_api.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


class BacktestRequest(BaseModel):
    ticker: str
    market: Literal["US", "IN"] = "US"
    strategy: Literal["sma_crossover"] = "sma_crossover"
    fast: int = Field(20, ge=2, le=200)
    slow: int = Field(50, ge=5, le=400)
    period: Literal["1y", "2y", "3y", "5y", "10y", "max"] = "2y"
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
    user: User | None = Depends(enforce_guest_quota("backtest")),
) -> BacktestResponse:
    if req.fast >= req.slow:
        raise HTTPException(status_code=400, detail="fast must be < slow")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_backtest_sync, req),
            timeout=30.0,
        )
        if isinstance(result, HTTPException):
            raise result
        return result
    except asyncio.TimeoutError:
        logger.warning("backtest timed out for %s after 30s", req.ticker)
        # Return partial result with zeroed metrics instead of a 504
        return BacktestResponse(
            ticker=req.ticker.upper(),
            strategy=req.strategy,
            final_equity=req.initial_capital,
            total_return_pct=0.0,
            buy_hold_return_pct=0.0,
            sharpe=0.0,
            max_drawdown_pct=0.0,
            n_trades=0,
            n_days=0,
            equity_curve=[],
        )


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


class ScoreBreakdownItem(BaseModel):
    score: int                # 1-10
    count: int               # number of observations at this score
    hit_rate: float          # % with positive forward return
    avg_return_pct: float    # average forward 3M return %

class TopStockItem(BaseModel):
    ticker: str
    name: str | None = None
    score_1_10: int
    composite_score: float
    return_3m_pct: float | None = None  # forward 3M return (None if not yet measurable)

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
    is_fallback: bool = False
    score_breakdown: list[ScoreBreakdownItem] = []
    top_stocks_snapshot: list[TopStockItem] = []


@router.get("/accuracy", response_model=AccuracyResponse)
async def get_accuracy() -> AccuracyResponse:
    """
    Returns walk-forward backtest accuracy metrics for NeuralQuant ForeCast scores.

    Hit rate = % of stocks with positive forward 3-month return at each score threshold.
    This is the same metric competitors (Danelfin: 70%, Trade Ideas: 65%) publish.
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_get_accuracy_sync),
            timeout=45.0,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Backtest accuracy: timed out after 45s")
        return _accuracy_default("Accuracy calculation timed out. Score data is accumulating — check back later.")
    except Exception as e:
        import traceback
        logger.warning("Backtest accuracy: %s\n%s", e, traceback.format_exc())
        return _accuracy_default(str(e))


def _get_accuracy_sync() -> AccuracyResponse:
    """Blocking accuracy compute — runs in thread pool with 45s timeout."""
    from nq_signals.backtest import run_walk_forward
    import yfinance as yf

    try:
        rows = _score_cache_rows()
        if not rows or len(rows) < 50:
            return _accuracy_default("Insufficient score cache data (need 50+ stocks)")

        score_history = pd.DataFrame(rows)
        date_col = next(
            (c for c in ("computed_at", "last_updated", "scored_at", "created_at")
             if c in score_history.columns),
            None,
        )
        if date_col:
            score_history["date"] = pd.to_datetime(score_history[date_col])
            # Check staleness: if newest data > 30 days old, accuracy is unreliable
            newest = score_history["date"].max()
            age_days = (pd.Timestamp.now(tz=newest.tz) - newest).days if newest.tz else (pd.Timestamp.now() - newest).days
            if age_days > 30:
                logger.warning("Backtest accuracy: score_cache data is %d days old (stale)", age_days)
                return _accuracy_default(
                    f"Score cache data is {age_days} days old. Accuracy metrics require fresh data. "
                    "Trigger nightly-score GHA workflow to refresh."
                )
            # Guard: need at least 2 distinct CALENDAR dates for walk-forward validation
            # Normalize to date-only to avoid same-day timestamps passing the check
            score_history["date_only"] = score_history["date"].dt.normalize()
            n_dates = score_history["date_only"].nunique()
            if n_dates < 2:
                # Single-date fallback: show top stocks snapshot from current data
                # instead of returning "unavailable"
                return _single_date_snapshot(score_history, n_dates)
            # If date range spans < 90 days, walk-forward metrics will be unreliable
            # (3-month forward returns need 3+ months of price data after scoring).
            # Show snapshot view until we have enough history.
            date_range_days = (score_history["date_only"].max() - score_history["date_only"].min()).days
            if date_range_days < 90:
                return _single_date_snapshot(score_history, n_dates, date_range_days)
        else:
            score_history["date"] = pd.Timestamp.now()
            score_history["date_only"] = score_history["date"].dt.normalize()
        score_history["ticker"] = score_history["ticker"].str.upper()

        # Derive score_1_10 from composite_score if null (history table doesn't store it)
        if "score_1_10" not in score_history.columns or score_history["score_1_10"].isna().all():
            from nq_api.score_builder import _score_to_1_10
            score_history["score_1_10"] = score_history["composite_score"].apply(
                lambda s: _score_to_1_10(s) if pd.notna(s) else None
            )
        else:
            # Fill null score_1_10 from composite_score
            from nq_api.score_builder import _score_to_1_10
            mask = score_history["score_1_10"].isna() & score_history["composite_score"].notna()
            score_history.loc[mask, "score_1_10"] = score_history.loc[mask, "composite_score"].apply(_score_to_1_10)

        # Drop rows where score_1_10 is still null (no composite_score either)
        score_history = score_history[score_history["score_1_10"].notna()].copy()

        # Use US tickers only — yfinance can't download Indian tickers without .NS suffix
        us_rows = score_history[score_history.get("market", "US") == "US"]
        if len(us_rows) < 20:
            us_rows = score_history  # fallback: use all if too few US rows
        tickers = us_rows["ticker"].unique()[:100]

        # Add .NS suffix for Indian tickers so yfinance can find them
        yf_tickers = []
        for t in tickers:
            market = us_rows.loc[us_rows["ticker"] == t, "market"].iloc[0] if "market" in us_rows.columns else "US"
            yf_tickers.append(f"{t}.NS" if market == "IN" else t)

        prices = yf.download(yf_tickers, period="6mo", progress=False)
        if prices is None or prices.empty:
            return _accuracy_default("Failed to fetch price data")

        # Normalize yfinance output into [date, ticker, close] format
        if isinstance(prices.columns, pd.MultiIndex):
            prices = prices.stack(level=1, future_stack=True).reset_index()
        else:
            prices = prices.reset_index()

        # yfinance returns "Date"/"Ticker"/"Close" — normalize to lowercase
        rename = {}
        for c in list(prices.columns):
            name = c[0] if isinstance(c, tuple) else c
            if isinstance(name, str):
                nl = name.lower()
                if nl in ("date", "level_0"):
                    rename[c] = "date"
                elif nl == "close":
                    rename[c] = "close"
                elif nl == "ticker":
                    rename[c] = "ticker"
        prices.rename(columns=rename, inplace=True)

        # Ensure we have the required columns
        if "ticker" not in prices.columns:
            prices["ticker"] = yf_tickers[0] if len(yf_tickers) == 1 else prices.get("Ticker", yf_tickers[0])
        if "date" not in prices.columns:
            for c in prices.columns:
                if pd.api.types.is_datetime64_any_dtype(prices[c]):
                    prices.rename(columns={c: "date"}, inplace=True)
                    break

        # Drop rows with missing close prices
        prices = prices.dropna(subset=["close"])

        if prices.empty:
            return _accuracy_default("No valid price data after cleanup")

        prices["date"] = pd.to_datetime(prices["date"])

        # Strip .NS suffix so tickers match score_history
        prices["ticker"] = prices["ticker"].str.replace(r"\.(NS|BO)$", "", regex=True)

        # Normalize timezones: strip tz info to avoid tz-aware vs tz-naive comparisons
        # Use date_only (date-normalized) so same-day timestamps don't create fake periods
        score_history["date"] = pd.to_datetime(score_history["date_only"]).dt.tz_localize(None)
        score_history.drop(columns=["date_only"], inplace=True)
        prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)

        # Filter score_history to only tickers we have price data for
        available_tickers = set(prices["ticker"].unique())
        score_history = score_history[score_history["ticker"].isin(available_tickers)]

        # Drop rows with NaN composite_score — pd.qcut cannot handle NaN
        score_history = score_history.dropna(subset=["composite_score"])
        if len(score_history) < 20:
            return _accuracy_default(f"Insufficient matching score data ({len(score_history)} rows)")

        result = run_walk_forward(score_history, prices, forward_months=3)

        # ── Compute score_breakdown from walk-forward data ──
        score_breakdown = []
        if "score_1_10" in score_history.columns:
            for score_level in range(1, 11):
                mask = score_history["score_1_10"] == score_level
                subset = score_history[mask]
                if len(subset) == 0:
                    continue
                # Merge with price data to compute returns
                hit_count = 0
                total_return_pct = []
                for _, row in subset.iterrows():
                    tkr = row["ticker"]
                    score_date = row["date"]
                    tkr_prices = prices[prices["ticker"] == tkr].sort_values("date")
                    start_prices = tkr_prices[tkr_prices["date"] >= score_date]
                    if len(start_prices) < 2:
                        continue
                    start_price = float(start_prices.iloc[0]["close"])
                    # 3-month forward return
                    end_idx = min(63, len(start_prices) - 1)  # ~63 trading days = 3 months
                    end_price = float(start_prices.iloc[end_idx]["close"])
                    if start_price > 0:
                        ret = (end_price - start_price) / start_price
                        total_return_pct.append(ret * 100)
                        if ret > 0:
                            hit_count += 1
                n = len(total_return_pct)
                if n > 0:
                    score_breakdown.append(ScoreBreakdownItem(
                        score=score_level,
                        count=n,
                        hit_rate=round(hit_count / n * 100, 1),
                        avg_return_pct=round(sum(total_return_pct) / n, 1),
                    ))

        # ── Compute top_stocks_snapshot from current score_cache ──
        top_stocks_snapshot = []
        try:
            from nq_api.cache.score_cache import _supabase_rest
            current_scores = _supabase_rest(
                "score_cache", "GET",
                {"select": "ticker,market,composite_score,score_1_10,current_price", "order": "composite_score.desc", "limit": "10", "market": "eq.US"},
            )
            if isinstance(current_scores, list):
                for s in current_scores[:10]:
                    tkr = s.get("ticker", "")
                    top_stocks_snapshot.append(TopStockItem(
                        ticker=tkr,
                        name=None,
                        score_1_10=s.get("score_1_10") or 0,
                        composite_score=round(s.get("composite_score") or 0, 4),
                        return_3m_pct=None,  # Would need forward-looking data
                    ))
        except Exception:
            pass  # Non-critical, skip

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
            score_breakdown=score_breakdown,
            top_stocks_snapshot=top_stocks_snapshot,
        )
    except Exception as e:
        import traceback
        logger.warning("Backtest accuracy: %s\n%s", e, traceback.format_exc())
        return _accuracy_default(str(e))


def _score_cache_rows() -> list[dict]:
    """Fetch score cache rows from Supabase. Prefers score_cache_history (all snapshots)
    over score_cache (latest only) for walk-forward validation depth.

    Fetches the most recent rows per date group so walk-forward gets distinct dates,
    rather than just the earliest 2000 rows which may all share one date.
    """
    from nq_api.cache.score_cache import _supabase_rest
    # Try history table first (has multiple dates for walk-forward)
    try:
        # Fetch recent rows (desc order) to ensure we span multiple dates
        data = _supabase_rest("score_cache_history", "GET", {"select": "*", "limit": "2000", "order": "computed_at.desc"})
        if isinstance(data, list) and len(data) >= 50:
            # Reverse to chronological order for walk-forward
            data.reverse()
            return data
    except Exception:
        pass  # Table may not exist yet
    # Fallback to current score_cache
    data = _supabase_rest("score_cache", "GET", {"select": "*", "limit": "500"})
    return data if isinstance(data, list) else []


def _single_date_snapshot(score_history: pd.DataFrame, n_dates: int, date_range_days: int = 0) -> AccuracyResponse:
    """Return a snapshot-only accuracy response when walk-forward validation isn't possible yet.

    Shows current top stocks and score distribution without requiring 2+ historical dates.
    """
    logger.info("_single_date_snapshot: %d rows, columns=%s", len(score_history), list(score_history.columns))
    us_rows = score_history[score_history.get("market", "US") == "US"] if "market" in score_history.columns else score_history
    logger.info("_single_date_snapshot: US rows after filter=%d", len(us_rows))
    if len(us_rows) < 5:
        us_rows = score_history

    # Derive score_1_10 from composite_score if null
    from nq_api.score_builder import _score_to_1_10
    if "score_1_10" not in us_rows.columns or us_rows["score_1_10"].isna().all():
        us_rows["score_1_10"] = us_rows["composite_score"].apply(
            lambda s: _score_to_1_10(s) if pd.notna(s) else None
        )
    else:
        mask = us_rows["score_1_10"].isna() & us_rows["composite_score"].notna()
        us_rows.loc[mask, "score_1_10"] = us_rows.loc[mask, "composite_score"].apply(_score_to_1_10)

    # Compute score distribution from current snapshot
    score_col = "score_1_10" if "score_1_10" in us_rows.columns else None
    comp_col = "composite_score" if "composite_score" in us_rows.columns else None

    # Drop rows where score_1_10 is still null
    if score_col and score_col in us_rows.columns:
        us_rows = us_rows[us_rows[score_col].notna()].copy()
    logger.info("_single_date_snapshot: after score_1_10 derivation, rows=%d, sample=%s", len(us_rows), us_rows[["ticker","score_1_10","composite_score"]].head(3).to_dict() if len(us_rows) > 0 else "empty")

    score_breakdown = []
    if score_col and score_col in us_rows.columns:
        for level in range(1, 11):
            count = int((us_rows[score_col] == level).sum())
            if count > 0:
                avg_comp = float(us_rows.loc[us_rows[score_col] == level, comp_col].dropna().mean()) if comp_col and comp_col in us_rows.columns else level / 10
                score_breakdown.append(ScoreBreakdownItem(
                    score=level, count=count,
                    hit_rate=round(avg_comp * 100, 1),
                    avg_return_pct=0.0,
                ))

    # Top stocks from current snapshot
    top_stocks = []
    if comp_col and comp_col in us_rows.columns:
        top_rows = us_rows.nlargest(10, comp_col)
        for _, row in top_rows.iterrows():
            raw_score = row.get("score_1_10")
            top_stocks.append(TopStockItem(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("long_name", "")) if row.get("long_name") else None,
                score_1_10=int(raw_score) if raw_score is not None else 0,
                composite_score=round(float(row.get("composite_score") or 0), 4),
                return_3m_pct=None,
            ))

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
        observation_count=len(us_rows),
        period_start=str(us_rows["date_only"].min()) if "date_only" in us_rows.columns else "",
        period_end=str(us_rows["date_only"].max()) if "date_only" in us_rows.columns else "",
        avg_stocks_per_period=float(len(us_rows)),
        methodology="Current snapshot (walk-forward pending)",
        comparison="Snapshot view",
        note=f"Walk-forward validation needs 90+ days of history (have {n_dates} dates spanning {date_range_days}d). "
             "Showing current score distribution. Accuracy metrics will appear once 3+ months of snapshots accumulate. "
             f"({n_dates} dates, {len(us_rows)} observations)",
        is_fallback=True,
        score_breakdown=score_breakdown,
        top_stocks_snapshot=top_stocks,
    )


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
        is_fallback=True,
        score_breakdown=[],
        top_stocks_snapshot=[],
    )
