"""Trade signals router — automated trading with risk management.

Endpoints:
  GET  /trade/signals       — Run screener → edge detection → Kelly sizing
  GET  /trade/strategies    — Strategy presets for trade screening
  GET  /trade/calibration   — Signal accuracy report (hit rate, Sharpe, PnL)
  GET  /trade/risk-profile  — Map user risk profile to risk parameters
  POST /trade/log-signal    — Log a signal for calibration tracking
  POST /trade/resolve       — Resolve a signal with PnL outcome

All endpoints public (guest access). No auth required.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import APIRouter

from nq_api.cache import score_cache
from nq_api.universe import UNIVERSE_BY_MARKET

log = logging.getLogger(__name__)

router = APIRouter()

# ── Strategy presets (extends screener PRESETS with risk params) ────────────

TRADE_STRATEGIES = [
    {
        "id": "momentum_breakout",
        "name": "Momentum Breakout",
        "description": "Strong upward momentum stocks with high edge scores",
        "icon": "TrendingUp",
        "risk_profile": "aggressive",
        "kelly_fraction": 0.40,
        "min_edge_score": 0.62,
        "max_positions": 8,
        "max_bet": 5000.0,
    },
    {
        "id": "value_play",
        "name": "Value Play",
        "description": "Undervalued quality stocks — balanced sizing",
        "icon": "DollarSign",
        "risk_profile": "balanced",
        "kelly_fraction": 0.25,
        "min_edge_score": 0.60,
        "max_positions": 10,
        "max_bet": 5000.0,
    },
    {
        "id": "dividend_income",
        "name": "Dividend Income",
        "description": "Low-volatility quality stocks — conservative sizing",
        "icon": "Banknote",
        "risk_profile": "conservative",
        "kelly_fraction": 0.15,
        "min_edge_score": 0.65,
        "max_positions": 12,
        "max_bet": 3000.0,
    },
    {
        "id": "quality_compound",
        "name": "Quality Compound",
        "description": "Long-term compounders — balanced sizing, wider diversification",
        "icon": "Gem",
        "risk_profile": "balanced",
        "kelly_fraction": 0.25,
        "min_edge_score": 0.65,
        "max_positions": 10,
        "max_bet": 5000.0,
    },
    {
        "id": "contrarian_bet",
        "name": "Contrarian Bet",
        "description": "Beaten-down quality — aggressive sizing, tight stops",
        "icon": "RotateCcw",
        "risk_profile": "aggressive",
        "kelly_fraction": 0.40,
        "min_edge_score": 0.75,
        "max_positions": 5,
        "max_bet": 2500.0,
    },
    {
        "id": "macro_tailwind",
        "name": "Macro Tailwind",
        "description": "Regime-aligned stocks — conservative when bear, aggressive when risk-on",
        "icon": "Globe",
        "risk_profile": "balanced",
        "kelly_fraction": 0.25,
        "min_edge_score": 0.60,
        "max_positions": 10,
        "max_bet": 5000.0,
    },
]


def _get_todays_pnl_from_log(market: str = "US") -> float:
    """Sum today's resolved PnL from signal_log. Returns negative for losses."""
    from nq_api.cache.score_cache import _supabase_rest
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _supabase_rest(
        "signal_log",
        method="GET",
        query={
            "select": "pnl",
            "market": f"eq.{market}",
            "resolved": "eq.true",
            "resolution_date": f"gte.{today}T00:00:00Z",
        },
    )
    if not rows or not isinstance(rows, list):
        return 0.0
    return sum(float(r.get("pnl", 0) or 0) for r in rows)


def _daily_loss_limit_for_strategy(strategy_id: str) -> float:
    """Map strategy to daily loss limit via risk profile."""
    risk_map = {
        "conservative": 50.0,
        "balanced": 100.0,
        "aggressive": 200.0,
    }
    strat = next((s for s in TRADE_STRATEGIES if s["id"] == strategy_id), TRADE_STRATEGIES[0])
    return risk_map.get(strat.get("risk_profile", "balanced"), 100.0)


