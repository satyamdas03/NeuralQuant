"""Calibration tracker for NeuralQuant trading signals.

Logs every signal to Supabase signal_log and tracks accuracy over time.
Pattern from polymarket-pipeline: log → resolve → calibrate → size better.

All functions degrade gracefully when Supabase is unreachable or table missing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

log = logging.getLogger(__name__)
_env_loaded = False


def _load_env():
    global _env_loaded
    if _env_loaded:
        return
    env_path = Path(__file__).resolve().parents[3] / "apps" / "api" / ".env"
    load_dotenv(env_path, override=True)
    _env_loaded = True


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict[str, Any]] | dict[str, Any] | None = None,
    extra_headers: dict | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    _load_env()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None

    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra_headers:
        headers.update(extra_headers)

    try:
        with httpx.Client(timeout=10) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = client.post(endpoint, json=body, headers=headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as e:
        log.warning("Supabase REST call failed for table=%s: %s", table, e)
        return None


@dataclass
class SignalRecord:
    ticker: str
    signal_date: str              # ISO 8601
    composite_score: float        # 0-1
    edge: float                   # 0-1
    direction: str                # "bullish" | "bearish" | "neutral"
    entry_price: float
    exit_price: float | None = None
    pnl: float | None = None
    resolved: bool = False
    resolution_date: str | None = None
    market: str = "US"
    strategy: str = "default"
    bet: float = 0.0
    signal_id: str | None = None  # set by log_signal on success


@dataclass
class AccuracyReport:
    hit_rate: float               # pct of bullish signals that gained
    avg_pnl: float
    total_pnl: float
    sharpe: float
    profit_factor: float          # gross gain / gross loss
    n_trades: int
    n_winners: int
    n_losers: int
    lookback_days: int


class CalibrationTracker:
    """Logs, resolves, and analyzes trading signals against Supabase signal_log."""

    TABLE = "signal_log"

    def log_signal(self, record: SignalRecord) -> SignalRecord | None:
        """Insert a signal into signal_log. Returns record with signal_id set, or None."""
        now = datetime.now(timezone.utc).isoformat()
        body = {
            "ticker": record.ticker.upper(),
            "market": record.market,
            "signal_date": record.signal_date,
            "composite_score": record.composite_score,
            "edge": record.edge,
            "direction": record.direction,
            "entry_price": record.entry_price,
            "bet": record.bet,
            "strategy": record.strategy,
            "resolved": False,
            "created_at": now,
        }
        result = _supabase_rest(self.TABLE, method="POST", body=body)
        if isinstance(result, list) and result:
            record.signal_id = str(result[0].get("id", ""))
            return record
        if isinstance(result, dict) and "id" in result:
            record.signal_id = str(result["id"])
            return record
        return None

    def resolve_signal(
        self,
        signal_id: str,
        exit_price: float,
        pnl: float,
    ) -> bool:
        """Mark a signal as resolved with exit price and PnL."""
        now = datetime.now(timezone.utc).isoformat()
        result = _supabase_rest(
            self.TABLE,
            method="PATCH",
            query={"id": f"eq.{signal_id}"},
            body={
                "exit_price": exit_price,
                "pnl": pnl,
                "resolved": True,
                "resolution_date": now,
            },
        )
        return result is not None

    def get_accuracy(
        self,
        lookback_days: int = 90,
        market: str = "US",
    ) -> AccuracyReport:
        """Return accuracy metrics for resolved signals in lookback window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        data = _supabase_rest(
            self.TABLE,
            method="GET",
            query={
                "select": "*",
                "market": f"eq.{market}",
                "resolved": "eq.true",
                "signal_date": f"gte.{cutoff}",
                "order": "signal_date.desc",
            },
        )
        if not isinstance(data, list) or not data:
            return AccuracyReport(
                hit_rate=0.0, avg_pnl=0.0, total_pnl=0.0,
                sharpe=0.0, profit_factor=0.0,
                n_trades=0, n_winners=0, n_losers=0,
                lookback_days=lookback_days,
            )

        pnls: list[float] = []
        winners = 0
        losers = 0
        gross_gain = 0.0
        gross_loss = 0.0

        for row in data:
            p = row.get("pnl")
            if p is None:
                continue
            pnls.append(float(p))
            if p > 0:
                winners += 1
                gross_gain += float(p)
            elif p < 0:
                losers += 1
                gross_loss += abs(float(p))

        n = len(pnls)
        if n == 0:
            return AccuracyReport(
                hit_rate=0.0, avg_pnl=0.0, total_pnl=0.0,
                sharpe=0.0, profit_factor=0.0,
                n_trades=0, n_winners=0, n_losers=0,
                lookback_days=lookback_days,
            )

        avg = sum(pnls) / n
        total = sum(pnls)

        # Sharpe: mean / stddev (annualized factor omitted — it's per-trade)
        if n > 1:
            mean = sum(pnls) / n
            variance = sum((x - mean) ** 2 for x in pnls) / (n - 1)
            std = variance ** 0.5
            sharpe = mean / std if std > 0 else 0.0
        else:
            sharpe = 0.0

        profit_factor = gross_gain / gross_loss if gross_loss > 0 else (999.0 if gross_gain > 0 else 0.0)

        return AccuracyReport(
            hit_rate=round(winners / n, 4) if n > 0 else 0.0,
            avg_pnl=round(avg, 2),
            total_pnl=round(total, 2),
            sharpe=round(sharpe, 4),
            profit_factor=round(profit_factor, 2),
            n_trades=n,
            n_winners=winners,
            n_losers=losers,
            lookback_days=lookback_days,
        )

    def get_by_ticker(
        self,
        ticker: str,
        market: str = "US",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return signal history for a ticker, newest first."""
        data = _supabase_rest(
            self.TABLE,
            method="GET",
            query={
                "select": "*",
                "ticker": f"eq.{ticker.upper()}",
                "market": f"eq.{market}",
                "order": "signal_date.desc",
                "limit": str(limit),
            },
        )
        return data if isinstance(data, list) else []

    def get_recent_unresolved(
        self,
        market: str = "US",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return unresolved signals, newest first (for auto-resolution)."""
        data = _supabase_rest(
            self.TABLE,
            method="GET",
            query={
                "select": "*",
                "market": f"eq.{market}",
                "resolved": "eq.false",
                "order": "signal_date.desc",
                "limit": str(limit),
            },
        )
        return data if isinstance(data, list) else []
