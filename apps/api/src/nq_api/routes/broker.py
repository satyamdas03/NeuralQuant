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