def _rows_to_signals(
    rows: list[dict[str, Any]],
    bankroll: float,
    strategy: dict,
) -> list[dict[str, Any]]:
    """Convert score_cache rows to trade signals with risk sizing."""
    from nq_signals.risk import compute_edge, size_position_kelly

    threshold = strategy["min_edge_score"]
    kelly_frac = strategy["kelly_fraction"]
    max_bet = strategy["max_bet"]

    signals: list[dict[str, Any]] = []
    for row in rows:
        score = float(row.get("composite_score", 0))
        edge = compute_edge(score, threshold)
        if edge <= 0:
            continue

        sizing = size_position_kelly(
            edge=edge,
            bankroll=bankroll,
            kelly_fraction=kelly_frac,
            max_bet=max_bet,
        )
        if sizing.bet <= 0:
            continue

        signals.append({
            "ticker": row.get("ticker", ""),
            "market": row.get("market", "US"),
            "sector": row.get("sector", ""),
            "composite_score": round(score, 4),
            "edge": round(edge, 4),
            "direction": "bullish",
            "bet": sizing.bet,
            "capped": sizing.capped,
            "current_price": row.get("current_price"),
            "pe_ttm": row.get("pe_ttm"),
            "analyst_target": row.get("analyst_target"),
            "market_cap": row.get("market_cap"),
            "strategy": strategy["id"],
            "kelly_fraction": kelly_frac,
        })

    return signals


