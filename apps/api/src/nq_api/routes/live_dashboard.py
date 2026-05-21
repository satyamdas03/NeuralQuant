"""Live trading dashboard — read-only aggregated data from Supabase.

Endpoints:
  GET /live/dashboard — signal summary, positions, PnL chart, calibration curves

All read-only, sub-200ms. No API calls — Supabase queries only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["live dashboard"])


@router.get("/dashboard")
def get_dashboard(
    market: str = "US",
    lookback_days: int = 30,
    user: User = Depends(get_current_user),
) -> dict:
    """Aggregated dashboard data for live trading monitor."""
    from nq_api.cache.score_cache import _supabase_rest

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=lookback_days)).isoformat()

    # ── Signal summary ──────────────────────────────────────────────────
    todays_signals = _supabase_rest(
        "signal_log",
        method="GET",
        query={
            "select": "*",
            "market": f"eq.{market}",
            "signal_date": f"gte.{today}T00:00:00Z",
            "order": "signal_date.desc",
            "limit": "50",
        },
    )
    if not isinstance(todays_signals, list):
        todays_signals = []

    resolved_today = [s for s in todays_signals if s.get("resolved")]
    unresolved_today = [s for s in todays_signals if not s.get("resolved")]

    # ── PnL history ────────────────────────────────────────────────────
    resolved_history = _supabase_rest(
        "signal_log",
        method="GET",
        query={
            "select": "pnl,resolution_date,strategy",
            "market": f"eq.{market}",
            "resolved": "eq.true",
            "resolution_date": f"gte.{since}",
            "order": "resolution_date.asc",
            "limit": "500",
        },
    )
    if not isinstance(resolved_history, list):
        resolved_history = []

    # Daily PnL aggregation
    daily_pnl: dict[str, float] = {}
    for r in resolved_history:
        date_key = (r.get("resolution_date") or "")[:10]
        pnl_val = float(r.get("pnl", 0) or 0)
        daily_pnl[date_key] = daily_pnl.get(date_key, 0.0) + pnl_val

    pnl_series = [{"date": d, "pnl": round(v, 2)} for d, v in sorted(daily_pnl.items())]
    cumulative = 0.0
    equity_curve = []
    for entry in pnl_series:
        cumulative += entry["pnl"]
        equity_curve.append({"date": entry["date"], "equity": round(cumulative, 2)})

    total_pnl = round(sum(r.get("pnl", 0) or 0 for r in resolved_history), 2)
    today_pnl = round(sum(
        float(r.get("pnl", 0) or 0) for r in resolved_today
    ), 2)

    # ── Calibration metrics ─────────────────────────────────────────────
    winners = [r for r in resolved_history if (r.get("pnl") or 0) > 0]
    losers = [r for r in resolved_history if (r.get("pnl") or 0) < 0]
    n_trades = len(resolved_history)
    n_winners = len(winners)
    n_losers = len(losers)
    hit_rate = round(n_winners / n_trades, 4) if n_trades > 0 else 0.0

    gross_gain = sum(float(r.get("pnl", 0) or 0) for r in winners)
    gross_loss = abs(sum(float(r.get("pnl", 0) or 0) for r in losers))
    profit_factor = round(gross_gain / gross_loss, 2) if gross_loss > 0 else float("inf") if gross_gain > 0 else 0.0

    avg_win = round(gross_gain / n_winners, 2) if n_winners > 0 else 0.0
    avg_loss = round(gross_loss / n_losers, 2) if n_losers > 0 else 0.0

    # ── Strategy breakdown ──────────────────────────────────────────────
    strat_pnl: dict[str, dict] = {}
    for r in resolved_history:
        s = r.get("strategy", "unknown")
        if s not in strat_pnl:
            strat_pnl[s] = {"trades": 0, "wins": 0, "pnl": 0.0}
        strat_pnl[s]["trades"] += 1
        pnl = float(r.get("pnl", 0) or 0)
        strat_pnl[s]["pnl"] += pnl
        if pnl > 0:
            strat_pnl[s]["wins"] += 1

    strategy_breakdown = [
        {
            "strategy": name,
            "trades": d["trades"],
            "pnl": round(d["pnl"], 2),
            "hit_rate": round(d["wins"] / d["trades"], 3) if d["trades"] > 0 else 0.0,
        }
        for name, d in sorted(strat_pnl.items(), key=lambda x: x[1]["pnl"], reverse=True)
    ]

    # ── Source calibration (from news_classifications) ──────────────────
    source_cal = _get_source_calibration(market, lookback_days)

    return {
        "period": {"from": since[:10], "to": today, "days": lookback_days},
        "signal_summary": {
            "total_today": len(todays_signals),
            "resolved_today": len(resolved_today),
            "open_today": len(unresolved_today),
            "total_pnl_today": today_pnl,
        },
        "performance": {
            "total_trades": n_trades,
            "winners": n_winners,
            "losers": n_losers,
            "hit_rate": hit_rate,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        },
        "pnl_series": pnl_series,
        "equity_curve": equity_curve,
        "strategy_breakdown": strategy_breakdown,
        "source_calibration": source_cal,
    }


def _get_source_calibration(market: str, lookback_days: int) -> list[dict]:
    """Hit rate by news source from Supabase."""
    from nq_api.cache.score_cache import _supabase_rest
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    rows = _supabase_rest(
        "news_classifications",
        method="GET",
        query={
            "select": "source,direction,confidence",
            "classified_at": f"gte.{since}",
            "limit": "500",
        },
    )
    if not isinstance(rows, list) or not rows:
        return []

    source_counts: dict[str, dict] = {}
    for r in rows:
        src = r.get("source", "unknown")
        if src not in source_counts:
            source_counts[src] = {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0, "high_conf": 0}
        source_counts[src]["total"] += 1
        direction = r.get("direction", "neutral")
        if direction in ("bullish", "bearish", "neutral"):
            source_counts[src][direction] += 1
        if (r.get("confidence") or 0) >= 0.7:
            source_counts[src]["high_conf"] += 1

    return [
        {
            "source": name,
            "total": d["total"],
            "bullish_pct": round(d["bullish"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
            "bearish_pct": round(d["bearish"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
            "neutral_pct": round(d["neutral"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
            "high_confidence_pct": round(d["high_conf"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for name, d in sorted(source_counts.items(), key=lambda x: x[1]["total"], reverse=True)
    ]
