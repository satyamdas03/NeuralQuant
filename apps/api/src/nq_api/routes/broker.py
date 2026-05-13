"""Broker integration routes — Alpaca (US) and Zerodha (India) deep-link."""
from __future__ import annotations
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nq_api.auth.models import User
from nq_api.auth.rate_limit import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["broker"])


class TradeDeepLinkRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"] = "buy"
    broker: Literal["alpaca", "zerodha"] = "alpaca"


class TradeDeepLinkResponse(BaseModel):
    url: str
    broker: str
    symbol: str
    side: str
    note: str


class PlaceOrderRequest(BaseModel):
    symbol: str
    qty: float
    side: Literal["buy", "sell"] = "buy"
    dry_run: bool = True


class PlaceOrderResponse(BaseModel):
    status: str  # "simulated" | "executed" | "blocked" | "failed"
    symbol: str
    qty: float
    side: str
    order_id: str | None = None
    signal_id: str | None = None
    detail: str = ""


@router.post("/deep-link", response_model=TradeDeepLinkResponse)
def get_trade_deep_link(req: TradeDeepLinkRequest, user: User = Depends(get_current_user)):
    """
    Get deep-link URL to pre-fill trade ticket in broker app.
    User confirms trade in broker app — NeuralQuant never executes automatically.
    No regulatory risk. No funds handling.
    """
    from nq_data.broker import deep_link_trade

    url = deep_link_trade(req.symbol, req.side, req.broker)
    return TradeDeepLinkResponse(
        url=url,
        broker=req.broker,
        symbol=req.symbol.upper(),
        side=req.side,
        note="Opens broker trade ticket. Confirm trade in broker app. NeuralQuant never holds funds.",
    )


@router.get("/account")
def get_broker_account(user: User = Depends(get_current_user)):
    """Get Alpaca account info if configured."""
    from nq_data.broker import get_alpaca_config_from_env, get_account_info

    config = get_alpaca_config_from_env()
    if config is None:
        raise HTTPException(503, "Alpaca not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY.")

    info = get_account_info(config)
    if info is None:
        raise HTTPException(502, "Alpaca connection failed.")

    return info


@router.get("/positions")
def get_broker_positions(user: User = Depends(get_current_user)):
    """Get current Alpaca positions."""
    from nq_data.broker import get_alpaca_config_from_env, get_positions

    config = get_alpaca_config_from_env()
    if config is None:
        raise HTTPException(503, "Alpaca not configured.")

    return get_positions(config)


@router.post("/order", response_model=PlaceOrderResponse)
def place_order(req: PlaceOrderRequest, user: User = Depends(get_current_user)):
    """Place an order via Alpaca. Dry-run by default — pass dry_run=false to execute live.

    Safety gates:
    - TRADE_ENABLED must be "true" in env for live execution
    - DRY_RUN must be "false" in env for live execution
    - Auto-logs to signal_log for calibration tracking
    """
    import os
    from nq_data.broker import get_alpaca_config_from_env, place_market_order, get_positions
    from nq_signals.safety import load_safety_gate, check_order
    from nq_signals.calibration import CalibrationTracker, SignalRecord

    gate = load_safety_gate()

    # Count current positions for max_positions check
    try:
        config = get_alpaca_config_from_env()
        if config:
            positions = get_positions(config)
            current_positions = len(positions) if positions else 0
        else:
            current_positions = 0
    except Exception:
        current_positions = 0

    # Get today's PnL for daily loss check
    from nq_api.cache.score_cache import _supabase_rest
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pnl_rows = _supabase_rest(
        "signal_log",
        method="GET",
        query={
            "select": "pnl",
            "resolved": "eq.true",
            "resolution_date": f"gte.{today}T00:00:00Z",
        },
    )
    daily_pnl = sum(float(r.get("pnl", 0) or 0) for r in pnl_rows) if isinstance(pnl_rows, list) else 0.0

    # Safety gate check
    check = check_order(
        bet=req.qty * 100,  # approximate bet size
        gate=gate,
        daily_pnl=daily_pnl,
        current_positions=current_positions,
    )

    if not check.passed:
        return PlaceOrderResponse(
            status="blocked",
            symbol=req.symbol.upper(),
            qty=req.qty,
            side=req.side,
            detail=check.reason,
        )

    # Dry run: simulate only
    if req.dry_run or gate.dry_run:
        return PlaceOrderResponse(
            status="simulated",
            symbol=req.symbol.upper(),
            qty=req.qty,
            side=req.side,
            detail=f"Dry run: would have {req.side} {req.qty} shares of {req.symbol.upper()}. Set DRY_RUN=false + dry_run=false to execute.",
        )

    # Live execution
    config = get_alpaca_config_from_env()
    if config is None:
        return PlaceOrderResponse(
            status="failed",
            symbol=req.symbol.upper(),
            qty=req.qty,
            side=req.side,
            detail="Alpaca not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY.",
        )

    try:
        result = place_market_order(
            config, req.symbol.upper(), int(req.qty), req.side, "market", "day"
        )
        order_id = result.get("id", "") if result else ""

        # Auto-log to signal_log for calibration
        tracker = CalibrationTracker()
        price_est = 0.0
        try:
            fills = result.get("filled_avg_price") if result else None
            if fills:
                price_est = float(fills)
        except Exception:
            pass

        record = SignalRecord(
            ticker=req.symbol.upper(),
            market="US",
            composite_score=0.0,
            edge=0.0,
            direction=req.side,
            entry_price=price_est,
            bet=float(req.qty),
            strategy="manual",
        )
        tracker.log_signal(record)

        return PlaceOrderResponse(
            status="executed",
            symbol=req.symbol.upper(),
            qty=req.qty,
            side=req.side,
            order_id=order_id,
            signal_id=record.signal_id,
            detail=f"Order {order_id} placed: {req.side} {req.qty} {req.symbol.upper()}",
        )
    except Exception as exc:
        logger.exception("Order execution failed")
        return PlaceOrderResponse(
            status="failed",
            symbol=req.symbol.upper(),
            qty=req.qty,
            side=req.side,
            detail=str(exc),
        )