def _compute_live_signals(
    market: str,
    tickers: list[str],
    n: int,
    strat: dict,
    bankroll: float,
) -> list[dict[str, Any]]:
    """Fast live signal computation using FMP parallel data fetch.

    Fetches batch quotes + per-ticker key metrics, financial scores, profiles
    concurrently via ThreadPoolExecutor. Computes simplified composite_score
    cross-sectionally, then applies edge detection + Kelly sizing.

    Returns empty list on data fetch failure (caller falls back to empty response).
    """
    import os
    import httpx
    from nq_signals.risk import compute_edge, size_position_kelly

    api_key = os.environ.get("FMP_API_KEY", "")
    base_url = os.environ.get("FMP_BASE_URL", "https://financialmodelingprep.com/stable")
    if not api_key:
        return []

    top_tickers = tickers[: min(n, 50)]

    # Step 1: Batch quotes — use shared FMP client (single call, no threading issue)
    from nq_data.fmp import get_fmp_client
    fmp_shared = get_fmp_client()
    batch_quotes = fmp_shared.get_batch_quotes(top_tickers) or {}

    # Step 2: Per-ticker data in parallel — each thread owns its httpx.Client
    def _fetch_one(ticker: str):
        """Fetch key_metrics + financial_scores + profile + quote for one ticker.
        Uses dedicated httpx.Client per thread (thread-safe)."""
        local_client = httpx.Client(timeout=15.0, follow_redirects=True)
        sym = ticker  # US tickers match FMP symbols; IN needs .NS (handled separately)
        try:
            def _get(endpoint: str, extra_params: dict | None = None):
                params = {"symbol": sym, "apikey": api_key}
                if extra_params:
                    params.update(extra_params)
                r = local_client.get(f"{base_url}/{endpoint}", params=params)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and data:
                        return data[0]
                return None

            metrics = _get("key-metrics", {"period": "annual"})
            scores = _get("financial-scores")
            profile_data = _get("profile")
            quote_data = _get("quote")
            return ticker, metrics, scores, profile_data, quote_data
        except Exception:
            return ticker, None, None, None, None
        finally:
            local_client.close()

    ticker_data: dict[str, tuple] = {}
    # 6 workers keeps FMP calls ~24/sec peak (safe under 750/min Premium limit)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in top_tickers}
        for future in as_completed(futures, timeout=15):
            try:
                ticker, metrics, scores, profile, quote = future.result()
                ticker_data[ticker] = (metrics, scores, profile, quote)
            except Exception:
                pass

    if not ticker_data:
        return []

    # Step 3: Build rows with essential columns from raw FMP responses
    rows: list[dict[str, Any]] = []
    for ticker in top_tickers:
        metrics, scores, profile, quote = ticker_data.get(ticker, (None, None, None, None))
        bq = batch_quotes.get(ticker, {})

        # Extract from raw FMP dicts (not normalized FMPClient return)
        price = bq.get("price") or (profile or {}).get("price")
        pe = bq.get("pe") or (metrics or {}).get("peRatio")
        mcap = bq.get("market_cap") or (metrics or {}).get("marketCap") or (profile or {}).get("marketCap")

        gross_margin = (metrics or {}).get("grossProfitMargin")
        roe_val = (metrics or {}).get("returnOnEquity") or (metrics or {}).get("roe")
        pb = (metrics or {}).get("pbRatio") or (metrics or {}).get("priceToBookRatio")
        beta = (metrics or {}).get("beta") or (profile or {}).get("beta")
        sector = (profile or {}).get("sector", "")
        name = (profile or {}).get("companyName", ticker)

        piotroski = (scores or {}).get("piotroskiScore")

        # Momentum: approximate from 52w price position in range
        year_high = (quote or {}).get("yearHigh")
        year_low = (quote or {}).get("yearLow")
        momentum_raw = 0.0
        if price and year_high and year_low and year_high > (year_low or 0):
            momentum_raw = (price - year_low) / (year_high - year_low) - 0.5

        rows.append({
            "ticker": ticker,
            "market": market,
            "sector": sector or "Unknown",
            "long_name": name,
            "current_price": price,
            "pe_ttm": pe,
            "pb_ratio": pb,
            "beta": beta or 1.0,
            "gross_profit_margin": gross_margin or 0.0,
            "roe": roe_val or 0.0,
            "piotroski": piotroski or 5,
            "momentum_raw": momentum_raw,
            "accruals_ratio": 0.0,
            "market_cap": mcap,
            "short_interest_pct": None,
            "delivery_pct": None,
            "dividend_yield": (metrics or {}).get("dividendYield"),
            "analyst_target": None,
        })

    if not rows:
        return []

    # Step 4: Compute percentiles cross-sectionally
    import pandas as pd

    df = pd.DataFrame(rows)

    # Quality: rank average of gross_margin, piotroski, accruals
    for col, fill, invert in [
        ("gross_profit_margin", 0, False),
        ("piotroski", 5, False),
        ("accruals_ratio", 0, True),
    ]:
        vals = df[col].fillna(fill).rank(pct=True)
        if invert:
            vals = 1.0 - vals
        df[f"{col}_rank"] = vals

    df["quality_percentile"] = (
        df["gross_profit_margin_rank"] * 0.34
        + df["piotroski_rank"] * 0.33
        + df["accruals_ratio_rank"] * 0.33
    )

    # Momentum
    df["momentum_percentile"] = df["momentum_raw"].rank(pct=True)

    # Value: 1 - P/E rank, 1 - P/B rank
    pe_med = df["pe_ttm"].median()
    pb_med = df["pb_ratio"].median()
    if pd.isna(pe_med):
        pe_med = 20.0  # market average fallback
    if pd.isna(pb_med):
        pb_med = 3.0
    pe_rank = 1.0 - df["pe_ttm"].fillna(pe_med).rank(pct=True)
    pb_rank = 1.0 - df["pb_ratio"].fillna(pb_med).rank(pct=True)
    df["value_percentile"] = pe_rank * 0.5 + pb_rank * 0.5

    # Low vol: approximate realized_vol from beta
    df["realized_vol_1y"] = df["beta"].fillna(1.0) * 0.20
    df["low_vol_percentile"] = 1.0 - df["realized_vol_1y"].rank(pct=True)

    # Market-specific factor — neutral default
    df["short_interest_percentile"] = 0.5
    df["delivery_percentile"] = 0.5
    df["insider_percentile"] = 0.5

    # Step 5: Composite score (equal-weighted 5 factors)
    factor_cols = [
        "quality_percentile", "momentum_percentile", "value_percentile",
        "low_vol_percentile", "short_interest_percentile",
    ]
    w = 1.0 / len(factor_cols)
    df["composite_score"] = sum(df[c] * w for c in factor_cols)

    # Step 6: Edge detection + Kelly sizing
    threshold = strat["min_edge_score"]
    kelly_frac = strat["kelly_fraction"]
    max_bet = strat["max_bet"]

    signals: list[dict[str, Any]] = []
    for _, row in df.sort_values("composite_score", ascending=False).iterrows():
        score = float(row["composite_score"])
        edge = compute_edge(score, threshold)
        if edge <= 0:
            continue

        sizing = size_position_kelly(
            edge=edge,
            bankroll=bankroll,
            kelly_fraction=kelly_frac,
            max_bet=max_bet,
        )
        if sizing.bet <= 0:
            continue

        signals.append({
            "ticker": row["ticker"],
            "market": market,
            "sector": row.get("sector", ""),
            "composite_score": round(score, 4),
            "edge": round(edge, 4),
            "direction": "bullish",
            "bet": sizing.bet,
            "capped": sizing.capped,
            "current_price": row.get("current_price"),
            "pe_ttm": row.get("pe_ttm"),
            "analyst_target": row.get("analyst_target"),
            "market_cap": row.get("market_cap"),
            "strategy": strat["id"],
            "kelly_fraction": kelly_frac,
        })

    return signals


@router.get("/strategies")
def get_strategies() -> dict:
    return {"strategies": TRADE_STRATEGIES}


