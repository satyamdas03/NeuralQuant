"""Upload tools mixin — user-uploaded file analysis via Claude Vision or text processing."""

from __future__ import annotations

import base64
import json
import logging
import os

from livekit.agents import function_tool

log = logging.getLogger(__name__)

# File types that can be analyzed as images (send to Claude Vision)
_IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf",
}

# File types that can be read as text directly
_TEXT_MIMES = {
    "text/plain", "text/csv", "application/json",
    "text/html", "text/markdown", "text/xml",
    "application/xml",
}


class UploadToolsMixin:
    """Upload tools — analyze files the user uploads through the frontend.

    The frontend reads uploaded files as base64 and sends them via
    the LiveKit data channel. This mixin stores them and provides tools
    for the agent to analyze the content.
    """

    _uploaded_files: list[dict] = []

    def _add_upload(self, file_name: str, mime_type: str, data_b64: str, size: int) -> str:
        """Add an uploaded file to our store. Called from data channel handler."""
        file_id = f"file_{len(self._uploaded_files) + 1}"
        self._uploaded_files.append({
            "id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "data_b64": data_b64,
            "size": size,
        })
        log.info("UploadToolsMixin: stored %s (%s, %d bytes)", file_name, mime_type, size)
        return file_id

    @function_tool
    async def analyze_upload(self, question: str) -> str:
        """Analyze a file the user uploaded. Use when the user says things like
        'look at this', 'analyze this data', 'what do you think of this chart',
        'check this spreadsheet', 'review this report', or any request to look
        at something they've uploaded.

        This sends the uploaded file content to Claude for analysis. Works with
        images (PNG, JPEG, GIF, WebP), PDFs, CSVs, text files, JSON, and more.

        VOICE: Announce "Let me look at what you uploaded..." then describe what
        you see naturally. Don't list technical field names — tell the story of
        what the data shows and what it means for the client.

        Parameters:
            question: What the user wants to know about the uploaded file,
                      e.g. 'What does this chart show?' or 'Summarize this report'
        """
        if not self._uploaded_files:
            return json.dumps({
                "status": "unavailable",
                "reason": "No files uploaded yet. Ask the client to upload a file first — they can upload images, PDFs, spreadsheets, or text documents."
            })

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return json.dumps({"status": "error", "reason": "Anthropic API key not configured"})

        # Use the most recently uploaded file
        latest = self._uploaded_files[-1]
        mime_type = latest["mime_type"]
        file_name = latest["file_name"]

        try:
            import httpx

            is_image = mime_type in _IMAGE_MIMES or mime_type.startswith("image/")
            is_text = mime_type in _TEXT_MIMES or mime_type.startswith("text/")

            if is_image:
                # Send to Claude Vision
                media_type = mime_type if mime_type in _IMAGE_MIMES else "image/png"
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-6",
                            "max_tokens": 2048,
                            "system": "You are QuantAstra's document analysis system. Analyze the file the user uploaded. Be concise and insightful — focus on what matters for an investor or trader. Describe data, charts, trends, numbers clearly. Never use markdown or emoji. Speak like an analyst on a call.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type,
                                                "data": latest["data_b64"],
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
            elif is_text:
                # Decode and send as text
                text_bytes = base64.b64decode(latest["data_b64"])
                file_text = text_bytes.decode("utf-8", errors="replace")[:50000]

                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-6",
                            "max_tokens": 2048,
                            "system": f"You are QuantAstra's data analysis system. The user uploaded a file named '{file_name}' ({mime_type}). Analyze it and answer their question. Focus on insights relevant to an investor or trader. Never use markdown or emoji. Be concise but thorough.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": f"File '{file_name}' contents:\n\n{file_text}\n\n---\n\nQuestion: {question}",
                                },
                            ],
                        },
                    )
            else:
                return json.dumps({
                    "status": "error",
                    "reason": f"Unsupported file type: {mime_type}. Supported formats: images, PDFs, text files, CSVs, JSON."
                })

            if resp.status_code != 200:
                log.error("Claude API returned %d: %s", resp.status_code, resp.text[:300])
                return json.dumps({"status": "error", "reason": f"Analysis failed (HTTP {resp.status_code})"})

            data = resp.json()
            analysis = data.get("content", [{}])[0].get("text", "")
            if not analysis:
                analysis = "I can see the file but I'm having trouble analyzing it. Could you describe what you're looking at?"

            return json.dumps({"status": "ok", "file_name": file_name, "analysis": analysis})

        except Exception as exc:
            log.error("analyze_upload failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def check_uploads_status(self) -> str:
        """Check what files the user has uploaded so far.
        Use before calling analyze_upload to confirm files are available."""
        if not self._uploaded_files:
            return json.dumps({
                "status": "ok",
                "files_available": 0,
            })
        return json.dumps({
            "status": "ok",
            "files_available": len(self._uploaded_files),
            "files": [
                {"name": f["file_name"], "type": f["mime_type"], "size": f["size"]}
                for f in self._uploaded_files[-5:]  # last 5
            ],
        })

    @function_tool
    async def clear_uploads(self) -> str:
        """Clear all previously uploaded files. Use when the user wants to
        start fresh with new uploads. Call close_whiteboard if whiteboard is open."""
        count = len(self._uploaded_files)
        self._uploaded_files.clear()
        return json.dumps({"status": "ok", "cleared": count})
