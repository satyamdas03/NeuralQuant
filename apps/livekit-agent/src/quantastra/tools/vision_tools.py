"""Vision tools mixin — screen share analysis via Claude Vision."""

from __future__ import annotations

import base64
import json
import logging
import os

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class VisionToolsMixin:
    """Vision tools — analyze shared screen content with Claude Vision."""

    # Set by entrypoint when video track frames arrive
    _latest_frame: bytes | None = None
    _screen_sharing: bool = False

    @function_tool
    async def analyze_screen(self, question: str) -> str:
        """Analyze what the user is sharing on their screen. Use when the user
        says things like 'look at this', 'what do you think of this chart',
        'analyze this data', 'see this stock', or any request to look at
        what's on their screen.

        This sends the current screen frame to Claude Vision for analysis.

        VOICE: Announce "Let me look at what you're sharing..." then describe
        what you see naturally. Don't list technical field names — tell the story
        of what the data shows and what it means for the client.

        Parameters:
            question: What the user wants to know about the shared screen,
                      e.g. 'What does this chart show?' or 'Analyze this spreadsheet'
        """
        if not self._latest_frame:
            return json.dumps({
                "status": "unavailable",
                "reason": "No screen being shared. Ask the client to click 'Share Screen' first."
            })

        try:
            # Frame already JPEG-encoded from VideoStream capture
            img_base64 = base64.b64encode(self._latest_frame).decode("utf-8")

            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                return json.dumps({"status": "error", "reason": "Anthropic API key not configured"})

            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-6",
                        "max_tokens": 1024,
                        "system": "You are QuantAstra's vision system. Analyze the screen content the user is sharing. Be concise and insightful — focus on what matters for an investor or trader. Describe data, charts, trends, numbers clearly. Never use markdown or emoji. Speak like an analyst on a call.",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": img_base64,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": question,
                                    },
                                ],
                            }
                        ],
                    },
                )

                if resp.status_code != 200:
                    log.error("Claude Vision API returned %d: %s", resp.status_code, resp.text[:300])
                    return json.dumps({"status": "error", "reason": f"Vision analysis failed (HTTP {resp.status_code})"})

                data = resp.json()
                analysis = data.get("content", [{}])[0].get("text", "")
                if not analysis:
                    analysis = "I can see the screen but I'm having trouble analyzing it. Could you describe what you're looking at?"

                return json.dumps({"status": "ok", "analysis": analysis})

        except Exception as exc:
            log.error("analyze_screen failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def check_screen_share_status(self) -> str:
        """Check whether the user is currently sharing their screen.
        Use before calling analyze_screen to confirm screen share is active."""
        return json.dumps({
            "status": "ok",
            "screen_sharing": self._screen_sharing,
            "has_frame": self._latest_frame is not None,
        })
