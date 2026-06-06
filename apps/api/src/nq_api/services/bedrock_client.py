"""
AWS Bedrock client — drop-in replacement for anthropic.Anthropic.
Routes all Claude calls through Amazon Bedrock via cross-region inference profiles.
Activated by USE_BEDROCK=true env var. Zero other code changes needed.

Cross-region inference profiles are required for newer Claude models (4.x+).
Direct model IDs (anthropic.claude-*) do not support on-demand invocation for
these models — only INFERENCE_PROFILE type is available.
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError as BotoClientError, ConnectionError as BotoConnectionError

logger = logging.getLogger(__name__)

# Bedrock cross-region inference profile IDs
# These are the ONLY way to invoke newer Claude models on Bedrock.
# Format: {region_prefix}.anthropic.{model-version}
# See: https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html
BEDROCK_MODEL_MAP = {
    # Sonnet 4.6 (primary — matches current anthropic_helpers MODEL default)
    "claude-sonnet-4-6": "us.anthropic.claude-sonnet-4-6",
    # Sonnet 4.5
    "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Haiku 4.5 (low-latency fallback)
    "claude-haiku-4-5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    # Claude 3.7 Sonnet (APAC — Mumbai data residency)
    "claude-3-7-sonnet": "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
}

# Default region for the Bedrock runtime client
# us-east-1 for US cross-region profiles, ap-south-1 for APAC
BEDROCK_RUNTIME_REGION = os.getenv("BEDROCK_RUNTIME_REGION", "us-east-1")


class _BedrockContent:
    """Adapter: Bedrock content → Anthropic SDK format."""
    def __init__(self, raw: dict):
        self.text = raw.get("text", "")
        self.type = raw.get("type", "text")


class _BedrockUsage:
    """Adapter: Bedrock usage → Anthropic SDK format."""
    def __init__(self, raw: dict):
        self.input_tokens = raw.get("input_tokens", 0)
        self.output_tokens = raw.get("output_tokens", 0)


class _BedrockResponse:
    """Adapter: Bedrock response → Anthropic SDK format."""
    def __init__(self, raw: dict):
        self._raw = raw
        self.content = [_BedrockContent(c) for c in raw.get("content", [])]
        self.usage = _BedrockUsage(raw.get("usage", {}))
        self.stop_reason = raw.get("stop_reason", "end_turn")
        self.model = raw.get("model", "")


class _BedrockMessages:
    """Adapter that provides .messages.create() interface matching anthropic.Anthropic.

    Every call site in the codebase uses client.messages.create(**kwargs).
    This adapter bridges the gap so BedrockClient can be a true drop-in replacement.
    """

    def __init__(self, client: "BedrockClient"):
        self._client = client

    def create(self, **kwargs) -> _BedrockResponse:
        """Synchronous create — matches anthropic.Anthropic().messages.create()."""
        # Extract params from Anthropic SDK keyword args
        messages = kwargs.get("messages", [])
        system = kwargs.get("system", "")
        if isinstance(system, list):
            # Anthropic SDK sometimes passes system as list of dicts
            system = "\n".join(s.get("text", "") for s in system if isinstance(s, dict))
        model = kwargs.get("model", "claude-sonnet-4-6")
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.3)
        # tools/tool_choice not supported yet via Bedrock — log warning
        if kwargs.get("tools"):
            logger.warning("Bedrock adapter: tools not yet supported, ignoring")
        return self._client.create_message(
            messages=messages,
            system=system,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def stream(self, **kwargs):
        """Async streaming — matches anthropic.Anthropic().messages.stream()."""
        messages = kwargs.get("messages", [])
        system = kwargs.get("system", "")
        if isinstance(system, list):
            system = "\n".join(s.get("text", "") for s in system if isinstance(s, dict))
        model = kwargs.get("model", "claude-sonnet-4-6")
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.3)

        # Run sync stream in thread pool
        def _sync_stream():
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                body["system"] = system
            model_id = self._client._resolve_model(model)
            response = self._client.client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            chunks = []
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        chunks.append(text)
            full_text = "".join(chunks)
            return _BedrockResponse({
                "content": [{"text": full_text, "type": "text"}],
                "usage": {},
                "stop_reason": "end_turn",
                "model": model_id,
            })

        return await asyncio.to_thread(_sync_stream)


class BedrockClient:
    """
    Drop-in replacement for anthropic.Anthropic().

    All 9 PARA-DEBATE agents + DART routes route through this client
    when USE_BEDROCK=true. Zero other code changes needed.

    Provides .messages.create() interface matching the Anthropic SDK.
    """

    def __init__(self):
        region = BEDROCK_RUNTIME_REGION
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            config=BotoConfig(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=120,
            ),
        )
        # Expose .messages.create() for drop-in compatibility with anthropic.Anthropic
        self.messages = _BedrockMessages(self)
        logger.info(f"BedrockClient initialized in {region}")

    def _resolve_model(self, model: str) -> str:
        """Map Anthropic model names to Bedrock cross-region inference profile IDs."""
        # Pass through if already a cross-region profile (us./apac./global.)
        if model.startswith(("us.", "apac.", "global.", "eu.", "au.", "jp.")):
            return model
        # Strip version suffixes for lookup (e.g. "claude-sonnet-4-5-20250929-v1:0" → "claude-sonnet-4-5")
        import re
        base = re.sub(r"-20\d{6}-v\d+.*$", "", model).rstrip("-")
        bedrock_id = BEDROCK_MODEL_MAP.get(base) or BEDROCK_MODEL_MAP.get(model)
        if not bedrock_id:
            logger.warning(f"Unknown model {model}, using sonnet-4-6 as fallback")
            bedrock_id = BEDROCK_MODEL_MAP["claude-sonnet-4-6"]
        return bedrock_id

    def create_message(
        self,
        messages: list[dict],
        system: str = "",
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs,
    ) -> _BedrockResponse:
        """
        Synchronous call — matches anthropic.messages.create() signature.
        Returns a response dict with .content[0].text accessible pattern.
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system

        model_id = self._resolve_model(model)
        logger.debug(f"Bedrock invoke: model={model_id}, max_tokens={max_tokens}")

        try:
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return _BedrockResponse(result)
        except BotoClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Bedrock invoke error: {error_code} — {e}")
            raise
        except BotoConnectionError as e:
            logger.error(f"Bedrock connection error: {e}")
            raise

    async def create_message_async(self, **kwargs) -> _BedrockResponse:
        """Async wrapper using asyncio.to_thread for non-blocking calls."""
        return await asyncio.to_thread(self.create_message, **kwargs)


# Singleton — imported everywhere
bedrock = BedrockClient()