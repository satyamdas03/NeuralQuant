"""Background alert checker — compares latest scores to subscriptions and fires emails.

Called from the data pipeline after scores are recomputed. Uses Supabase for
subscription/delivery state and Resend for email delivery.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from nq_api.notify import send_alert_email

logger = logging.getLogger(__name__)


def _client():
    from supabase import create_client
    import os
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def check_and_fire_alerts(scores: dict[str, float], market: str = "US") -> int:
    """Compare latest scores to alert subscriptions. Fire emails where thresholds crossed.

    scores: {ticker: composite_score} — latest scores from engine compute.
    market: "US" or "IN"

    Returns count of alerts fired.
    """
    if not scores:
        return 0

    client = _client()
    fired = 0

    # Get all subscriptions for tickers we have scores for
    tickers = list(scores.keys())
    # Fetch in batches of 50 (Supabase filter limit)
    all_subs = []
    for i in range(0, len(tickers), 50):
        batch = tickers[i:i + 50]
        resp = (
            client.table("alert_subscriptions")
            .select("*, users!inner(email, tier)")
            .in_("ticker", batch)
            .eq("market", market)
            .execute()
        )
        all_subs.extend(resp.data or [])

    for sub in all_subs:
        ticker = sub["ticker"]
        current_score = scores.get(ticker)
        if current_score is None:
            continue

        user_email = sub["users"]["email"] if sub.get("users") else None
        if not user_email:
            continue

        alert_type = sub["alert_type"]

        # Fetch last delivery for dedup
        last = (
            client.table("alert_deliveries")
            .select("new_value, delivered_at")
            .eq("subscription_id", sub["id"])
            .order("delivered_at", desc=True)
            .limit(1)
            .execute()
        )
        last_rows = last.data or []
        old_value = last_rows[0]["new_value"] if last_rows else None

        should_fire = False

        if alert_type == "score_change":
            if old_value is not None:
                delta = abs(current_score - old_value)
                if delta >= sub.get("min_delta", 0.10):
                    should_fire = True
        elif alert_type == "threshold":
            threshold = sub.get("threshold")
            if threshold is not None:
                if old_value is not None:
                    crossed_up = old_value < threshold <= current_score
                    crossed_down = old_value >= threshold > current_score
                    if crossed_up or crossed_down:
                        should_fire = True
                else:
                    if current_score >= threshold:
                        should_fire = True
        elif alert_type == "regime_change":
            # Regime change alerts handled separately — always fire if score changed
            if old_value is not None and old_value != current_score:
                should_fire = True

        if not should_fire:
            continue

        # Rate-limit: don't re-trigger within 4 hours
        last_triggered = sub.get("last_triggered_at")
        if last_triggered:
            try:
                from dateutil.parser import isoparse
                lt = isoparse(str(last_triggered))
                hours_since = (datetime.now(timezone.utc) - lt).total_seconds() / 3600
                if hours_since < 4:
                    continue
            except Exception:
                pass

        # Fire email
        ok = send_alert_email(
            to=user_email,
            ticker=ticker,
            market=market,
            alert_type=alert_type,
            old_value=old_value,
            new_value=current_score,
        )

        if ok:
            # Record delivery
            client.table("alert_deliveries").insert({
                "user_id": sub["user_id"],
                "subscription_id": sub["id"],
                "ticker": ticker,
                "market": market,
                "alert_type": alert_type,
                "old_value": old_value,
                "new_value": current_score,
            }).execute()

            # Update last_triggered_at on subscription
            client.table("alert_subscriptions").update({
                "last_triggered_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", sub["id"]).execute()

            fired += 1

    return fired