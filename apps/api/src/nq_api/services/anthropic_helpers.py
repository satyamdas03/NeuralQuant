"""Anthropic API client creation and call wrappers with retry logic."""
import asyncio
import os
import logging

import anthropic
from botocore.exceptions import ClientError as BotoClientError, ConnectionError as BotoConnectionError

from nq_api.services.constants import MODEL, _CLOUD_MODEL, USE_BEDROCK

if USE_BEDROCK:
    from nq_api.services.bedrock_client import bedrock

log = logging.getLogger(__name__)


def _is_ollama_proxy() -> bool:
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


def _query_client(api_key: str, timeout: float = 120.0) -> tuple[anthropic.Anthropic, str]:
    """Create Anthropic client for Ask AI -- bypasses Ollama proxy for speed.

    Returns (client, model_name) tuple.
    """
    if USE_BEDROCK:
        # Route through AWS Bedrock — zero other code changes needed
        log.info("Using AWS Bedrock for inference")
        return bedrock, _CLOUD_MODEL
    if _is_ollama_proxy():
        saved = os.environ.pop("ANTHROPIC_BASE_URL", None)
        try:
            c = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        finally:
            if saved:
                os.environ["ANTHROPIC_BASE_URL"] = saved
        return c, _CLOUD_MODEL
    return anthropic.Anthropic(api_key=api_key, timeout=timeout), MODEL


async def _call_anthropic_with_retry(client, *, model: str, max_tokens: int, system: str, messages: list, tools: list | None = None, tool_choice: dict | None = None, timeout: float = 90.0):
    """Call Anthropic API with exponential-backoff retry on 5xx / connection / rate-limit errors.

    Handles both Anthropic SDK exceptions and Bedrock/botocore exceptions.
    """
    kwargs: dict = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    last_exc = None
    for attempt in range(3):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(client.messages.create, **kwargs),
                timeout=timeout,
            )
        except anthropic.APIError as e:
            status = getattr(e, "status_code", None)
            if status and 500 <= status < 600:
                last_exc = e
                wait = 2 ** attempt
                log.warning("Anthropic API error %s (attempt %d/3), retrying in %ds...", status, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            raise
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            last_exc = e
            wait = 2 ** attempt
            log.warning("Anthropic connection/rate error (attempt %d/3), retrying in %ds...", attempt + 1, wait)
            await asyncio.sleep(wait)
            continue
        except (BotoClientError, BotoConnectionError) as e:
            last_exc = e
            wait = 2 ** attempt
            log.warning("Bedrock error (attempt %d/3), retrying in %ds... %s", attempt + 1, wait, e)
            await asyncio.sleep(wait)
            continue
    raise last_exc
