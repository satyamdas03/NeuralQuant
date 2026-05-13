"""Live trading pipeline — news classification → signal → order execution.

Endpoints:
  POST /live/classify        — Run news classification pipeline
  POST /live/execute         — Full pipeline: classify → edge → size → safety → execute
  GET  /live/status          — Current trading state (positions, PnL, safety gate)
  GET  /live/pipeline-health — Dependency health checks
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from nq_api.cache import score_cache
from nq_api.universe import UNIVERSE_BY_MARKET

log = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["live trading"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_todays_pnl(market: str = "US") -> float:
    """Sum today's resolved PnL from signal_log. Returns negative for losses."""
    from nq_api.cache.score_cache import _supabase_rest
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


def _get_signals_from_scores(
    tickers: list[str],
    market: str,
    strategy_id: str,
    bankroll: float,
    n: int,
) -> list[dict[str, Any]]:
    """Get trade signals — prefers cache, falls back to live FMP computation."""
    from .trade import TRADE_STRATEGIES, _rows_to_signals, _compute_live_signals

    strat = next((s for s in TRADE_STRATEGIES if s["id"] == strategy_id), TRADE_STRATEGIES[0])
    rows = score_cache.read_top(market, n=n, max_age_seconds=86400)

    if rows:
        return _rows_to_signals(rows, bankroll, strat)
    else:
        return _compute_live_signals(market, tickers, n, strat, bankroll)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/classify")
async def classify_news(
    market: str = "US",
    top_n: int = 10,
) -> dict:
    """Run news classification pipeline for top-scored tickers.

    Fetches headlines from Finnhub + StockTwits, classifies via Claude,
    stores to Supabase news_classifications table.
    """
    tickers = UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"])
    if not tickers:
        return {"status": "error", "error": f"No tickers for market={market}"}

    # Use top-scored tickers from cache to focus on actionable stocks
    rows = score_cache.read_top(market, n=min(top_n, 30), max_age_seconds=86400)
    if rows:
        target_tickers = [r["ticker"] for r in rows]
    else:
        target_tickers = tickers[:top_n]

    try:
        from nq_data.news_pipeline import run_classification_pipeline
        result = await run_classification_pipeline(target_tickers, market)
        result["tickers_processed"] = len(target_tickers)
        return result
    except Exception as exc:
        log.exception("Classification pipeline failed")
        return {"status": "error", "error": str(exc)}


