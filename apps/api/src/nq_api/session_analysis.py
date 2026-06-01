"""Session analysis pipeline — fetch activities, generate MoM report via Claude, email via Resend.

Called as a background task from POST /session/end.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from nq_api.cache.score_cache import _supabase_rest
from nq_api.notify import RESEND_FROM, FRONTEND_URL, _resend_client

log = logging.getLogger(__name__)


def _fetch_activities(session_id: str) -> list[dict]:
    """Fetch all activities for a session, ordered by time."""
    try:
        result = _supabase_rest(
            f"session_activities?session_id=eq.{session_id}&select=*&order=created_at.asc&limit=500",
            method="GET",
        )
        return result if isinstance(result, list) else []
    except Exception:
        log.exception("Failed to fetch activities for session %s", session_id)
        return []


def _build_activity_summary(activities: list[dict], duration_seconds: int) -> str:
    """Build a structured text summary of all session activities."""
    if not activities:
        return "No activities recorded in this session."

    by_category: dict[str, list[dict]] = {}
    for a in activities:
        cat = a.get("category", "other")
        by_category.setdefault(cat, []).append(a)

    lines = [f"Session duration: {duration_seconds // 60} minutes", f"Total actions: {len(activities)}", ""]

    category_labels = {
        "navigation": "Pages Visited",
        "analysis": "Stocks Analyzed",
        "conversation": "AI Conversations",
        "screening": "Screening Activity",
        "portfolio": "Portfolio Actions",
        "watchlist": "Watchlist Actions",
        "feature": "Features Used",
        "other": "Other Actions",
    }

    for cat, cat_acts in sorted(by_category.items()):
        label = category_labels.get(cat, cat.title())
        lines.append(f"--- {label} ({len(cat_acts)}) ---")
        for a in cat_acts:
            act_label = a.get("label", a.get("activity_type", ""))
            payload = a.get("payload", {})
            detail = ""
            if payload:
                # Extract key details without being overly verbose
                if "ticker" in payload:
                    detail = f" [{payload['ticker']}]"
                elif "question" in payload:
                    q = str(payload["question"])[:80]
                    detail = f" Q: {q}"
                elif "text" in payload:
                    t = str(payload["text"])[:80]
                    detail = f" {t}"
                elif "feature" in payload:
                    detail = f" [{payload['feature']}]"
            lines.append(f"  • {act_label}{detail}")
        lines.append("")

    return "\n".join(lines)


def _generate_report_via_claude(
    activity_summary: str,
    user_name: str | None,
    duration_minutes: int,
    activity_count: int,
) -> tuple[str, str]:
    """Use Claude to generate a warm, personalized session report. Returns (report_text, summary)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("No ANTHROPIC_API_KEY — generating basic report without Claude")
        return _fallback_report(user_name, duration_minutes, activity_count)

    greeting_name = user_name or "there"

    prompt = f"""You are writing a post-session summary email for a user of NeuralQuant, an AI-powered stock analysis platform.

The user just finished a {duration_minutes}-minute session. Here is everything they did:

{activity_summary}

Write a warm, personalized "Session Minutes" report in this exact format:

SUBJECT: [Write a short subject line summarizing the session — different every time, never repeat]

BODY:
Start with a warm, personal greeting paragraph (2-3 sentences max). Acknowledge what they focused on. Make them feel seen. Never use the same greeting twice across reports — vary your style each time.

Then a section called "📋 What You Did" with bullet points summarizing the key actions grouped by type. Be specific — name the stocks they looked at, the questions they asked.

Then a section called "💡 Key Insights" — 1-3 sentences about what patterns you noticed in their research.

Then a section called "🔍 Continue Exploring" with 1-2 specific suggestions for what they might want to look at next, based on their activity.

End with a warm, brief sign-off line (different each time).

IMPORTANT RULES:
- NEVER repeat the same greeting or sign-off phrasing across reports
- Be specific and personal — reference actual stocks and questions from the session
- Keep total length under 400 words
- Use plain text with minimal markdown (just bold headers with **)
- No emoji in headers, use the provided section titles exactly
- Sound like a thoughtful research assistant, not a robot"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            temperature=0.9,  # Higher temp for variety in greetings
            system="You write warm, personalized session summary emails. Every email feels fresh and unique. You never repeat phrases or patterns.",
            messages=[{"role": "user", "content": prompt}],
        )

        full_text = ""
        if hasattr(resp, "content") and resp.content:
            for block in resp.content:
                if hasattr(block, "text"):
                    full_text += block.text

        if not full_text:
            return _fallback_report(user_name, duration_minutes, activity_count)

        # Extract subject (first line, remove SUBJECT: prefix)
        lines = full_text.strip().split("\n")
        subject = "Your NeuralQuant Session Summary"
        body_start = 0

        if lines and lines[0].upper().startswith("SUBJECT:"):
            subject = lines[0].split(":", 1)[1].strip().strip('"')
            body_start = 1

        # Skip blank lines after subject
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1

        body = "\n".join(lines[body_start:]).strip()

        # Summary = first 150 chars of body
        summary = body[:150].strip()
        if len(body) > 150:
            summary += "..."

        return body, summary

    except Exception:
        log.exception("Claude report generation failed, using fallback")
        return _fallback_report(user_name, duration_minutes, activity_count)


def _fallback_report(user_name: str | None, duration_minutes: int, activity_count: int) -> tuple[str, str]:
    """Generate a simple report when Claude is unavailable."""
    greeting_name = user_name or "there"
    body = f"""Hi {greeting_name}!

