"""Persistent trading daemon — Polymarket Pipeline V2 pattern.

Async event loop: news → classify → edge → Kelly size → safety gate → execute.
Runs as Render worker service. Default dry-run. --live flag for real trading.

Usage:
  python trade_daemon.py              # dry-run mode
  python trade_daemon.py --live       # live trading (requires TRADE_ENABLED=true)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / "apps" / "api" / ".env", override=True)

import httpx
import pandas as pd
from nq_signals.risk import compute_edge, size_position_kelly, compute_daily_drawdown
from nq_signals.safety import load_safety_gate, check_order, SafetyGate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("trade_daemon")


# ── Config ────────────────────────────────────────────────────────────────────

class DaemonConfig:
    def __init__(self, args):
        self.live = args.live
        self.market = os.environ.get("TRADE_DAEMON_MARKET", "US")
        self.strategy_id = os.environ.get("TRADE_DAEMON_STRATEGY", "value_play")
        self.bankroll = float(os.environ.get("TRADE_DAEMON_BANKROLL", "10000.0"))
        self.scan_interval = int(os.environ.get("TRADE_DAEMON_SCAN_INTERVAL_MINUTES", "15"))
        self.top_n = int(os.environ.get("TRADE_DAEMON_TOP_N", "10"))
        self.max_signals_per_day = int(os.environ.get("TRADE_DAEMON_MAX_SIGNALS_PER_DAY", "20"))

    def __repr__(self):
        return (
            f"DaemonConfig(live={self.live}, market={self.market}, "
            f"strategy={self.strategy_id}, bankroll={self.bankroll}, "
            f"scan_interval={self.scan_interval}m, top_n={self.top_n}, "
            f"max_signals_per_day={self.max_signals_per_day})"
        )


# ── Strategy presets (mirrors trade.py TRADE_STRATEGIES) ──────────────────────

STRATEGIES = {
    "momentum_breakout": {"kelly_fraction": 0.40, "min_edge_score": 0.62, "max_positions": 8, "max_bet": 5000.0},
    "value_play": {"kelly_fraction": 0.25, "min_edge_score": 0.60, "max_positions": 10, "max_bet": 5000.0},
    "dividend_income": {"kelly_fraction": 0.15, "min_edge_score": 0.65, "max_positions": 12, "max_bet": 3000.0},
    "quality_compound": {"kelly_fraction": 0.25, "min_edge_score": 0.65, "max_positions": 10, "max_bet": 5000.0},
    "contrarian_bet": {"kelly_fraction": 0.40, "min_edge_score": 0.75, "max_positions": 5, "max_bet": 2500.0},
    "macro_tailwind": {"kelly_fraction": 0.25, "min_edge_score": 0.60, "max_positions": 10, "max_bet": 5000.0},
}


# ── Market hours ──────────────────────────────────────────────────────────────

def _get_alpaca_clock():
    """Check if US market is open via Alpaca clock API. Returns (is_open, next_open, next_close)."""
    try:
        from nq_data.broker import get_alpaca_config_from_env, get_alpaca_client
        config = get_alpaca_config_from_env()
        if config is None:
            return False, None, None
        client = get_alpaca_client(config)
        if client is None:
            return False, None, None
        clock = client.get_clock()
        return clock.is_open, clock.next_open, clock.next_close
    except Exception:
        return False, None, None


def _in_market_hours() -> bool:
    """Quick check: are we within US market hours window? (9:30-16:00 ET = 13:30-20:00 UTC)"""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    t = now.hour * 60 + now.minute
    return 13 * 60 + 30 <= t < 20 * 60  # 13:30 to 20:00 UTC


# ── Live signal computation (ported from trade.py _compute_live_signals) ──────

def _compute_live_signals(market: str, tickers: list[str], n: int,
                          strat: dict, bankroll: float) -> list[dict[str, Any]]:
    """Fast live signal computation using FMP parallel data fetch."""
    api_key = os.environ.get("FMP_API_KEY", "")
    base_url = os.environ.get("FMP_BASE_URL", "https://financialmodelingprep.com/stable")
    if not api_key:
        log.warning("FMP_API_KEY not set — cannot compute live signals")
        return []

    top_tickers = tickers[: min(n, 50)]

    # Batch quotes
    from nq_data.fmp import get_fmp_client
    fmp_shared = get_fmp_client()
    batch_quotes = fmp_shared.get_batch_quotes(top_tickers) or {}

    # Per-ticker data in parallel
    def _fetch_one(ticker: str):
        local_client = httpx.Client(timeout=15.0, follow_redirects=True)
        sym = ticker
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
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in top_tickers}
        for future in as_completed(futures, timeout=15):
            try:
                ticker, metrics, scores, profile, quote = future.result()
                ticker_data[ticker] = (metrics, scores, profile, quote)
            except Exception:
                pass

    if not ticker_data:
        log.warning("No ticker data fetched from FMP")
        return []

    # Build rows
    rows: list[dict[str, Any]] = []
    for ticker in top_tickers:
        metrics, scores, profile, quote = ticker_data.get(ticker, (None, None, None, None))
        bq = batch_quotes.get(ticker, {})

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
        year_high = (quote or {}).get("yearHigh")
        year_low = (quote or {}).get("yearLow")
        momentum_raw = 0.0
        if price and year_high and year_low and year_high > (year_low or 0):
            momentum_raw = (price - year_low) / (year_high - year_low) - 0.5

        rows.append({
            "ticker": ticker, "market": market, "sector": sector or "Unknown",
            "long_name": name, "current_price": price, "pe_ttm": pe,
            "pb_ratio": pb, "beta": beta or 1.0,
            "gross_profit_margin": gross_margin or 0.0, "roe": roe_val or 0.0,
            "piotroski": piotroski or 5, "momentum_raw": momentum_raw,
            "accruals_ratio": 0.0, "market_cap": mcap,
            "short_interest_pct": None, "delivery_pct": None,
            "dividend_yield": (metrics or {}).get("dividendYield"),
            "analyst_target": None,
        })

    if not rows:
        return []

    # Percentiles cross-sectionally
    df = pd.DataFrame(rows)
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
    df["momentum_percentile"] = df["momentum_raw"].rank(pct=True)

    pe_med = df["pe_ttm"].median()
    pb_med = df["pb_ratio"].median()
    if pd.isna(pe_med):
        pe_med = 20.0
    if pd.isna(pb_med):
        pb_med = 3.0
    pe_rank = 1.0 - df["pe_ttm"].fillna(pe_med).rank(pct=True)
    pb_rank = 1.0 - df["pb_ratio"].fillna(pb_med).rank(pct=True)
    df["value_percentile"] = pe_rank * 0.5 + pb_rank * 0.5

    df["realized_vol_1y"] = df["beta"].fillna(1.0) * 0.20
    df["low_vol_percentile"] = 1.0 - df["realized_vol_1y"].rank(pct=True)

    df["short_interest_percentile"] = 0.5
    df["delivery_percentile"] = 0.5
    df["insider_percentile"] = 0.5

    factor_cols = [
        "quality_percentile", "momentum_percentile", "value_percentile",
        "low_vol_percentile", "short_interest_percentile",
    ]
    w = 1.0 / len(factor_cols)
    df["composite_score"] = sum(df[c] * w for c in factor_cols)

    threshold = strat["min_edge_score"]
    kelly_frac = strat["kelly_fraction"]
    max_bet = strat["max_bet"]

    signals = []
    for _, row in df.iterrows():
        edge_val = compute_edge(row["composite_score"], threshold)
        if edge_val <= 0:
            continue
        size = size_position_kelly(edge_val, bankroll, kelly_fraction=kelly_frac, max_bet=max_bet)
        if size.bet <= 0:
            continue
        signals.append({
            "ticker": row["ticker"],
            "composite_score": round(row["composite_score"], 4),
            "edge": round(edge_val, 4),
            "direction": "bullish",
            "bet": round(size.bet, 2),
            "current_price": row["current_price"],
            "sector": row["sector"],
            "long_name": row["long_name"],
        })

    signals.sort(key=lambda s: s["edge"], reverse=True)
    return signals


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _supabase_rest(table: str, method: str = "GET", query: dict | None = None,
                   body: dict | None = None) -> Any:
    """Minimal Supabase REST call. Returns parsed JSON or None."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not supabase_key:
        return None
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}",
               "Content-Type": "application/json", "Prefer": "return=representation"}
    try:
        if method == "GET":
            params = {}
            if query:
                params = query
            r = httpx.get(f"{supabase_url}/rest/v1/{table}", headers=headers,
                          params=params, timeout=10.0)
        elif method == "POST":
            r = httpx.post(f"{supabase_url}/rest/v1/{table}", headers=headers,
                           json=body or {}, timeout=10.0)
        elif method == "PATCH":
            # query params for PATCH are filters in the URL
            qs = ""
            if query:
                qs = "?" + "&".join(f"{k}={v}" for k, v in query.items())
            r = httpx.patch(f"{supabase_url}/rest/v1/{table}{qs}", headers=headers,
                            json=body or {}, timeout=10.0)
        else:
            return None
        if r.status_code in (200, 201):
            return r.json() if r.text else []
        return None
    except Exception:
        return None


