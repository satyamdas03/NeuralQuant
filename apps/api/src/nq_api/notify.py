"""Email notifications — DISABLED.

All email functionality has been removed. This module now exposes the same
public API as no-ops so callers don't have to be rewritten, but nothing is
sent and no external email service is imported.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Legacy compatibility constant — always empty string.
RESEND_FROM = ""


def _send_email_with_retry(to: str, subject: str, html: str) -> bool:
    """No-op — emails are disabled."""
    logger.debug("Email send skipped (disabled): %s -> %s", subject, to)
    return False


def send_alert_email(
    to: str,
    ticker: str,
    market: str,
    alert_type: str,
    old_value: Optional[float],
    new_value: Optional[float],
    regime_label: Optional[str] = None,
) -> bool:
    """No-op — email alerts are disabled."""
    logger.debug("Alert email skipped (disabled): %s %s", ticker, to)
    return False


def send_welcome_email(to: str, name: str | None = None) -> bool:
    """No-op — welcome emails are disabled."""
    logger.debug("Welcome email skipped (disabled): %s", to)
    return False


def send_debate_demo_email(to: str) -> bool:
    """No-op — onboarding emails are disabled."""
    logger.debug("Debate demo email skipped (disabled): %s", to)
    return False


def send_screener_email(to: str) -> bool:
    """No-op — onboarding emails are disabled."""
    logger.debug("Screener email skipped (disabled): %s", to)
    return False


def send_upgrade_email(to: str) -> bool:
    """No-op — onboarding emails are disabled."""
    logger.debug("Upgrade email skipped (disabled): %s", to)
    return False
