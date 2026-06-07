"""Portfolio management tools mixin — holdings lookup, analysis, IRS scan, sell signals, risk profile."""

from __future__ import annotations

import json
import logging

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class PortfolioToolsMixin:
    """Portfolio management tools — holdings lookup, analysis, IRS scan, sell signals, risk profile."""

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
            from nq_api.services.portfolio import _load_portfolio_from_supabase

            stocks = await _load_portfolio_from_supabase(user_id)
            if not stocks:
                return json.dumps({
                    "status": "empty",
                    "message": (
                        "I don't see any stocks in your watchlist yet. Would you like me to help you "
                        "build one based on our top AI-ranked picks? I can screen for stocks matching "
                        "your risk profile and goals."
                    ),
                })

            # Enrich watchlist items with live data
            from nq_api.services.portfolio import _infer_portfolio_market
            from nq_api.data_builder import _fetch_one
            import asyncio

            market = _infer_portfolio_market(stocks, None)

            async def _enrich_one(s):
                ticker = s["ticker"]
                mkt = s.get("market", market)
                row = _fetch_one(ticker, mkt, fast_pe=True)
                if row is None:
                    return {
                        "ticker": ticker,
                        "market": mkt,
                        "status": "unavailable",
                    }
                return {
                    "ticker": ticker,
                    "name": row.get("name", ""),
                    "market": mkt,
                    "current_price": row.get("current_price"),
                    "pe_ttm": row.get("pe_ttm"),
                    "beta": row.get("beta"),
                    "composite_score": row.get("composite_score"),
                    "sector": row.get("sector", ""),
                    "status": "ok",
                }

            enriched = await asyncio.gather(*[_enrich_one(s) for s in stocks])

            return json.dumps({
                "status": "ok",
                "market": market,
                "total_positions": len(enriched),
                "stocks": [r for r in enriched if r.get("status") == "ok"],
                "unavailable": [r["ticker"] for r in enriched if r.get("status") != "ok"],
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

    @function_tool
    async def assess_portfolio_irs(self, user_id: str) -> str:
        """Assess the client's portfolio using Investment Readiness Score (IRS%).

        Returns IRS% for each holding plus portfolio-level aggregate.
        Flags sell signals (G Score < -4 or Risk < -3.5).

        ALWAYS use this when a client asks "how is my portfolio doing?" or
        "should I sell anything?"

        Parameters:
            user_id: The client's Supabase user ID
        """
        if not user_id or user_id == "anonymous":
            return json.dumps({"status": "no_portfolio", "message": "Sign in to get IRS portfolio assessment."})

        try:
            from nq_api.cache.score_cache import _supabase_rest

            # Get user's watchlist
            wl = _supabase_rest(
                f"watchlists?user_id=eq.{user_id}&select=ticker,market&limit=50",
                method="GET",
            )
            if not wl:
                return json.dumps({"status": "empty", "message": "No stocks in portfolio to assess."})

            tickers = [(s["ticker"], s.get("market", "US")) for s in wl]

            # Fetch IRS data from anjali_enrichment
            holdings = []
            sell_signals = []
            for ticker, market in tickers:
                rows = _supabase_rest(
                    f"anjali_enrichment?ticker=eq.{ticker}&market=eq.{market}"
                    f"&select=ticker,name,irs_pct,g_score,risk_eff_score,sector,composite_anjali_score",
                    method="GET",
                )
                if not rows:
                    holdings.append({"ticker": ticker, "market": market, "irs_status": "no_data"})
                    continue
                r = rows[0]
                irs_pct = float(r.get("irs_pct") or 0)
                g_score = float(r.get("g_score") or 0)
                risk_eff = float(r.get("risk_eff_score") or 0)
                is_sell = g_score < -4.0 or risk_eff < -3.5
                entry = {
                    "ticker": r.get("ticker"),
                    "name": r.get("name", ""),
                    "irs_pct": round(irs_pct, 1),
                    "g_score": round(g_score, 1),
                    "risk_eff_score": round(risk_eff, 1),
                    "composite_score": r.get("composite_anjali_score"),
                    "sector": r.get("sector", ""),
                    "zone": "STRONG BUY" if irs_pct > 65 else "MODERATE" if irs_pct > 45 else "WEAK" if irs_pct > 30 else "VERY WEAK",
                    "sell_signal": is_sell,
                }
                holdings.append(entry)
                if is_sell:
                    sell_signals.append({
                        "ticker": r.get("ticker"),
                        "reason": f"G Score {g_score:.1f}" if g_score < -4.0 else f"Risk Eff {risk_eff:.1f}",
                    })

            # Portfolio aggregate
            irs_values = [h["irs_pct"] for h in holdings if h.get("irs_pct")]
            avg_irs = round(sum(irs_values) / len(irs_values), 1) if irs_values else None

            return json.dumps({
                "status": "ok",
                "holdings": holdings,
                "portfolio_irs_avg": avg_irs,
                "sell_signals": sell_signals,
                "sell_count": len(sell_signals),
            }, default=str)
        except Exception as exc:
            log.error("assess_portfolio_irs failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_sell_signals(self, user_id: str) -> str:
        """Get hard sell signals for the client's portfolio.

        HARD SELL TRIGGERS: G Score < -4 OR Risk Efficiency Score < -3.5.
        NEUTRAL ZONE: G Score < -0.5 (never recommend as buy, but not sell yet).

        Use proactively when starting a session with a portfolio-holding client.

        Parameters:
            user_id: The client's Supabase user ID
        """
        if not user_id or user_id == "anonymous":
            return json.dumps({"status": "no_portfolio", "message": "Sign in to check sell signals."})

        try:
            from nq_api.cache.score_cache import _supabase_rest

            wl = _supabase_rest(
                f"watchlists?user_id=eq.{user_id}&select=ticker,market&limit=50",
                method="GET",
            )
            if not wl:
                return json.dumps({"status": "empty", "sell_signals": [], "neutral_zone": []})

            hard_sell = []
            neutral_zone = []
            for s in wl:
                rows = _supabase_rest(
                    f"anjali_enrichment?ticker=eq.{s['ticker']}&market=eq.{s.get('market', 'US')}"
                    f"&select=ticker,name,g_score,risk_eff_score,irs_pct",
                    method="GET",
                )
                if not rows:
                    continue
                r = rows[0]
                g = float(r.get("g_score") or 0)
                re = float(r.get("risk_eff_score") or 0)
                if g < -4.0 or re < -3.5:
                    hard_sell.append({
                        "ticker": r.get("ticker"),
                        "name": r.get("name", ""),
                        "g_score": round(g, 1),
                        "risk_eff_score": round(re, 1),
                        "irs_pct": round(float(r.get("irs_pct") or 0), 1),
                        "trigger": "G Score < -4" if g < -4.0 else "Risk Eff < -3.5",
                    })
                elif g < -0.5:
                    neutral_zone.append({
                        "ticker": r.get("ticker"),
                        "name": r.get("name", ""),
                        "g_score": round(g, 1),
                        "irs_pct": round(float(r.get("irs_pct") or 0), 1),
                    })

            return json.dumps({
                "status": "ok",
                "hard_sell": hard_sell,
                "neutral_zone": neutral_zone,
                "hard_sell_count": len(hard_sell),
                "neutral_count": len(neutral_zone),
            }, default=str)
        except Exception as exc:
            log.error("get_sell_signals failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def manage_risk_profile(
        self,
        user_id: str,
        action: str = "get",
        risk_profile: str = "",
    ) -> str:
        """Get or set the client's risk profile for portfolio recommendations.

        GET: Returns the saved risk profile — 'low', 'high', 'very_high', or None.
        SET: Saves a risk profile. Must be one of: 'low', 'high', 'very_high'.

        LOW: Conservative — 100% LM250 Alpha (IRS > 65%, large-cap stable)
        HIGH: Moderate-aggressive — 50% LM250 + 30% SmallCap + 20% MicroCap
        VERY_HIGH: Aggressive — LM250 + SmallCap + MicroCap + Turnaround plays

        ALWAYS set the risk profile BEFORE making portfolio recommendations.

        Parameters:
            user_id: The client's Supabase user ID
            action: 'get' to read profile, 'set' to save profile (default 'get')
            risk_profile: Required when action='set'. One of 'low', 'high', 'very_high'
        """
        if not user_id or user_id == "anonymous":
            return json.dumps({"status": "no_profile", "message": "Must be signed in to manage risk profile"})

        try:
            from nq_api.cache.score_cache import _supabase_rest

            if action == "set":
                if risk_profile not in ("low", "high", "very_high"):
                    return json.dumps({
                        "status": "error",
                        "reason": f"Invalid risk profile: {risk_profile}. Must be 'low', 'high', or 'very_high'",
                    })

                from datetime import datetime, timezone
                _supabase_rest(
                    f"user_profiles?id=eq.{user_id}",
                    method="PATCH",
                    body={"astra_risk_profile": risk_profile, "risk_profile_set_at": datetime.now(timezone.utc).isoformat()},
                )
                return json.dumps({"status": "ok", "action": "set", "risk_profile": risk_profile})

            # action == "get"
            result = _supabase_rest(
                f"user_profiles?id=eq.{user_id}&select=astra_risk_profile",
                method="GET",
            )
            if result and result[0].get("astra_risk_profile"):
                profile = result[0]["astra_risk_profile"]
                return json.dumps({"status": "ok", "action": "get", "risk_profile": profile})
            return json.dumps({"status": "no_profile", "action": "get", "risk_profile": None})
        except Exception as exc:
            log.error("manage_risk_profile failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})