def _get_todays_pnl(market: str = "US") -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _supabase_rest("signal_log", method="GET", query={
        "select": "pnl", "market": f"eq.{market}",
        "resolved": "eq.true", "resolution_date": f"gte.{today}T00:00:00Z",
    })
    if not isinstance(rows, list):
        return 0.0
    return sum(float(r.get("pnl", 0) or 0) for r in rows)


def _count_todays_signals(market: str = "US") -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _supabase_rest("signal_log", method="GET", query={
        "select": "id", "market": f"eq.{market}",
        "signal_date": f"gte.{today}T00:00:00Z",
    })
    return len(rows) if isinstance(rows, list) else 0


def _get_universe(market: str) -> list[str]:
    try:
        from nq_api.universe import UNIVERSE_BY_MARKET
        return list(UNIVERSE_BY_MARKET.get(market, []))
    except Exception:
        # Hardcoded fallback
        if market == "US":
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
                    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
                    "MRK", "LLY", "CVX", "BAC", "NFLX", "ORCL", "ADBE", "CRM", "AMD",
                    "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC",
                    "WMT", "TGT", "NKE", "MCD", "SBUX", "DIS", "CMCSA", "T", "VZ",
                    "PFE", "AMGN", "GILD", "REGN", "ISRG"]
        return []


