"""LiveKit function-calling tools for stock screening."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from livekit.agents import llm

log = logging.getLogger(__name__)


class ScreenerTools(llm.FunctionContext):
    """Stock screening tools — find stocks by criteria, peer comparison."""

    @llm.ai_callable(
        description=(
            "Screen for stocks matching specific criteria using NeuralQuant's AI scores. "
            "Filter by minimum momentum percentile, minimum quality percentile, value percentile, "
            "and market. Returns ranked results with scores and key metrics. "
            "Use when client asks 'find me stocks with strong momentum and quality' or "
            "'what are the best value stocks right now?'"
        ),
    )
    async def run_screener(
        self,
        market: Annotated[
            str,
            llm.TypeInfo(description="Market: 'US' or 'IN'"),
        ] = "US",
        min_momentum_percentile: Annotated[
            float,
            llm.TypeInfo(description="Minimum momentum percentile 0.0-1.0. Default 0.7 (top 30%)"),
        ] = 0.7,
        min_quality_percentile: Annotated[
            float,
            llm.TypeInfo(description="Minimum quality percentile 0.0-1.0. Default 0.5"),
        ] = 0.5,
        min_value_percentile: Annotated[
            float,
            llm.TypeInfo(description="Minimum value percentile 0.0-1.0. Default 0.0 (no filter)"),
        ] = 0.0,
        n: Annotated[
            int,
            llm.TypeInfo(description="Maximum number of results (max 20)"),
        ] = 10,
    ) -> str:
        """Run a screener query against score_cache."""
        try:
            from nq_api.cache.score_cache import read_top

            # Fetch top 100 and filter locally
            all_results = read_top(market, 100)
            if not all_results:
                return json.dumps({"status": "unavailable", "reason": "Score data temporarily unavailable — scores are refreshed nightly"})

            filtered = []
            for r in all_results:
                if len(filtered) >= n:
                    break
                momentum = float(r.get("momentum_percentile", 0) or 0)
                quality = float(r.get("quality_percentile", 0) or 0)
                value = float(r.get("value_percentile", 0) or 0)
                if momentum >= min_momentum_percentile and quality >= min_quality_percentile and value >= min_value_percentile:
                    filtered.append({
                        "ticker": r["ticker"],
                        "score_1_10": r["score_1_10"],
                        "momentum_percentile": momentum,
                        "quality_percentile": quality,
                        "value_percentile": value,
                        "low_vol_percentile": float(r.get("low_vol_percentile", 0) or 0),
                        "pe_ttm": r.get("pe_ttm"),
                        "sector": r.get("sector", ""),
                        "market_cap": r.get("market_cap"),
                    })

            return json.dumps({
                "status": "ok",
                "market": market,
                "criteria": {
                    "min_momentum": min_momentum_percentile,
                    "min_quality": min_quality_percentile,
                    "min_value": min_value_percentile,
                },
                "count": len(filtered),
                "results": filtered,
            }, default=str)
        except Exception as exc:
            log.error("run_screener failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @llm.ai_callable(
        description=(
            "Find peer/similar stocks to a given ticker. Returns stocks in the same sector "
            "with similar scores for comparison. Use when client asks 'what are NVDA's competitors?' "
            "or 'how does X compare to its peers?'"
        ),
    )
    async def find_similar(
        self,
        ticker: Annotated[
            str,
            llm.TypeInfo(description="Reference stock ticker, e.g. 'AAPL' or 'TCS'"),
        ],
        market: Annotated[
            str,
            llm.TypeInfo(description="Market: 'US' or 'IN'"),
        ] = "US",
    ) -> str:
        """Find similar stocks by sector and score proximity."""
        try:
            from nq_api.data_builder import _fetch_one
            from nq_api.cache.score_cache import read_top

            # Get target stock info
            target = _fetch_one(ticker, market, fast_pe=True)
            if target is None:
                return json.dumps({"status": "unavailable", "ticker": ticker, "reason": "Could not fetch data for this stock"})

            target_sector = target.get("sector", "")
            target_score = float(target.get("composite_score", 0) or 0)

            # Get top 50 in the market and filter by sector
            all_results = read_top(market, 50)
            peers = []
            for r in all_results:
                if r["ticker"].upper() == ticker.upper():
                    continue
                if r.get("sector") == target_sector:
                    score_diff = abs(float(r.get("score_1_10", 0) or 0) - target_score)
                    peers.append({
                        "ticker": r["ticker"],
                        "score_1_10": r["score_1_10"],
                        "score_diff": round(score_diff, 1),
                        "pe_ttm": r.get("pe_ttm"),
                        "sector": r.get("sector", target_sector),
                        "momentum_percentile": r.get("momentum_percentile"),
                        "quality_percentile": r.get("quality_percentile"),
                    })

            # Sort by score proximity
            peers.sort(key=lambda p: p["score_diff"])
            peers = peers[:8]

            return json.dumps({
                "status": "ok",
                "reference": {
                    "ticker": ticker,
                    "score_1_10": target_score,
                    "sector": target_sector,
                    "pe_ttm": target.get("pe_ttm"),
                },
                "peers": peers,
            }, default=str)
        except Exception as exc:
            log.error("find_similar failed for %s: %s", ticker, exc)
            return json.dumps({"status": "error", "reason": str(exc)})
