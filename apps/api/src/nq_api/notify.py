"""Email notifications via Resend.

Requires RESEND_API_KEY env var. If missing, logs instead of sending.
"""
from __future__ import annotations
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

RESEND_FROM = os.environ.get("RESEND_FROM", "NeuralQuant <alerts@neuralquant.ai>")


def _resend_client():
    """Lazy import resend — only needed when sending."""
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY", "")
        return resend
    except ImportError:
        return None


def send_alert_email(
    to: str,
    ticker: str,
    market: str,
    alert_type: str,
    old_value: Optional[float],
    new_value: Optional[float],
    regime_label: Optional[str] = None,
) -> bool:
    """Send an alert email. Returns True if sent (or key missing but logged)."""
    subject = f"NeuralQuant Alert: {ticker} "
    if alert_type == "score_change":
        delta = (new_value or 0) - (old_value or 0)
        direction = "up" if delta > 0 else "down"
        subject += f"score {direction} to {new_value:.2f}"
    elif alert_type == "threshold":
        subject += f"crossed threshold ({new_value:.2f})"
    elif alert_type == "regime_change":
        subject += f"regime shifted to {regime_label or 'new regime'}"
    else:
        subject += "alert triggered"

    market_label = "NIFTY 500" if market == "IN" else "S&P 500"
    score_display = f"{new_value:.2f}" if new_value is not None else "N/A"
    delta_display = ""
    if old_value is not None and new_value is not None:
        delta_display = f" ({'+' if new_value >= old_value else ''}{(new_value - old_value):.2f})"

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto;
                background: #131313; color: #e0e0e0; border-radius: 12px; overflow: hidden;">
      <div style="padding: 24px 32px; background: linear-gradient(135deg, #c1c1ff 0%, #bdf4ff 100%);
                  color: #0e0e0e;">
        <h1 style="margin: 0; font-size: 20px;">{ticker}</h1>
        <p style="margin: 4px 0 0; font-size: 14px; opacity: 0.7;">{market_label} · {alert_type.replace('_', ' ').title()}</p>
      </div>
      <div style="padding: 24px 32px;">
        <p style="font-size: 32px; font-weight: 700; margin: 0;">
          {score_display}<span style="font-size: 16px; color: #a0a0a0;">{delta_display}</span>
        </p>
        <p style="font-size: 14px; color: #a0a0a0; margin-top: 16px;">
          You set this alert on NeuralQuant. This is not investment advice.
        </p>
        <a href="https://neuralquant.vercel.app/stocks/{ticker}?market={market}"
           style="display: inline-block; margin-top: 16px; padding: 10px 24px;
                  background: linear-gradient(135deg, #c1c1ff, #bdf4ff);
                  color: #0e0e0e; border-radius: 8px; text-decoration: none; font-weight: 600;">
          View {ticker} Details →
        </a>
      </div>
    </div>
    """

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging alert: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": to,
            "subject": subject,
            "html": html,
        })
        logger.info("Alert email sent: %s -> %s", subject, to)
        return True
    except Exception:
        logger.exception("Failed to send alert email to %s", to)
        return False