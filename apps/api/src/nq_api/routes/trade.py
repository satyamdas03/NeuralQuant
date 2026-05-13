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
from typing import Any

from fastapi import APIRouter

from nq_api.cache import score_cache

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
        "min_edge_score": 0.70,
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
    if not rows:
        return {
            "signals": [],
            "strategy": strat,
            "n_signals": 0,
            "bankroll": bankroll,
            "message": "Score cache empty — signals appear after nightly score calculation runs."
        }

    signals = _rows_to_signals(rows, bankroll, strat)

    # Check daily drawdown
    from nq_signals.risk import compute_daily_drawdown
    drawdown = compute_daily_drawdown([], daily_loss_limit=100.0)

    return {
        "signals": signals,
        "strategy": strat,
        "n_signals": len(signals),
        "bankroll": bankroll,
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