@router.post("/execute")
async def execute_pipeline(
    market: str = "US",
    strategy_id: str = "momentum_breakout",
    bankroll: float = 10000.0,
    n: int = 5,
    live: bool = False,
) -> dict:
    """Run full signal-to-order pipeline.

    1. Get trade signals from score_cache (or live FMP fallback)
    2. Run news classification for context
    3. Apply safety gate to each signal
    4. In dry-run mode: simulate + log to signal_log
    5. In live mode: place real orders via Alpaca

    `live=True` only works when TRADE_ENABLED=true AND DRY_RUN=false in env.
    """
    from nq_signals.safety import load_safety_gate, check_order
    from nq_signals.calibration import CalibrationTracker, SignalRecord

    gate = load_safety_gate()
    tickers = UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"])

    # Get signals
    signals = _get_signals_from_scores(tickers, market, strategy_id, bankroll, n)

    # Run classification concurrently for context
    if signals:
        top_tickers = [s["ticker"] for s in signals[:5]]
        classify_task = asyncio.create_task(
            asyncio.to_thread(lambda: None)  # placeholder, replaced below
        )
        try:
            from nq_data.news_pipeline import run_classification_pipeline
            classify_task = asyncio.create_task(run_classification_pipeline(top_tickers, market))
        except Exception:
            pass

    # Safety gate + execution
    daily_pnl = _get_todays_pnl(market)
    active_positions = _count_broker_positions()
    tracker = CalibrationTracker()

    results = []
    orders_placed = 0
    orders_blocked = 0
    orders_simulated = 0

    for signal in signals:
        bet = signal.get("bet", 0)
        if bet is None:
            bet = 0

        check = check_order(
            bet=float(bet),
            gate=gate,
            daily_pnl=daily_pnl,
            current_positions=active_positions + orders_placed,
        )

        result_entry = {
            "ticker": signal["ticker"],
            "score": signal.get("composite_score"),
            "edge": signal.get("edge"),
            "bet": bet,
            "direction": signal.get("direction", "bullish"),
            "safety": {
                "passed": check.passed,
                "reason": check.reason,
                "dry_run_note": check.dry_run_note,
            },
        }

        if not check.passed:
            orders_blocked += 1
            results.append(result_entry)
            continue

        if check.dry_run_note:
            # Dry run: simulate order, log to signal_log
            orders_simulated += 1
            record = SignalRecord(
                ticker=signal["ticker"],
                market=market,
                composite_score=float(signal.get("composite_score", 0) or 0),
                edge=float(signal.get("edge", 0) or 0),
                direction=signal.get("direction", "bullish"),
                entry_price=float(signal.get("current_price", 0) or 0),
                bet=float(bet),
                strategy=strategy_id,
            )
            tracker.log_signal(record)
            result_entry["execution"] = "simulated"
            result_entry["signal_id"] = record.signal_id
            results.append(result_entry)
        else:
            # Live mode: place real order
            try:
                order_result = await _place_alpaca_order(
                    symbol=signal["ticker"],
                    qty=_bet_to_shares(float(bet), float(signal.get("current_price", 0) or 0)),
                    side="buy",
                )
                orders_placed += 1
                record = SignalRecord(
                    ticker=signal["ticker"],
                    market=market,
                    composite_score=float(signal.get("composite_score", 0) or 0),
                    edge=float(signal.get("edge", 0) or 0),
                    direction="bullish",
                    entry_price=float(signal.get("current_price", 0) or 0),
                    bet=float(bet),
                    strategy=strategy_id,
                )
                tracker.log_signal(record)
                result_entry["execution"] = "live"
                result_entry["order"] = order_result
                result_entry["signal_id"] = record.signal_id
            except Exception as exc:
                log.exception("Order execution failed for %s", signal["ticker"])
                result_entry["execution"] = "failed"
                result_entry["error"] = str(exc)
            results.append(result_entry)

    # Collect classification results
    classification = None
    try:
        if classify_task:
            classification = await asyncio.wait_for(classify_task, timeout=15.0)
    except (asyncio.TimeoutError, Exception):
        pass

    return {
        "status": "ok",
        "mode": "dry_run" if gate.dry_run else "live",
        "trade_enabled": gate.trade_enabled,
        "daily_pnl": round(daily_pnl, 2),
        "orders_placed": orders_placed,
        "orders_simulated": orders_simulated,
        "orders_blocked": orders_blocked,
        "results": results,
        "classification": classification,
        "safety_gate": {
            "dry_run": gate.dry_run,
            "trade_enabled": gate.trade_enabled,
            "daily_loss_limit": gate.daily_loss_limit,
            "max_bet": gate.max_bet,
            "max_positions": gate.max_positions,
        },
    }


@router.get("/status")
def get_live_status(market: str = "US") -> dict:
    """Current trading state: signals, positions, PnL, safety gate."""
    from nq_signals.safety import load_safety_gate

    gate = load_safety_gate()
    daily_pnl = _get_todays_pnl(market)
    positions = _get_broker_positions_list()
    active_count = len(positions) if positions else 0

    # Get today's signals from signal_log
    from nq_api.cache.score_cache import _supabase_rest
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todays_signals = _supabase_rest(
        "signal_log",
        method="GET",
        query={
            "select": "*",
            "market": f"eq.{market}",
            "signal_date": f"gte.{today}T00:00:00Z",
            "order": "signal_date.desc",
            "limit": "20",
        },
    )

    return {
        "mode": "dry_run" if gate.dry_run else "live",
        "trade_enabled": gate.trade_enabled,
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss_limit": gate.daily_loss_limit,
        "pnl_remaining": round(gate.daily_loss_limit + daily_pnl, 2),
        "limit_breached": daily_pnl <= -gate.daily_loss_limit,
        "active_positions": active_count,
        "max_positions": gate.max_positions,
        "max_bet": gate.max_bet,
        "signals_today": len(todays_signals) if isinstance(todays_signals, list) else 0,
        "recent_signals": todays_signals if isinstance(todays_signals, list) else [],
    }