@router.get("/signals")
def get_signals(
    market: str = "US",
    strategy_id: str = "momentum_breakout",
    bankroll: float = 10000.0,
    n: int = 50,
) -> dict:
    """Generate trade signals from score_cache with risk sizing.

    Uses cached scores (no live data fetch) for sub-100ms response.
    Falls back to live SignalEngine.compute() when cache is stale.
    """
    strat = next((s for s in TRADE_STRATEGIES if s["id"] == strategy_id), TRADE_STRATEGIES[0])

    rows = score_cache.read_top(market, n=n, max_age_seconds=86400)
    signals: list[dict[str, Any]] = []
    live = False

    if rows:
        signals = _rows_to_signals(rows, bankroll, strat)
    else:
        # Live fallback: compute scores from FMP in real-time
        tickers = UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"])
        signals = _compute_live_signals(market, tickers, n, strat, bankroll)
        live = True

    # Check daily drawdown with real PnL from signal_log
    from nq_signals.risk import compute_daily_drawdown
    todays_pnl = _get_todays_pnl_from_log(market)
    daily_limit = _daily_loss_limit_for_strategy(strategy_id)
    drawdown = compute_daily_drawdown(
        [todays_pnl] if todays_pnl != 0 else [],
        daily_loss_limit=daily_limit,
    )

    return {
        "signals": signals,
        "strategy": strat,
        "n_signals": len(signals),
        "bankroll": bankroll,
        "live": live,
        "drawdown": {
            "total_pnl_today": drawdown.total_pnl_today,
            "limit_breached": drawdown.limit_breached,
            "warning_level": drawdown.warning_level,
        },
    }


@router.get("/calibration")
def get_calibration(
    lookback_days: int = 90,
    market: str = "US",
) -> dict:
    """Return accuracy metrics from resolved signal log."""
    from nq_signals.calibration import CalibrationTracker

    tracker = CalibrationTracker()
    report = tracker.get_accuracy(lookback_days=lookback_days, market=market)
    return {
        "hit_rate": report.hit_rate,
        "avg_pnl": report.avg_pnl,
        "total_pnl": report.total_pnl,
        "sharpe": report.sharpe,
        "profit_factor": report.profit_factor,
        "n_trades": report.n_trades,
        "n_winners": report.n_winners,
        "n_losers": report.n_losers,
        "lookback_days": report.lookback_days,
    }


@router.get("/risk-profile")
def get_risk_profile(profile: str = "balanced") -> dict:
    """Return risk parameters for a given risk profile."""
    from nq_signals.risk import kelly_fraction_from_profile

    fraction = kelly_fraction_from_profile(profile)

    profiles = {
        "conservative": {
            "kelly_fraction": 0.15,
            "daily_loss_limit": 50.0,
            "max_bet": 3000.0,
            "max_positions": 12,
            "description": "Lower risk, wider diversification, smaller bets",
        },
        "balanced": {
            "kelly_fraction": 0.25,
            "daily_loss_limit": 100.0,
            "max_bet": 5000.0,
            "max_positions": 10,
            "description": "Standard quarter-Kelly with moderate risk controls",
        },
        "aggressive": {
            "kelly_fraction": 0.40,
            "daily_loss_limit": 200.0,
            "max_bet": 7500.0,
            "max_positions": 8,
            "description": "Higher risk tolerance, larger concentrated bets",
        },
    }

    return {
        "profile": profile,
        "kelly_fraction": fraction,
        **profiles.get(profile, profiles["balanced"]),
    }


@router.post("/log-signal")
def log_signal(body: dict) -> dict:
    """Log a signal for calibration tracking.

    Body: {ticker, market, composite_score, edge, direction, entry_price, bet, strategy}
    """
    from nq_signals.calibration import CalibrationTracker, SignalRecord
    from datetime import datetime, timezone

    tracker = CalibrationTracker()
    record = SignalRecord(
        ticker=body.get("ticker", ""),
        market=body.get("market", "US"),
        signal_date=body.get("signal_date", datetime.now(timezone.utc).isoformat()),
        composite_score=float(body.get("composite_score", 0)),
        edge=float(body.get("edge", 0)),
        direction=body.get("direction", "bullish"),
        entry_price=float(body.get("entry_price", 0)),
        bet=float(body.get("bet", 0)),
        strategy=body.get("strategy", "default"),
    )
    result = tracker.log_signal(record)
    if result:
        return {"status": "logged", "signal_id": result.signal_id}
    return {"status": "error", "detail": "Failed to log signal"}


@router.post("/resolve")
def resolve_signal(body: dict) -> dict:
    """Resolve a logged signal with exit price and PnL.

    Body: {signal_id, exit_price, pnl}
    """
    from nq_signals.calibration import CalibrationTracker

    tracker = CalibrationTracker()
    ok = tracker.resolve_signal(
        signal_id=body.get("signal_id", ""),
        exit_price=float(body.get("exit_price", 0)),
        pnl=float(body.get("pnl", 0)),
    )
    if ok:
        return {"status": "resolved"}
    return {"status": "error", "detail": "Failed to resolve signal"}
