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
from nq_api.config import FRONTEND_URL


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
        <a href="{FRONTEND_URL}/stocks/{ticker}?market={market}"
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


# ---------------------------------------------------------------------------
# Welcome / onboarding email sequence
# ---------------------------------------------------------------------------

_NQ_BRAND_HEAD = """
<div style="font-family: system-ui, -apple-system, sans-serif; max-width: 520px;
            margin: 0 auto; background: #0f0f1a; color: #e0e0e0;
            border-radius: 12px; overflow: hidden;">
  <div style="padding: 28px 32px; background: linear-gradient(135deg, #c1c1ff 0%, #bdf4ff 100%);
              color: #0e0e0e;">
    <h1 style="margin: 0; font-size: 22px; letter-spacing: -0.3px;">NeuralQuant</h1>
  </div>
"""

_NQ_BRAND_FOOT = """
  <div style="padding: 20px 32px; border-top: 1px solid #1e1e30;">
    <p style="margin: 0; font-size: 12px; color: #a0a0b0;">
      NeuralQuant · AI-powered stock intelligence<br>
      <a href="{FRONTEND_URL}" style="color: #bdf4ff;">neuralquant.ai</a>
       · <a href="{FRONTEND_URL}/pricing" style="color: #bdf4ff;">Upgrade</a>
    </p>
  </div>
</div>
"""

_NQ_CTA = """<a href="{url}" style="display: inline-block; margin-top: 20px; padding: 12px 28px;
           background: linear-gradient(135deg, #c1c1ff, #bdf4ff);
           color: #0e0e0e; border-radius: 8px; text-decoration: none;
           font-weight: 600; font-size: 15px;">{label}</a>"""


def send_welcome_email(to: str, name: str | None = None) -> bool:
    """Day-0 welcome email with quickstart links."""
    greeting = f"Hi {name}" if name else "Hi there"
    subject = "Welcome to NeuralQuant — here's your first analysis"

    html = f"""
    {_NQ_BRAND_HEAD}
    <div style="padding: 28px 32px;">
      <p style="font-size: 18px; margin: 0 0 8px;">{greeting}, welcome aboard!</p>
      <p style="font-size: 14px; color: #a0a0b0; margin: 0 0 24px;">
        NeuralQuant scores 1 000+ stocks every night so you can act with confidence.
        Here's what you can do right now:
      </p>

      <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 0; color: #c1c1ff;">📊</td>
          <td style="padding: 8px 0;"><strong>5-Factor Scoring</strong> — composite score across valuation, momentum, quality, growth &amp; sentiment</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #c1c1ff;">🎭</td>
          <td style="padding: 8px 0;"><strong>PARA-DEBATE</strong> — watch 6 AI analysts argue over any stock</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #c1c1ff;">💰</td>
          <td style="padding: 8px 0;"><strong>Smart Money Signals</strong> — track what the big money is doing</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #c1c1ff;">🔍</td>
          <td style="padding: 8px 0;"><strong>Screener &amp; Watchlists</strong> — filter, sort and save your top picks</td>
        </tr>
      </table>

      <p style="font-size: 14px; margin: 24px 0 4px; color: #a0a0b0;">
        Start with two popular names:
      </p>

      <div style="margin: 8px 0 0;">
        <a href="{FRONTEND_URL}/stocks/RELIANCE.NS?market=IN"
           style="display: inline-block; padding: 8px 16px; margin-right: 8px;
                  background: #1e1e30; border-radius: 6px; color: #c1c1ff;
                  text-decoration: none; font-weight: 600;">
          RELIANCE.NS →
        </a>
        <a href="{FRONTEND_URL}/stocks/AAPL?market=US"
           style="display: inline-block; padding: 8px 16px;
                  background: #1e1e30; border-radius: 6px; color: #c1c1ff;
                  text-decoration: none; font-weight: 600;">
          AAPL →
        </a>
      </div>
    </div>
    {_NQ_BRAND_FOOT}
    """

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging welcome email: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({"from": RESEND_FROM, "to": to, "subject": subject, "html": html})
        logger.info("Welcome email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send welcome email to %s", to)
        return False


