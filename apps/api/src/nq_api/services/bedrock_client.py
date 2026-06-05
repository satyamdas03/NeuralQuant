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


class BedrockClient:
    """
    Drop-in replacement for anthropic.Anthropic().

    All 9 PARA-DEBATE agents + DART routes route through this client
    when USE_BEDROCK=true. Zero other code changes needed.
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
        logger.info(f"BedrockClient initialized in {region}")

    def _resolve_model(self, model: str) -> str:
        """Map Anthropic model names to Bedrock cross-region inference profile IDs."""
        # Pass through if already a cross-region profile (us./apac./global.)
        if model.startswith(("us.", "apac.", "global.", "eu.")):
            return model
        # Strip version suffixes for lookup
        base = model.split("-20")[0] if "-20" in model else model
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

        response = self.client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        return _BedrockResponse(result)

    async def create_message_async(self, **kwargs) -> _BedrockResponse:
        """Async wrapper using asyncio.to_thread for non-blocking calls."""
        return await asyncio.to_thread(self.create_message, **kwargs)

    def stream_message(
        self,
        messages: list[dict],
        system: str = "",
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """
        Streaming call via Bedrock InvokeModelWithResponseStream.
        Yields text chunks matching the Anthropic stream format.
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

        response = self.client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        for event in response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                yield delta.get("text", "")


# Singleton — imported everywhere
bedrock = BedrockClient()
