"""Market data tools mixin — prices, indices, scores, movers, sectors."""

from __future__ import annotations

import json
import logging

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class MarketToolsMixin:
    """Market intelligence tools — live prices, indices, scores, movers."""

    @function_tool
    async def get_stock_price(
        self,
        ticker: str,
        market: str = "US",
    ) -> str:
        """Get live price and fundamentals for a stock: current price, P/E, beta,
        market cap, sector, ROE, revenue growth, analyst target, 52-week range,
        and AI composite score with factor percentiles.

        ALWAYS call this before giving any stock analysis.

        VOICE: Describe metrics naturally as a story. "NVDA trades at $223 with
        a P/E of 42 — that's expensive, but justified by seventy-six percent ROE
        and dominant AI positioning. Our models score it 8.7 out of 10."
        Never recite field names or format as a table.

        Parameters:
            ticker: Stock ticker symbol, e.g. 'AAPL', 'NVDA', 'RELIANCE', 'TCS'
            market: Market — 'US' or 'IN'
        """
        try:
            from nq_api.data_builder import _fetch_one
            from nq_api.cache.score_cache import read_top

            row = _fetch_one(ticker, market, fast_pe=True)
            if row is None:
                return json.dumps({"status": "unavailable", "ticker": ticker, "reason": "Market data temporarily unavailable — try again or try an alternative ticker"})

            result = {
                "status": "ok",
                "ticker": ticker,
                "market": market,
                "current_price": row.get("current_price"),
                "pe_ttm": row.get("pe_ttm"),
                "beta": row.get("beta"),
                "market_cap": row.get("market_cap"),
                "sector": row.get("sector", ""),
                "composite_score": row.get("composite_score"),
                "momentum_percentile": row.get("momentum_percentile"),
                "quality_percentile": row.get("quality_percentile"),
                "value_percentile": row.get("value_percentile"),
                "low_vol_percentile": row.get("low_vol_percentile"),
                "gross_profit_margin": row.get("gross_profit_margin"),
                "debt_equity": row.get("debt_equity"),
                "roe": row.get("roe"),
                "revenue_growth_yoy": row.get("revenue_growth_yoy"),
                "analyst_target": row.get("analyst_target"),
                "week52_high": row.get("week52_high"),
                "week52_low": row.get("week52_low"),
            }
            result = {k: v for k, v in result.items() if v is not None}
            return json.dumps(result, default=str)
        except Exception as exc:
            log.error("get_stock_price failed for %s/%s: %s", ticker, market, exc)
            return json.dumps({"status": "error", "ticker": ticker, "reason": str(exc)})

    @function_tool
    async def get_market_overview(self) -> str:
        """Get current market overview: VIX, S&P 500 return, 10-year yield,
        Fed funds rate, high-yield spreads, CPI, ISM PMI, plus top 5 US and
        India AI-ranked stocks. Use when client asks how markets are doing.

        VOICE: Narrate macro naturally. "Markets are calm — VIX at eighteen,
        S&P up over five percent this month, ten-year yield steady at four
        point two." Don't recite field names like "VIX: 18, SPX return: 5.2%."
        """
        try:
            from nq_api.data_builder import fetch_real_macro
            from nq_api.cache.score_cache import read_top

            macro = fetch_real_macro()
            us_top = read_top("US", 5)
            in_top = read_top("IN", 5)

            result = {
                "status": "ok",
                "macro": {
                    "vix": getattr(macro, "vix", None),
                    "spx_return_1m": getattr(macro, "spx_return_1m", None),
                    "spx_vs_200ma": getattr(macro, "spx_vs_200ma", None),
                    "yield_10y": getattr(macro, "yield_10y", None),
                    "fed_funds_rate": getattr(macro, "fed_funds_rate", None),
                    "hy_spread_oas": getattr(macro, "hy_spread_oas", None),
                    "cpi_yoy": getattr(macro, "cpi_yoy", None),
                    "ism_pmi": getattr(macro, "ism_pmi", None),
                    "yield_spread_2y10y": getattr(macro, "yield_spread_2y10y", None),
                },
                "top_us_scores": [
                    {"ticker": s["ticker"], "score_1_10": s["score_1_10"], "sector": s.get("sector", "")}
                    for s in us_top
                ] if us_top else [],
                "top_in_scores": [
                    {"ticker": s["ticker"], "score_1_10": s["score_1_10"], "sector": s.get("sector", "")}
                    for s in in_top
                ] if in_top else [],
            }
            result["macro"] = {k: v for k, v in result["macro"].items() if v is not None}
            return json.dumps(result, default=str)
        except Exception as exc:
            log.error("get_market_overview failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_top_scores(
        self,
        market: str = "US",
        n: int = 10,
    ) -> str:
        """Get the top AI-ranked stocks with composite scores (1-10) and factor
        percentiles. Use when client asks for best picks or what's hot.

        FALLBACK: If score data is unavailable (nightly refresh), DO NOT retry
        this tool. Instead call get_market_movers() to find strong gainers, then
        call get_stock_price() on the top candidates. Combine with
        get_sector_performance() and get_macro_context() to build your own ranking.

        Parameters:
            market: Market — 'US' or 'IN'
            n: Number of top stocks to return (max 20)
        """
        try:
            from nq_api.cache.score_cache import read_top

            results = read_top(market, min(n, 20))
            if not results:
                return json.dumps({"status": "unavailable", "reason": "Score data temporarily unavailable — scores are refreshed nightly"})

            stocks = [
                {
                    "rank": i + 1,
                    "ticker": r["ticker"],
                    "score_1_10": r["score_1_10"],
                    "momentum_percentile": r.get("momentum_percentile"),
                    "quality_percentile": r.get("quality_percentile"),
                    "value_percentile": r.get("value_percentile"),
                    "pe_ttm": r.get("pe_ttm"),
                    "sector": r.get("sector", ""),
                }
                for i, r in enumerate(results)
            ]
            return json.dumps({"status": "ok", "market": market, "count": len(stocks), "stocks": stocks}, default=str)
        except Exception as exc:
            log.error("get_top_scores failed for %s: %s", market, exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_market_movers(self) -> str:
        """Get today's biggest market movers — top gainers and losers by percentage change.
        Use when the client wants to know what's moving dramatically in the market.
        """
        try:
            import asyncio
            import yfinance as yf

            gainers_raw = await asyncio.to_thread(
                lambda: yf.Screener(body={"operator": "gt", "field": "percent_change", "value": 3}).response
            )
            losers_raw = await asyncio.to_thread(
                lambda: yf.Screener(body={"operator": "lt", "field": "percent_change", "value": -3}).response
            )

            gainers = []
            losers = []
            quotes = gainers_raw.get("quotes", []) if isinstance(gainers_raw, dict) else []
            for q in quotes[:10]:
                price = q.get("regularMarketPrice", 0) or 0
                if price < 5:
                    continue
                gainers.append({
                    "ticker": q.get("symbol", ""),
                    "name": q.get("shortName") or q.get("longName", ""),
                    "price": price,
                    "change_pct": q.get("regularMarketChangePercent", 0),
                })

            loser_quotes = losers_raw.get("quotes", []) if isinstance(losers_raw, dict) else []
            for q in loser_quotes[:10]:
                price = q.get("regularMarketPrice", 0) or 0
                if price < 5:
                    continue
                losers.append({
                    "ticker": q.get("symbol", ""),
                    "name": q.get("shortName") or q.get("longName", ""),
                    "price": price,
                    "change_pct": q.get("regularMarketChangePercent", 0),
                })

            return json.dumps({"status": "ok", "gainers": gainers, "losers": losers}, default=str)
        except Exception as exc:
            log.error("get_market_movers failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_indices(self) -> str:
        """Get live index values for major indices. Returns S&P 500, Nifty 50, VIX,
        and other key index levels with daily changes.

        Use when client asks about specific index levels or market benchmarks.
        """
        try:
            import asyncio
            import yfinance as yf

            symbols = ["^GSPC", "^IXIC", "^DJI", "^NSEI", "^VIX", "INR=X"]
            indices = []

            def _fetch():
                results = []
                for sym in symbols:
                    try:
                        t = yf.Ticker(sym)
                        info = t.fast_info or {}
                        price = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                        change = info.get("regularMarketChangePercent") or 0
                        name_map = {
                            "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones",
                            "^NSEI": "Nifty 50", "^VIX": "VIX", "INR=X": "INR/USD",
                        }
                        if price:
                            results.append({
                                "symbol": name_map.get(sym, sym),
                                "price": price,
                                "change_pct": change,
                            })
                    except Exception:
                        pass
                return results

            indices = await asyncio.to_thread(_fetch)
            return json.dumps({"status": "ok", "indices": indices}, default=str)
        except Exception as exc:
            log.error("get_indices failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_sector_performance(self) -> str:
        """Get sector performance data showing which sectors are leading or lagging.
        Returns percentage changes for all 11 GICS sectors.

        Use when client asks about sector rotation or which sectors to overweight/underweight.
        """
        try:
            import asyncio
            import yfinance as yf

            sector_etfs = {
                "Technology": "XLK",
                "Financials": "XLF",
                "Healthcare": "XLV",
                "Consumer Discretionary": "XLY",
                "Communication Services": "XLC",
                "Industrials": "XLI",
                "Energy": "XLE",
                "Consumer Staples": "XLP",
                "Utilities": "XLU",
                "Real Estate": "XLRE",
                "Materials": "XLB",
            }

            async def _fetch_one(sector: str, etf: str):
                try:
                    t = await asyncio.to_thread(lambda: yf.Ticker(etf))
                    info = await asyncio.to_thread(lambda: t.fast_info)
                    price = info.get("lastPrice") or info.get("regularMarketPrice")
                    prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
                    if price and prev and prev > 0:
                        change = ((price - prev) / prev) * 100
                        return {"sector": sector, "etf": etf, "change_pct": round(change, 2)}
                except Exception:
                    return None
                return None

            tasks = [_fetch_one(sector, etf) for sector, etf in sector_etfs.items()]
            results = await asyncio.gather(*tasks)
            sectors = [r for r in results if r is not None]
            sectors.sort(key=lambda s: s["change_pct"], reverse=True)

            return json.dumps({"status": "ok", "sectors": sectors}, default=str)
        except Exception as exc:
            log.error("get_sector_performance failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})