def send_debate_demo_email(to: str) -> bool:
    """Day-1 PARA-DEBATE demo email."""
    subject = "Watch 6 AI analysts debate RELIANCE"

    html = f"""
    {_NQ_BRAND_HEAD}
    <div style="padding: 28px 32px;">
      <p style="font-size: 18px; margin: 0 0 12px;">Ever seen analysts fight over a stock?</p>
      <p style="font-size: 14px; color: #a0a0b0; margin: 0 0 16px; line-height: 1.6;">
        NeuralQuant's <strong style="color: #bdf4ff;">PARA-DEBATE</strong> engine runs
        <strong>6 AI personas</strong> — Bull, Bear, Quant, Fundamentalist, Technician &amp;
        Sentiment Analyst — each arguing their case on any stock you pick.
        <br><br>
        They challenge each other's assumptions, expose blind spots, and deliver a final
        verdict so you see <em>both</em> sides before you trade.
      </p>

      {_NQ_CTA.format(url=f"{FRONTEND_URL}/query", label="Try PARA-DEBATE now →")}
    </div>
    {_NQ_BRAND_FOOT}
    """

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging debate demo email: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({"from": RESEND_FROM, "to": to, "subject": subject, "html": html})
        logger.info("Debate demo email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send debate demo email to %s", to)
        return False


def send_screener_email(to: str) -> bool:
    """Day-3 screener intro email."""
    subject = "Find top-rated stocks in seconds"

    html = f"""
    {_NQ_BRAND_HEAD}
    <div style="padding: 28px 32px;">
      <p style="font-size: 18px; margin: 0 0 12px;">1 000+ stocks. Scored nightly. Filtered your way.</p>
      <p style="font-size: 14px; color: #a0a0b0; margin: 0 0 16px; line-height: 1.6;">
        NeuralQuant's <strong style="color: #bdf4ff;">Screener</strong> lets you sort by any
        factor — valuation, momentum, quality, growth, sentiment, or the composite score — and
        save results to watchlists for quick check-ins.
        <br><br>
        Whether you're hunting deep-value picks or momentum leaders, the Screener surfaces
        them in seconds.
      </p>

      {_NQ_CTA.format(url=f"{FRONTEND_URL}/screener", label="Open Screener →")}
    </div>
    {_NQ_BRAND_FOOT}
    """

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging screener email: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({"from": RESEND_FROM, "to": to, "subject": subject, "html": html})
        logger.info("Screener email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send screener email to %s", to)
        return False


def send_upgrade_email(to: str) -> bool:
    """Day-7 upgrade prompt email."""
    subject = "Unlock 100 queries/day — Investor tier"

    html = f"""
    {_NQ_BRAND_HEAD}
    <div style="padding: 28px 32px;">
      <p style="font-size: 18px; margin: 0 0 12px;">You've been using NeuralQuant for a week!</p>
      <p style="font-size: 14px; color: #a0a0b0; margin: 0 0 16px; line-height: 1.6;">
        The free tier gives you <strong>10 queries per day</strong> — great for getting started.
        But if you're checking multiple stocks, running debates, and using the screener daily,
        you might be hitting that limit more often than you'd like.
      </p>

      <table style="width: 100%; font-size: 14px; border-collapse: collapse;
                     background: #1a1a2e; border-radius: 8px; overflow: hidden;">
        <tr style="border-bottom: 1px solid #2a2a40;">
          <td style="padding: 12px 16px; color: #a0a0b0;">Free tier</td>
          <td style="padding: 12px 16px; text-align: right; color: #a0a0b0;">10 queries / day</td>
        </tr>
        <tr>
          <td style="padding: 12px 16px; color: #c1c1ff; font-weight: 600;">Investor tier</td>
          <td style="padding: 12px 16px; text-align: right; color: #bdf4ff; font-weight: 600;">
            100 queries / day · 25 watchlists
          </td>
        </tr>
      </table>

      {_NQ_CTA.format(url=f"{FRONTEND_URL}/pricing", label="See Investor plan →")}
    </div>
    {_NQ_BRAND_FOOT}
    """

    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        logger.info("RESEND_API_KEY not set — logging upgrade email: %s -> %s", subject, to)
        return True

    try:
        resend.Emails.send({"from": RESEND_FROM, "to": to, "subject": subject, "html": html})
        logger.info("Upgrade email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send upgrade email to %s", to)
        return False