# ── Position helpers ──────────────────────────────────────────────────────────

def _get_alpaca_positions() -> list[dict]:
    try:
        from nq_data.broker import get_alpaca_config_from_env, get_positions
        config = get_alpaca_config_from_env()
        if config is None:
            return []
        return get_positions(config) or []
    except Exception:
        return []


# ── 5 Coroutines ─────────────────────────────────────────────────────────────

async def clock(signal_queue: asyncio.Queue, config: DaemonConfig):
    """Tick producer: push a tick into signal_queue every scan_interval during market hours."""
    log.info("Clock coroutine started (interval=%dmin)", config.scan_interval)
    ticks_today = 0
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    while True:
        try:
            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")
            if today_str != day:
                ticks_today = 0
                day = today_str

            in_hours = _in_market_hours()

            if in_hours:
                # Check queue backpressure — skip if executor is behind
                if signal_queue.qsize() < signal_queue.maxsize * 0.8:
                    await signal_queue.put({"type": "tick", "time": now.isoformat()})
                    ticks_today += 1
                    log.info("Tick #%d — signal_queue size=%d", ticks_today, signal_queue.qsize())
                else:
                    log.warning("Signal queue near full (%d/%d) — skipping tick",
                                signal_queue.qsize(), signal_queue.maxsize)
                await asyncio.sleep(config.scan_interval * 60)
            else:
                # Outside market hours — sleep 5 minutes, recheck
                log.info("Outside market hours — sleeping 5min")
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Clock error — retrying in 60s")
            await asyncio.sleep(60)


async def scanner(signal_queue: asyncio.Queue, execute_queue: asyncio.Queue, config: DaemonConfig):
    """Signal producer: consume ticks, run FMP compute, enqueue executable signals."""
    log.info("Scanner coroutine started")
    strat = STRATEGIES.get(config.strategy_id, STRATEGIES["momentum_breakout"])

    while True:
        try:
            tick = await signal_queue.get()
            tick_time = tick.get("time", "?")
            log.info("Scanner woke: tick=%s", tick_time[:19])

            universe = _get_universe(config.market)
            if not universe:
                log.warning("Empty universe for market=%s", config.market)
                continue

            # Check daily signal cap
            n_today = _count_todays_signals(config.market)
            if n_today >= config.max_signals_per_day:
                log.warning("Daily signal cap reached (%d/%d) — skipping scan",
                            n_today, config.max_signals_per_day)
                continue

            remaining = config.max_signals_per_day - n_today
            top_n = min(config.top_n, remaining)

            # Compute live signals
            signals = await asyncio.to_thread(
                _compute_live_signals, config.market, universe, top_n * 3, strat, config.bankroll
            )

            if not signals:
                log.info("No actionable signals found this scan")
                continue

            # Enqueue top signals
            for sig in signals[:top_n]:
                await execute_queue.put({
                    "type": "signal",
                    "ticker": sig["ticker"],
                    "composite_score": sig["composite_score"],
                    "edge": sig["edge"],
                    "direction": sig["direction"],
                    "bet": sig["bet"],
                    "current_price": sig["current_price"],
                    "strategy": config.strategy_id,
                })

            log.info("Scanner enqueued %d signals (edge range: %.3f - %.3f)",
                     min(len(signals), top_n),
                     signals[0]["edge"],
                     signals[min(len(signals), top_n) - 1]["edge"] if len(signals) > 0 else 0)

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scanner error — continuing")


