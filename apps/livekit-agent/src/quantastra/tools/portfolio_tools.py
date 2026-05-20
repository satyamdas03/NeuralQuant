"""Portfolio management tools mixin — holdings lookup, analysis."""

from __future__ import annotations

import json
import logging

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class PortfolioToolsMixin:
    """Portfolio management tools — holdings lookup, analysis, price validation."""

    @function_tool
    async def lookup_portfolio(self, user_id: str) -> str:
        """Look up the client's current portfolio holdings. Returns every position with
        ticker, allocation percentage, entry price, target price, and stop loss.

        ALWAYS call this first when a client asks about their portfolio, holdings,
        performance, or asks 'how am I doing?'

        Parameters:
            user_id: The client's Supabase user ID (provided at session start)
        """
        if not user_id or user_id == "anonymous":
            return json.dumps({
                "status": "no_portfolio",
                "message": (
                    "You're not logged in, so I don't have access to your portfolio. "
                    "You can ask me about specific stocks, market conditions, or investment ideas though — "
                    "or sign in to connect your portfolio for personalized analysis."
                ),
            })

        try:
            from nq_api.services.portfolio import _load_portfolio_from_supabase, _validate_and_fill_portfolio_prices

            stocks = await _load_portfolio_from_supabase(user_id)
            if not stocks:
                return json.dumps({
                    "status": "empty",
                    "message": (
                        "I don't see any stocks in your portfolio yet. Would you like me to help you "
                        "build one based on our top AI-ranked picks? I can screen for stocks matching "
                        "your risk profile and goals."
                    ),
                })

            from nq_api.services.portfolio import _infer_portfolio_market
            market = _infer_portfolio_market(stocks, None)
            filled, notes = _validate_and_fill_portfolio_prices(stocks, market)

            position_details = []
            for s in filled:
                position_details.append({
                    "ticker": s.get("ticker", ""),
                    "name": s.get("name", ""),
                    "allocation_pct": float(s.get("allocation_pct", 0)),
                    "entry_price": s.get("entry_price", "unknown"),
                    "target_price": s.get("target_price", "unknown"),
                    "stop_loss": s.get("stop_loss", "unknown"),
                    "sector": s.get("sector", ""),
                })

            return json.dumps({
                "status": "ok",
                "market": market,
                "total_positions": len(filled),
                "total_allocation_pct": round(sum(float(s.get("allocation_pct", 0)) for s in filled), 1),
                "stocks": position_details,
                "fill_notes": notes if notes else [],
            }, default=str)
        except Exception as exc:
            log.error("lookup_portfolio failed for user %s: %s", user_id, exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def analyze_holdings(
        self,
        tickers: list[str],
        market: str = "US",
    ) -> str:
        """Analyze a list of portfolio holdings with live prices and AI scores.
        Returns current price, score, percentiles, and a summary of which positions
        are strong vs weak.

        Use after lookup_portfolio to get deeper analysis, or when a client lists
        their holdings manually in conversation.

        Parameters:
            tickers: List of stock ticker symbols, e.g. ['NVDA', 'AAPL', 'RELIANCE']
            market: Market — 'US' or 'IN'
        """
        try:
            import asyncio
            from nq_api.data_builder import _fetch_one
            from nq_api.cache.score_cache import read_enrichment

            async def _analyze_one(ticker: str):
                row = _fetch_one(ticker, market, fast_pe=True)
                enrichment = read_enrichment(ticker, market) or {}
                if row is None:
                    return {"ticker": ticker, "status": "unavailable"}
                return {
                    "ticker": ticker,
                    "status": "ok",
                    "current_price": row.get("current_price"),
                    "pe_ttm": row.get("pe_ttm"),
                    "beta": row.get("beta"),
                    "composite_score": row.get("composite_score"),
                    "momentum_percentile": row.get("momentum_percentile"),
                    "quality_percentile": row.get("quality_percentile"),
                    "value_percentile": row.get("value_percentile"),
                    "sector": row.get("sector", ""),
                    "rsi_14": enrichment.get("rsi_14"),
                    "analyst_target": row.get("analyst_target"),
                }

            tasks = [_analyze_one(t) for t in tickers]
            results = await asyncio.gather(*tasks)

            strong = [r for r in results if r.get("composite_score", 0) and r["composite_score"] >= 7]
            weak = [r for r in results if r.get("composite_score", 0) and r["composite_score"] < 5]

            return json.dumps({
                "status": "ok",
                "market": market,
                "holdings": [r for r in results],
                "summary": {
                    "total": len(results),
                    "strong_positions": len(strong),
                    "weak_positions": len(weak),
                    "strong_tickers": [r["ticker"] for r in strong],
                    "weak_tickers": [r["ticker"] for r in weak],
                },
            }, default=str)
        except Exception as exc:
            log.error("analyze_holdings failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})
