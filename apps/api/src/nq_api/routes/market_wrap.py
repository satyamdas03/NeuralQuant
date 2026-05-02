"""Daily Market Wrap — scheduled email with market snapshot and NeuralQuant picks.

This module provides:
1. POST /market-wrap/send — Trigger a market wrap email to a specific user
2. POST /market-wrap/broadcast — Send to all subscribed users (admin only)

The email content is built from live market data + score_cache.
A GitHub Actions cron or scheduled task can call /market-wrap/broadcast daily.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from nq_api.config import FRONTEND_URL
from nq_api.auth.models import User
from nq_api.auth.rate_limit import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-wrap", tags=["market-wrap"])


class MarketWrapRequest(BaseModel):
    email: str
    name: Optional[str] = None
    market: str = "US"


class BroadcastRequest(BaseModel):
    market: str = "US"
    tier: str = "investor"  # minimum tier to receive


def _build_market_wrap_html(market_data: dict, top_picks: list[dict], market: str = "US") -> str:
    """Build the daily market wrap email HTML."""
    market_label = "NIFTY 500" if market == "IN" else "S&P 500"

    # Market snapshot section
    indices_html = ""
    for idx in market_data.get("indices", []):
        change_icon = "▲" if idx.get("change_pct", 0) >= 0 else "▼"
        change_color = "#4ade80" if idx.get("change_pct", 0) >= 0 else "#f87171"
        indices_html += f"""
        <tr>
          <td style="padding: 8px 0; font-weight: 600;">{idx.get('name', 'N/A')}</td>
          <td style="padding: 8px 0; text-align: right;">{idx.get('price', 'N/A'):,.2f}</td>
          <td style="padding: 8px 0; text-align: right; color: {change_color};">
            {change_icon} {idx.get('change_pct', 0):.2f}%
          </td>
        </tr>"""

    # Top picks section
    picks_html = ""
    for pick in top_picks[:5]:
        score = pick.get("composite_score", 0)
        score_bar = int(score * 10)  # Convert 0-1 to 0-10
        picks_html += f"""
        <tr>
          <td style="padding: 8px 0; font-weight: 600; color: #c1c1ff;">
            <a href="{FRONTEND_URL}/stocks/{pick.get('ticker', '')}?market={market}"
               style="color: #c1c1ff; text-decoration: none;">
              {pick.get('ticker', 'N/A')}
            </a>
          </td>
          <td style="padding: 8px 0; text-align: center;">
            <span style="background: linear-gradient(135deg, #c1c1ff, #bdf4ff);
                          padding: 4px 12px; border-radius: 4px; color: #0e0e0e; font-weight: 600;">
              {score_bar}/10
            </span>
          </td>
          <td style="padding: 8px 0; text-align: right; color: #a0a0b0;">
            {pick.get('sector', 'N/A')}
          </td>
        </tr>"""

    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

    return f"""
    <div style="font-family: system-ui, -apple-system, sans-serif; max-width: 520px;
                margin: 0 auto; background: #0f0f1a; color: #e0e0e0;
                border-radius: 12px; overflow: hidden;">
      <div style="padding: 28px 32px; background: linear-gradient(135deg, #c1c1ff 0%, #bdf4ff 100%);
                  color: #0e0e0e;">
        <p style="margin: 0; font-size: 12px; opacity: 0.7;">{today}</p>
        <h1 style="margin: 4px 0 0; font-size: 22px;">NeuralQuant Daily Wrap</h1>
        <p style="margin: 4px 0 0; font-size: 14px; opacity: 0.8;">{market_label} Market Snapshot</p>
      </div>

      <div style="padding: 24px 32px;">
        <h2 style="font-size: 16px; margin: 0 0 12px; color: #bdf4ff;">Market Snapshot</h2>
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
          <tr style="border-bottom: 1px solid #1e1e30;">
            <th style="padding: 8px 0; text-align: left; color: #a0a0b0;">Index</th>
            <th style="padding: 8px 0; text-align: right; color: #a0a0b0;">Price</th>
            <th style="padding: 8px 0; text-align: right; color: #a0a0b0;">Change</th>
          </tr>
          {indices_html}
        </table>
      </div>

      <div style="padding: 0 32px 24px;">
        <h2 style="font-size: 16px; margin: 0 0 12px; color: #bdf4ff;">Top NeuralQuant Picks</h2>
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
          <tr style="border-bottom: 1px solid #1e1e30;">
            <th style="padding: 8px 0; text-align: left; color: #a0a0b0;">Ticker</th>
            <th style="padding: 8px 0; text-align: center; color: #a0a0b0;">Score</th>
            <th style="padding: 8px 0; text-align: right; color: #a0a0b0;">Sector</th>
          </tr>
          {picks_html}
        </table>
      </div>

      <div style="padding: 20px 32px; border-top: 1px solid #1e1e30;">
        <a href="{FRONTEND_URL}/screener"
           style="display: inline-block; padding: 12px 28px;
                  background: linear-gradient(135deg, #c1c1ff, #bdf4ff);
                  color: #0e0e0e; border-radius: 8px; text-decoration: none;
                  font-weight: 600; font-size: 15px;">
          Explore All Picks →
        </a>
      </div>

      <div style="padding: 16px 32px; border-top: 1px solid #1e1e30;">
        <p style="margin: 0; font-size: 12px; color: #a0a0b0;">
          NeuralQuant · AI-powered stock intelligence<br>
          <a href="{FRONTEND_URL}" style="color: #bdf4ff;">neuralquant.ai</a>
        </p>
      </div>
    </div>"""


def _send_market_wrap(to: str, name: str | None, market: str) -> bool:
    """Fetch market data and top picks, build HTML, send via Resend."""
    from nq_api.notify import _resend_client, RESEND_FROM
    from nq_api.routes.market import _market_overview_sync
    from nq_api.cache.score_cache import read_top_picks

    # Fetch market snapshot
    try:
        market_data = _market_overview_sync(market)
    except Exception:
        logger.exception("Market wrap: failed to fetch market data")
        market_data = {"indices": [], "futures": []}

    # Fetch top picks from score_cache
    try:
        top_picks = read_top_picks(market=market, limit=5)
    except Exception:
        logger.exception("Market wrap: failed to fetch top picks")
        top_picks = []

    html = _build_market_wrap_html(market_data, top_picks, market)
    subject = f"NeuralQuant Daily Wrap — {market_label(market)}"

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging market wrap: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": to,
            "subject": subject,
            "html": html,
        })
        logger.info("Market wrap email sent: %s -> %s", subject, to)
        return True
    except Exception:
        logger.exception("Failed to send market wrap to %s", to)
        return False


def market_label(market: str) -> str:
    return "NIFTY 500" if market == "IN" else "S&P 500"


@router.post("/send")
async def send_market_wrap(
    req: MarketWrapRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Send a market wrap email to the requesting user."""
    background_tasks.add_task(_send_market_wrap, req.email, req.name, req.market)
    return {"status": "queued", "email": req.email, "market": req.market}


@router.post("/broadcast")
async def broadcast_market_wrap(
    req: BroadcastRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Admin: Send market wrap to all subscribed users above the given tier.

    Requires RESEND_API_KEY and SUPABASE_SERVICE_ROLE_KEY.
    This endpoint is rate-limited to once per 4 hours.
    """
    if user.tier not in ("pro", "api"):
        raise HTTPException(403, "Broadcast requires pro or api tier")

    # Fetch subscribed users from Supabase
    from nq_api.cache.score_cache import _supabase_rest
    try:
        users = _supabase_rest("GET", f"/rest/v1/users?select=email,name,tier&tier=gte.{req.tier}")
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch users: {e}")

    if not users:
        return {"status": "no_recipients", "count": 0}

    count = 0
    for u in users:
        if u.get("email"):
            background_tasks.add_task(_send_market_wrap, u["email"], u.get("name"), req.market)
            count += 1

    return {"status": "queued", "recipients": count, "market": req.market}