async def executor(execute_queue: asyncio.Queue, config: DaemonConfig):
    """Order placer: consume signals, apply safety gate, dry-run/log or live/execute."""
    log.info("Executor coroutine started (live=%s)", config.live)
    from nq_signals.calibration import CalibrationTracker, SignalRecord

    tracker = CalibrationTracker()

    while True:
        try:
            signal_data = await execute_queue.get()
            ticker = signal_data["ticker"]
            bet = signal_data["bet"]
            edge = signal_data["edge"]
            direction = signal_data["direction"]
            price = signal_data.get("current_price") or 0
            strategy = signal_data.get("strategy", config.strategy_id)

            log.info("Executing: %s %s bet=$%.2f edge=%.3f price=%.2f",
                     direction.upper(), ticker, bet, edge, price)

            # Safety gate
            gate = load_safety_gate()
            daily_pnl = _get_todays_pnl(config.market)
            positions = _get_alpaca_positions()

            # Override max_bet and max_positions from strategy
            strat = STRATEGIES.get(config.strategy_id, STRATEGIES["momentum_breakout"])
            gate_override = SafetyGate(
                dry_run=gate.dry_run,
                trade_enabled=gate.trade_enabled,
                daily_loss_limit=gate.daily_loss_limit,
                max_bet=strat["max_bet"],
                max_positions=strat["max_positions"],
            )

            check = check_order(bet, gate_override, daily_pnl, len(positions))

            if not check.passed:
                log.warning("Signal blocked: %s — %s", ticker, check.reason)
                continue

            # Log signal record
            record = SignalRecord(
                ticker=ticker,
                market=config.market,
                signal_date=datetime.now(timezone.utc).isoformat(),
                composite_score=signal_data["composite_score"],
                edge=edge,
                direction=direction,
                entry_price=price,
                bet=bet,
                strategy=strategy,
            )
            logged = tracker.log_signal(record)

            signal_id = logged.signal_id if logged else "?"

            if gate.dry_run or not config.live:
                log.info("DRY RUN: %s %s bet=$%.2f @ $%.2f — signal_id=%s",
                         direction.upper(), ticker, bet, price, signal_id)
            else:
                # Live execution
                from nq_data.broker import get_alpaca_config_from_env, place_market_order
                broker_config = get_alpaca_config_from_env()
                if broker_config is None:
                    log.error("Alpaca not configured — cannot execute live order")
                    continue

                qty = max(1, int(bet / price)) if price > 0 else 1
                log.warning("LIVE ORDER: %s %d %s @ market", direction.upper(), qty, ticker)
                try:
                    result = await asyncio.to_thread(
                        place_market_order, broker_config, ticker.upper(), qty, direction, "market", "day"
                    )
                    order_id = result.get("id", "?") if result else "?"
                    log.warning("LIVE FILLED: %s order_id=%s signal_id=%s", ticker, order_id, signal_id)
                except Exception as exc:
                    log.exception("Live order failed: %s — %s", ticker, exc)

            log.info("Executor done: %s signal_id=%s pnl_today=$%.2f positions=%d",
                     ticker, signal_id, daily_pnl, len(positions))

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Executor error — continuing")


