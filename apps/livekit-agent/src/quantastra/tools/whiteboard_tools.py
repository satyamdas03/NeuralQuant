"""Whiteboard tools mixin — show calculations and visual explanations."""

from __future__ import annotations

import asyncio
import json
import logging

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class WhiteboardToolsMixin:
    """Whiteboard tools — visual calculations, projections, and explanations."""

    @function_tool
    async def show_calculation(
        self,
        title: str,
        steps: str,
        result: str,
        description: str = "",
        currency: str = "$",
        disclaimer: str = "This is a projection, not financial advice. Past performance does not guarantee future results.",
    ) -> str:
        """Show a step-by-step calculation on the QuantAstra whiteboard.

        Use this when the client asks ANY question involving math, projections,
        or calculations — investment returns, compounding, SIP growth, CAGR,
        portfolio allocation percentages, tax calculations, etc.

        Seeing calculations step-by-step builds trust and shows your work.
        Announce "Let me work this out on the whiteboard" before calling.

        Parameters:
            title: Short title for the calculation, e.g. "TCS 5-Year Return Projection"
            steps: JSON array of calculation steps. Each step has:
                   {"label": "What this step does", "formula": "Math formula (optional)",
                    "value": "Calculated result (optional)"}
                   Example: [{"label":"Initial investment","value":"₹10,00,000"},
                             {"label":"Annual return rate","value":"12%"},
                             {"label":"Year 1 growth","formula":"₹10,00,000 × 1.12","value":"₹11,20,000"}]
            result: Final answer, e.g. "₹17,62,342 — a 76.2% total return over 5 years"
            description: One-line explanation of what we're calculating (optional)
            currency: Currency symbol — "$" for US, "₹" for India (default "$")
            disclaimer: Custom disclaimer or use default
        """
        try:
            steps_data = json.loads(steps) if isinstance(steps, str) else steps
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"status": "error", "reason": "steps must be valid JSON array"})

        payload = {
            "type": "whiteboard_update",
            "action": "show",
            "content": {
                "title": title,
                "description": description,
                "steps": steps_data,
                "result": result,
                "currency": currency,
                "disclaimer": disclaimer,
            },
        }

        # Publish to frontend via data channel
        participant = getattr(self, "_participant", None)
        if participant:
            try:
                await participant.publish_data(
                    json.dumps(payload), reliable=True, topic="quantastra"
                )
            except Exception:
                log.debug("Failed to publish whiteboard update", exc_info=True)

        return json.dumps({"status": "ok", "title": title, "steps_count": len(steps_data)})

    @function_tool
    async def close_whiteboard(self) -> str:
        """Close/hide the whiteboard when the calculation is complete and
        the client is ready to move on. Also use when the client says
        'close the whiteboard' or 'that's enough'."""
        participant = getattr(self, "_participant", None)
        if participant:
            try:
                await participant.publish_data(
                    json.dumps({"type": "whiteboard_update", "action": "close"}),
                    reliable=True,
                    topic="quantastra",
                )
            except Exception:
                log.debug("Failed to publish whiteboard close", exc_info=True)

        return json.dumps({"status": "ok", "action": "closed"})
