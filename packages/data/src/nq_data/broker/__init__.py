"""
NeuralQuant broker package — rate limiter + Alpaca integration.

Rate limiter (from _rate_limiter): DataBroker, SourceConfig, broker singleton.
Alpaca (below): paper/live trading, account info, positions, orders, deep links.
"""
from __future__ import annotations
import os
import logging
from dataclasses import dataclass
from typing import Optional, Literal

# Re-export rate limiter from the original broker module (now _rate_limiter)
from nq_data.broker._rate_limiter import DataBroker, SourceConfig, broker  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass
class AlpacaConfig:
    api_key: str
    secret_key: str
    paper: bool = True  # Default to paper trading
    base_url: str = ""


def get_alpaca_client(config: AlpacaConfig):
    """Get Alpaca trading client. Returns None if alpaca-py not installed."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import AssetClass

        base_url = config.base_url or (
            "https://paper-api.alpaca.markets" if config.paper
            else "https://api.alpaca.markets"
        )
        return TradingClient(config.api_key, config.secret_key, paper=config.paper, url=base_url)
    except ImportError:
        logger.warning("alpaca-py not installed. Install: pip install alpaca-py")
        return None


def get_account_info(config: AlpacaConfig) -> dict | None:
    """Fetch Alpaca account details."""
    client = get_alpaca_client(config)
    if client is None:
        return None
    try:
        account = client.get_account()
        return {
            "id": str(account.id),
            "status": str(account.status),
            "currency": str(account.currency),
            "buying_power": str(account.buying_power),
            "cash": str(account.cash),
            "portfolio_value": str(account.portfolio_value),
            "equity": str(account.equity),
            "daytrade_count": int(account.daytrade_count),
            "pattern_day_trader": bool(account.pattern_day_trader),
            "paper": config.paper,
        }
    except Exception as e:
        logger.warning("Alpaca account fetch failed: %s", e)
        return None


def get_positions(config: AlpacaConfig) -> list[dict]:
    """Fetch current positions."""
    client = get_alpaca_client(config)
    if client is None:
        return []
    try:
        positions = client.get_all_positions()
        return [{
            "symbol": p.symbol,
            "qty": str(p.qty),
            "market_value": str(p.market_value),
            "cost_basis": str(p.cost_basis),
            "unrealized_pl": str(p.unrealized_pl),
            "unrealized_plpc": str(p.unrealized_plpc),
            "current_price": str(p.current_price),
            "avg_entry_price": str(p.avg_entry_price),
            "side": str(p.side),
        } for p in positions]
    except Exception as e:
        logger.warning("Alpaca positions fetch failed: %s", e)
        return []


def place_market_order(
    config: AlpacaConfig,
    symbol: str,
    qty: float,
    side: Literal["buy", "sell"],
    order_type: str = "market",
    time_in_force: str = "day",
) -> dict | None:
    """Place a market order on Alpaca."""
    client = get_alpaca_client(config)
    if client is None:
        return None
    try:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_data = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC,
        )
        order = client.submit_order(order_data)
        return {
            "id": str(order.id),
            "symbol": str(order.symbol),
            "qty": str(order.qty),
            "side": str(order.side),
            "type": str(order.type),
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
            "filled_qty": str(order.filled_qty) if order.filled_qty else "0",
            "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        }
    except Exception as e:
        logger.warning("Alpaca order failed: %s", e)
        return {"error": str(e)}


def deep_link_trade(symbol: str, side: str, broker: str = "alpaca") -> str:
    """
    Generate deep-link URL to pre-fill trade in broker app.
    Opens broker's trade ticket with symbol pre-filled.
    User confirms in broker app — we never execute automatically.
    """
    if broker == "alpaca":
        # Alpaca doesn't have deep links, direct to dashboard
        return f"https://app.alpaca.markets/trade/{symbol.upper()}"
    elif broker == "zerodha":
        return f"https://kite.zerodha.com/chart/web/trade/{symbol}"
    return f"https://app.alpaca.markets/trade/{symbol.upper()}"


def get_alpaca_config_from_env() -> AlpacaConfig | None:
    """Get Alpaca config from environment variables."""
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    paper = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

    if not api_key or not secret_key:
        return None

    return AlpacaConfig(api_key=api_key, secret_key=secret_key, paper=paper)