async def resolver(config: DaemonConfig):
    """Auto-resolve: match unresolved signal_log entries against current Alpaca positions.
    Missing positions → resolve with estimated PnL from fill history or last price."""
    log.info("Resolver coroutine started")
    from nq_signals.calibration import CalibrationTracker

    tracker = CalibrationTracker()

    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes

            unresolved = tracker.get_recent_unresolved(market=config.market, limit=50)
            if not unresolved:
                continue

            positions = _get_alpaca_positions()
            pos_symbols = {p.get("symbol", "").upper() for p in positions}

            orphaned = [u for u in unresolved
                        if u.get("ticker", "").upper() not in pos_symbols]

            if not orphaned:
                continue

            log.info("Resolver: %d unresolved in signal_log, %d orphaned (not in Alpaca positions)",
                     len(unresolved), len(orphaned))

            for sig in orphaned:
                sig_id = sig.get("id") or sig.get("signal_id", "")
                entry_price = float(sig.get("entry_price", 0) or 0)
                ticker = sig.get("ticker", "")

                if not entry_price or not sig_id:
                    continue

                # Try to get exit price from Alpaca fill history
                exit_price = 0.0
                try:
                    from nq_data.broker import get_alpaca_config_from_env, get_alpaca_client
                    broker_cfg = get_alpaca_config_from_env()
                    client = get_alpaca_client(broker_cfg) if broker_cfg else None
                    if client:
                        activities = client.get_account_activities(
                            activity_types=["FILL"],
                            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            direction="desc",
                        )
                        # Find fill for this ticker
                        for fill in activities:
                            if hasattr(fill, 'symbol') and fill.symbol.upper() == ticker.upper():
                                if hasattr(fill, 'price'):
                                    exit_price = float(fill.price)
                                    break
                except Exception:
                    pass

                if exit_price <= 0 and entry_price > 0:
                    # Approximate: use a 1% slippage estimate
                    exit_price = entry_price * 0.99

                bet = float(sig.get("bet", 0) or 0)
                qty = int(bet / entry_price) if entry_price > 0 else 1
                pnl = round((exit_price - entry_price) * qty, 2)

                success = tracker.resolve_signal(sig_id, exit_price, pnl)
                if success:
                    log.info("Resolved: %s signal_id=%s PnL=$%.2f (entry=%.2f exit=%.2f)",
                             ticker, sig_id, pnl, entry_price, exit_price)

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Resolver error — continuing")


async def monitor(config: DaemonConfig):
    """Health monitoring: log daemon status every 5 minutes."""
    log.info("Monitor coroutine started")

    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes

            gate = load_safety_gate()
            daily_pnl = _get_todays_pnl(config.market)
            positions = _get_alpaca_positions()
            n_signals_today = _count_todays_signals(config.market)

            drawdown = compute_daily_drawdown([daily_pnl], gate.daily_loss_limit)

            status = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": "LIVE" if config.live else "DRY_RUN",
                "market": config.market,
                "strategy": config.strategy_id,
                "market_open": _in_market_hours(),
                "daily_pnl": round(daily_pnl, 2),
                "loss_limit": gate.daily_loss_limit,
                "remaining": round(gate.daily_loss_limit + daily_pnl, 2),
                "limit_breached": drawdown.limit_breached,
                "warning": drawdown.warning_level,
                "positions": len(positions),
                "max_positions": gate.max_positions,
                "signals_today": n_signals_today,
                "max_signals": config.max_signals_per_day,
                "trade_enabled": gate.trade_enabled,
                "dry_run": gate.dry_run,
            }

            log.info("STATUS: %s", status)

            if drawdown.limit_breached:
                log.warning("CIRCUIT BREAKER: daily loss limit $%.2f breached (PnL=$%.2f)",
                            gate.daily_loss_limit, daily_pnl)

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Monitor error — continuing")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="NeuralQuant Trading Daemon")
    parser.add_argument("--live", action="store_true",
                        help="Enable live trading (requires TRADE_ENABLED=true in env)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry run mode (default)")
    args = parser.parse_args()

    config = DaemonConfig(args)
    log.info("=== NeuralQuant Trade Daemon ===")
    log.info("Config: %s", config)
    log.info("PID: %d", os.getpid())

    signal_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    execute_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    loop = asyncio.get_event_loop()

    async def shutdown():
        log.info("Shutdown signal received — draining queues...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Daemon stopped.")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await asyncio.gather(
            clock(signal_queue, config),
            scanner(signal_queue, execute_queue, config),
            executor(execute_queue, config),
            resolver(config),
            monitor(config),
        )
    except asyncio.CancelledError:
        log.info("Daemon cancelled — exiting")
    except Exception:
        log.exception("Daemon fatal error")
        raise


if __name__ == "__main__":
    asyncio.run(main())