@router.get("/pipeline-health")
def get_pipeline_health() -> dict:
    """Check health of all pipeline dependencies."""
    checks = {}

    # Anthropic
    try:
        import anthropic
        key = __import__('os').environ.get("ANTHROPIC_API_KEY", "")
        checks["anthropic"] = {"ok": bool(key), "detail": "key set" if key else "no key"}
    except ImportError:
        checks["anthropic"] = {"ok": False, "detail": "library not installed"}

    # FMP
    try:
        from nq_data.fmp import get_fmp_client
        client = get_fmp_client()
        checks["fmp"] = {"ok": client._enabled, "detail": "key set" if client._enabled else "no key"}
    except Exception as exc:
        checks["fmp"] = {"ok": False, "detail": str(exc)}

    # Alpaca
    try:
        from nq_data.broker import get_alpaca_config_from_env, get_account_info
        config = get_alpaca_config_from_env()
        if config:
            info = get_account_info(config)
            checks["alpaca"] = {
                "ok": True,
                "paper": config.paper,
                "account_status": info.get("status", "unknown") if info else "unreachable",
            }
        else:
            checks["alpaca"] = {"ok": False, "detail": "not configured"}
    except Exception as exc:
        checks["alpaca"] = {"ok": False, "detail": str(exc)}

    # Supabase
    try:
        from nq_api.cache.score_cache import _supabase_rest
        data = _supabase_rest("score_cache", method="GET", query={"select": "ticker", "limit": "1"})
        checks["supabase"] = {"ok": data is not None, "detail": "connected" if data is not None else "unreachable"}
    except Exception as exc:
        checks["supabase"] = {"ok": False, "detail": str(exc)}

    # OpenBB (optional)
    openbb_url = __import__('os').environ.get("OPENBB_API_URL", "")
    if openbb_url:
        try:
            import httpx
            r = httpx.Client(timeout=5.0).get(f"{openbb_url}/docs")
            checks["openbb"] = {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code}"}
        except Exception as exc:
            checks["openbb"] = {"ok": False, "detail": str(exc)}
    else:
        checks["openbb"] = {"ok": False, "detail": "not configured"}

    all_ok = all(c.get("ok", False) for c in checks.values())
    # OpenBB is optional
    critical = {k: v for k, v in checks.items() if k != "openbb"}
    critical_ok = all(c.get("ok", False) for c in critical.values())

    return {
        "overall": "healthy" if critical_ok else "degraded",
        "trading_ready": all_ok,
        "checks": checks,
    }


# ── Broker helpers ──────────────────────────────────────────────────────────

def _count_broker_positions() -> int:
    """Get count of current Alpaca positions."""
    try:
        positions = _get_broker_positions_list()
        return len(positions) if positions else 0
    except Exception:
        return 0


def _get_broker_positions_list() -> list[dict] | None:
    """Get list of current Alpaca positions."""
    try:
        from nq_data.broker import get_alpaca_config_from_env, get_positions
        config = get_alpaca_config_from_env()
        if config is None:
            return None
        return get_positions(config)
    except Exception:
        return None


async def _place_alpaca_order(symbol: str, qty: float, side: str = "buy") -> dict:
    """Place an order via Alpaca. Wraps synchronous place_market_order in async thread."""
    try:
        from nq_data.broker import get_alpaca_config_from_env, place_market_order
        config = get_alpaca_config_from_env()
        if config is None:
            raise RuntimeError("Alpaca not configured")
        result = await asyncio.to_thread(
            place_market_order, config, symbol, int(qty), side, "market", "day"
        )
        return {"id": result.get("id", "") if result else "", "symbol": symbol, "qty": qty, "side": side}
    except Exception as exc:
        log.exception("Alpaca order failed")
        raise


def _bet_to_shares(bet: float, price: float) -> int:
    """Convert dollar bet amount to integer share count."""
    if not price or price <= 0:
        return 1
    shares = int(bet / price)
    return max(1, shares)
