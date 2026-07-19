"""Reusable cron invoker for Render cron jobs.

Posts to https://neuralquant.onrender.com/{endpoint} with the CRON_SECRET
as a Bearer token. Retries on 5xx, timeout, or network errors with exponential
backoff. Exits non-zero on final failure so Render marks the cron run failed.

Usage:
  uv run python scripts/cron_invoke.py --endpoint /cron/market-refresh
  uv run python scripts/cron_invoke.py --endpoint /cron/market-wrap --params "market=US"
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx


DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 2
BASE_URL = "https://neuralquant.onrender.com"


class CronInvokeError(Exception):
    """Raised when the cron invocation ultimately fails."""


def invoke(
    endpoint: str,
    params: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> tuple[int, str]:
    """POST to the cron endpoint and return (status_code, text_preview)."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        raise CronInvokeError("CRON_SECRET environment variable is not set")

    path = endpoint.lstrip("/")
    url = f"{BASE_URL}/{path}"

    query: dict[str, list[str]] = {}
    if params:
        parsed = urlparse(f"?{params}")
        query = {k: v for k, v in parse_qs(parsed.query).items()}

    headers = {"Authorization": f"Bearer {secret}"}

    last_status = 0
    last_text = ""
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, params=query, headers=headers)
            last_status = r.status_code
            last_text = r.text[:200]
            if r.status_code < 500:
                return last_status, last_text
            # 5xx responses are retried below
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
            last_exc = exc
            last_status = 0
            last_text = f"{type(exc).__name__}: {exc}"
        except httpx.HTTPError as exc:
            # Other HTTP errors (e.g. invalid URL) are not retried
            raise CronInvokeError(f"HTTP error: {exc}") from exc

        if attempt < retries:
            backoff = 2 ** attempt
            print(f"[cron_invoke] attempt {attempt + 1} failed ({last_status}), retrying in {backoff}s...")
            time.sleep(backoff)

    if last_exc is not None:
        raise CronInvokeError(f"Network/timeout error after {retries + 1} attempts: {last_text}")
    raise CronInvokeError(f"HTTP {last_status} after {retries + 1} attempts: {last_text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Invoke a NeuralQuant cron endpoint")
    parser.add_argument("--endpoint", required=True, help="Cron endpoint path, e.g. /cron/market-refresh")
    parser.add_argument("--params", default=None, help="Optional query string, e.g. market=US")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Number of retries (default {DEFAULT_RETRIES})")
    args = parser.parse_args(argv)

    try:
        status, text = invoke(args.endpoint, args.params, args.timeout, args.retries)
    except CronInvokeError as exc:
        print(f"[cron_invoke] ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"[cron_invoke] {status} {text[:200]}")
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