Thanks for spending {duration_minutes} minutes on NeuralQuant today. You performed {activity_count} actions during this session.

📋 What You Did
• Explored stocks and market data
• Used NeuralQuant analysis tools

💡 Key Insights
• Your research activity helps build a clearer market picture over time.

🔍 Continue Exploring
• Try running PARA-DEBATE on a stock you haven't analyzed yet
• Check the Screener for top-scoring stocks in your preferred sectors

See you next time!
— NeuralQuant"""
    summary = f"{duration_minutes}-minute session with {activity_count} actions"
    return body, summary


def _store_report(session_id: str, user_id: str, report_text: str, summary: str) -> str | None:
    """Store the generated report in session_reports table. Returns report ID."""
    try:
        result = _supabase_rest(
            "session_reports",
            method="POST",
            body=[{
                "session_id": session_id,
                "user_id": user_id,
                "report_text": report_text,
                "summary": summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("id")
        return None
    except Exception:
        log.exception("Failed to store report for session %s", session_id)
        return None


import time as _time


def _send_report_email(to: str, subject: str, html_body: str) -> bool:
    """Send the session report email via Resend with retry.

    Returns True only if the API confirms delivery.
    Returns False on misconfiguration or persistent failure so callers can alert.
    """
    resend = _resend_client()
    if not resend or not os.environ.get("RESEND_API_KEY"):
        log.warning("RESEND_API_KEY not set — cannot send report email: %s -> %s", subject, to)
        return False

    for attempt in range(1, 4):
        try:
            resend.Emails.send({
                "from": RESEND_FROM,
                "to": to,
                "subject": subject,
                "html": html_body,
            })
            log.info("Session report email sent: %s -> %s (attempt %d)", subject, to, attempt)
            return True
        except Exception:
            log.exception("Failed to send session report email to %s (attempt %d)", to, attempt)
            if attempt < 3:
                _time.sleep(2 ** attempt)  # 2s, 4s, then give up
    return False


def _mark_report_sent(report_id: str) -> None:
    """Mark a report as emailed."""
    try:
        _supabase_rest(
            f"session_reports?id=eq.{report_id}",
            method="PATCH",
            body=[{
                "email_sent": True,
                "email_sent_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
    except Exception:
        log.exception("Failed to mark report %s as sent", report_id)


def _build_email_html(report_body: str, user_name: str | None) -> str:
    """Wrap the report body in NeuralQuant-branded HTML."""
    greeting_name = user_name or "there"

    # Convert plain text sections to HTML
    # Split on section headers (lines starting with emoji or bold markers)
    body_html = ""
    for line in report_body.strip().split("\n"):
        line = line.strip()
        if not line:
            body_html += "<br>"
        elif line.startswith("📋") or line.startswith("💡") or line.startswith("🔍") or line.startswith("**"):
            # Section header
            clean = line.replace("**", "")
            body_html += f'<p style="font-size:16px;font-weight:700;margin:20px 0 8px;color:#bdf4ff;">{clean}</p>'
        elif line.startswith("•") or line.startswith("-"):
            body_html += f'<p style="margin:4px 0 4px 16px;font-size:14px;">{line}</p>'
        else:
            body_html += f'<p style="margin:4px 0;font-size:14px;line-height:1.6;">{line}</p>'

    return f"""
    <div style="font-family: system-ui, -apple-system, sans-serif; max-width: 560px;
                margin: 0 auto; background: #0f0f1a; color: #e0e0e0;
                border-radius: 12px; overflow: hidden;">
      <div style="padding: 28px 32px; background: linear-gradient(135deg, #00ffb2 0%, #0a3d2a 100%);
                  color: #050a0f;">
        <h1 style="margin: 0; font-size: 20px; letter-spacing: -0.3px;">NeuralQuant</h1>
        <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.8;">Session Minutes</p>
      </div>
      <div style="padding: 24px 32px;">
        {body_html}
      </div>
      <div style="padding: 20px 32px; border-top: 1px solid #1e1e30;">
        <p style="margin: 0; font-size: 12px; color: #a0a0b0;">
          <a href="{FRONTEND_URL}/dashboard" style="color: #00ffb2;">Dashboard</a>
           · <a href="{FRONTEND_URL}/query" style="color: #00ffb2;">Ask Morgan</a>
           · <a href="{FRONTEND_URL}/screener" style="color: #00ffb2;">Screener</a>
        </p>
        <p style="margin: 8px 0 0; font-size: 11px; color: #606070;">
          You received this because you signed up at neuralquant.co. Session reports help you track your research.
        </p>
      </div>
    </div>
    """


# ── Main entry point ─────────────────────────────────────────────────────

def analyze_and_email(
    session_id: str,
    user_id: str,
    user_email: str,
    user_name: str | None,
    duration_seconds: int,
) -> None:
    """Full pipeline: fetch activities → generate report → store → email."""
    log.info("Starting session analysis for %s (user=%s, duration=%ds)",
             session_id, user_id, duration_seconds)

    activities = _fetch_activities(session_id)
    if not activities:
        log.info("No activities for session %s — skipping report", session_id)
        return

    duration_minutes = max(1, duration_seconds // 60)
    activity_summary = _build_activity_summary(activities, duration_seconds)

    log.info("Generating report for session %s (%d activities, %d min)",
             session_id, len(activities), duration_minutes)

    report_text, summary = _generate_report_via_claude(
        activity_summary, user_name, duration_minutes, len(activities),
    )

    report_id = _store_report(session_id, user_id, report_text, summary)
    log.info("Report stored: %s for session %s", report_id, session_id)

    # Extract subject from report (first meaningful line, or use default)
    subject = f"Your NeuralQuant Session Summary — {duration_minutes}min"
    for line in report_text.strip().split("\n"):
        clean = line.strip()
        if clean and not clean.startswith("**") and not clean.startswith("Hi") and not clean.startswith("Hey") and len(clean) > 10:
            # Use first non-greeting content line as subject material
            pass
        if clean.startswith("SUBJECT:"):
            subject = clean.split(":", 1)[1].strip().strip('"')
            break

    # Build HTML email
    # Strip any SUBJECT: line from body for the email
    email_body = report_text
    if email_body.strip().split("\n")[0].upper().startswith("SUBJECT:"):
        email_body = "\n".join(email_body.strip().split("\n")[1:]).strip()

    html = _build_email_html(email_body, user_name)
    sent = _send_report_email(user_email, subject, html)

    if sent and report_id:
        _mark_report_sent(report_id)
        log.info("Session report emailed to %s for session %s", user_email, session_id)
