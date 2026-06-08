"""FMP (Financial Modeling Prep) data connector — stock profiles, quotes, key metrics,
financial statements, analyst data, technical indicators, market data.

Premium tier: 750 calls/min. Rate limiting via nq_data.broker.
In-process dict cache with per-category TTLs. Thread-safe singleton.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .broker import broker

log = logging.getLogger(__name__)

# ── TTLs (seconds) ──────────────────────────────────────────────────────────
_TTLS: dict[str, int] = {
    "profile": 3600,          # 1 hour
    "quote": 300,             # 5 min
    "batch_quote": 300,       # 5 min
    "key_metrics": 3600,      # 1 hour
    "sector_perf": 300,       # 5 min
    "movers": 300,            # 5 min
    "ratios": 3600,           # 1 hour
    "income_stmt": 3600,      # 1 hour
    "balance_sheet": 3600,    # 1 hour
    "cash_flow": 3600,        # 1 hour
    "financial_scores": 86400, # 24 hours
    "analyst_estimates": 43200, # 12 hours
    "analyst_grades": 43200,   # 12 hours
    "price_target": 43200,     # 12 hours
    "technical": 900,         # 15 min
    "dcf": 43200,             # 12 hours
    "treasury": 86400,        # 24 hours
    "insider": 3600,          # 1 hour
    "earnings": 86400,        # 24 hours
    "dividends": 86400,       # 24 hours
    "screener": 3600,         # 1 hour
    "historical_prices": 3600,  # 1 hour
    "stock_peers": 86400,       # 24 hours — peer lists rarely change
    "news": 600,                # 10 minutes
}

# ── Symbol resolution ────────────────────────────────────────────────────────
_INDEX_MAP = {
    "^GSPC": ".SPX",
    "^IXIC": ".IXIC",
    "^DJI": ".DJI",
    "^VIX": "^VIX",
    "^NSEI": "NSEI.NS",
    "^BSESN": "BSESN.BO",
    "^INDIAVIX": "INDIAVIX.NS",
    "^NSEBANK": "CNXNIFTY.NS",
}

_FUTURES_MAP = {
    "ES=F": "ES=F",
    "NQ=F": "NQ=F",
    "YM=F": "YM=F",
}


class FMPClient:
    """FMP API client with rate limiting and in-process caching.

    Follows FinnhubClient pattern: httpx.Client, _cache dict with TTLs,
    broker.acquire("fmp") rate limiting, thread-safe singleton.
    """

    BASE_URL = os.environ.get("FMP_BASE_URL", "https://financialmodelingprep.com/stable")

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("FMP_API_KEY", "")
        self._client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._enabled = bool(self._api_key)

    # ── Phase 1: Core Data ────────────────────────────────────────────────────

    def get_profile(self, ticker: str) -> dict | None:
        """Company profile: name, market_cap, sector, industry, CEO, exchange, image."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("profile", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        p = data[0] if isinstance(data, list) else data
        return {
            "name": p.get("companyName") or p.get("name"),
            "market_cap": p.get("marketCap"),
            "sector": p.get("sector"),
            "industry": p.get("industry"),
            "description": p.get("description"),
            "ceo": p.get("ceo") or p.get("ceoName"),
            "exchange": p.get("exchangeShortName") or p.get("exchange"),
            "image": p.get("image"),
            "currency": p.get("currency"),
            "country": p.get("country"),
            "ipo_date": p.get("ipoDate"),
            "beta": p.get("beta"),
            "price": p.get("price"),
            "last_dividend": p.get("lastDividend"),
            "range": p.get("range"),
            "volume": p.get("volume"),
            "avg_volume": p.get("averageVolume"),
        }

    def get_quote(self, ticker: str) -> dict | None:
        """Real-time quote: price, change, P/E, EPS, marketCap, 52w range, volume."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("quote", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        q = data[0] if isinstance(data, list) else data
        price = q.get("price")
        prev = q.get("previousClose")
        change_pct = None
        if price is not None and prev and prev > 0:
            change_pct = round((price - prev) / prev * 100, 2)
        return {
            "price": price,
            "change": q.get("change"),
            "change_pct": change_pct or q.get("changesPercentage"),
            "pe": q.get("pe") or q.get("peRatio"),
            "eps": q.get("eps"),
            "market_cap": q.get("marketCap"),
            "year_high": q.get("yearHigh") or q.get("week52High"),
            "year_low": q.get("yearLow") or q.get("week52Low"),
            "volume": q.get("volume"),
            "avg_volume": q.get("avgVolume") or q.get("averageVolume"),
            "open": q.get("open"),
            "previous_close": prev,
            "timestamp": q.get("timestamp"),
        }

    def get_batch_quotes(self, tickers: list[str]) -> dict[str, dict] | None:
        """Batch quotes for up to 50 tickers. Returns {ticker: quote_dict}."""
        if not tickers:
            return None
        # Batch in chunks of 50
        results = {}
        for i in range(0, len(tickers), 50):
            chunk = tickers[i:i + 50]
            syms = ",".join(self._resolve_symbol(t) for t in chunk)
            cache_key = f"batch_quote:{syms}"
            cached = self._cache_get("batch_quote", cache_key)
            if cached is not None:
                results.update(cached)
                continue
            data = self._fetch("batch_quote", cache_key, {"symbols": syms})
            if data and isinstance(data, list):
                chunk_results = {}
                for q in data:
                    sym = q.get("symbol", "")
                    change_pct = None
                    price = q.get("price")
                    prev = q.get("previousClose")
                    if price is not None and prev and prev > 0:
                        change_pct = round((price - prev) / prev * 100, 2)
                    chunk_results[sym] = {
                        "price": price,
                        "change": q.get("change"),
                        "change_pct": change_pct or q.get("changesPercentage"),
                        "pe": q.get("pe") or q.get("peRatio"),
                        "market_cap": q.get("marketCap"),
                        "volume": q.get("volume"),
                    }
                self._cache_set("batch_quote", cache_key, chunk_results)
                results.update(chunk_results)
        return results if results else None

    def get_historical_prices(
        self, ticker: str, from_date: str | None = None, to_date: str | None = None,
        days: int = 365,
    ) -> list[dict] | None:
        """Historical EOD OHLCV data. Returns list of {date, open, high, low, close, volume, ...}.

        Uses /stable/historical-price-eod/full endpoint.
        If from_date/to_date omitted, computed from `days` lookback.
        """
        from datetime import datetime, timedelta
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d")
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=days + 5)).strftime("%Y-%m-%d")
        sym = self._resolve_symbol(ticker)
        cache_key = f"{ticker}:{from_date}:{to_date}"
        data = self._fetch("historical_prices", cache_key, {
            "symbol": sym, "from": from_date, "to": to_date,
        })
        if not data or not isinstance(data, list):
            return None
        # Sort ascending (API returns descending by default)
        data.sort(key=lambda r: r.get("date", ""))
        return data

    def get_key_metrics(self, ticker: str) -> dict | None:
        """Key metrics: P/B, dividend yield, ROE, ROA, margins, debt/equity, etc.
        Note: P/E and beta are NOT in the /stable/key-metrics endpoint.
        Use get_profile() for beta, get_quote() + get_ratios() for P/E calculation."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("key_metrics", ticker, {"symbol": sym, "period": "annual"})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        m = data[0] if isinstance(data, list) else data
        return {
            "pe_ratio": m.get("peRatio") or m.get("pe"),
            "pb_ratio": m.get("pbRatio") or m.get("priceToBookRatio"),
            "dividend_yield": m.get("dividendYield"),
            "beta": m.get("beta"),
            "roe": m.get("returnOnEquity") or m.get("roe"),
            "roa": m.get("returnOnAssets") or m.get("roa"),
            "gross_profit_margin": m.get("grossProfitMargin"),
            "operating_profit_margin": m.get("operatingProfitMargin"),
            "net_profit_margin": m.get("netProfitMargin"),
            "debt_to_equity": m.get("debtToEquity") or m.get("debtEquityRatio"),
            "current_ratio": m.get("currentRatio"),
            "revenue_growth": m.get("revenueGrowth") or m.get("revenueGrowthRate"),
            "earnings_growth": m.get("earningsGrowth") or m.get("epsgrowth"),
            "ev_to_ebitda": m.get("evToEbitda") or m.get("evToEBITDA"),
            "price_to_sales": m.get("priceToSalesRatio") or m.get("pS"),
            "market_cap": m.get("marketCap"),
        }

    def get_sector_performance(self, date_str: str | None = None) -> list[dict] | None:
        """Sector performance snapshot. Returns list of {sector, change_pct}."""
        params = {}
        if date_str:
            params["date"] = date_str
        data = self._fetch("sector_perf", "__sectors__", params)
        if not data or not isinstance(data, list):
            return None
        sectors = []
        for s in data:
            name = s.get("sector") or s.get("name") or ""
            chg = s.get("changePercentage") or s.get("changesPercentage")
            # FMP stable API uses averageChange as decimal percentage (e.g. -0.1129 = -0.11%)
            if chg is None and s.get("averageChange") is not None:
                chg = round(float(s["averageChange"]), 2)
            if name:
                sectors.append({
                    "sector": name,
                    "change_pct": round(float(chg), 2) if chg is not None else None,
                })
        return sectors if sectors else None

    def get_market_movers(self, direction: str = "gainers") -> list[dict] | None:
        """Market movers: 'gainers', 'losers', or 'active'."""
        endpoint_map = {
            "gainers": "biggest-gainers",
            "losers": "biggest-losers",
            "active": "most-actives",
        }
        endpoint = endpoint_map.get(direction, "biggest-gainers")
        # Use direction-specific endpoint path, but cache under movers category
        url = f"{self.BASE_URL}/{endpoint}"
        params = {"apikey": self._api_key}
        cache_key = f"movers:__movers_{direction}__"
        # Check cache first
        cached = self._cache_get("movers", f"__movers_{direction}__")
        if cached is not None:
            return cached

        if not self._enabled:
            return None

        try:
            with broker.acquire("fmp"):
                resp = self._client.get(url, params=params)
            if resp.status_code == 429:
                log.warning("FMP rate limited for market movers/%s", direction)
                return None
            if resp.status_code != 200:
                log.debug("FMP market movers/%s returned %d", direction, resp.status_code)
                return None

            data = resp.json()
            if not data or not isinstance(data, list):
                return None

            movers = []
            for item in data[:10]:
                price = item.get("price")
                change = item.get("change")
                change_pct = item.get("changesPercentage")
                movers.append({
                    "ticker": item.get("symbol", ""),
                    "name": item.get("name", ""),
                    "price": price,
                    "change": change,
                    "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
                    "volume": item.get("volume"),
                })
            result = movers if movers else None
            self._cache_set("movers", f"__movers_{direction}__", result)
            return result
        except httpx.TimeoutException:
            log.warning("FMP timeout for market movers/%s", direction)
            return None
        except Exception as exc:
            log.warning("FMP error market movers/%s: %s", direction, exc)
            return None

    # ── Phase 2: Enhanced Fundamentals ────────────────────────────────────────

    def get_ratios(self, ticker: str, period: str = "annual") -> dict | None:
        """Financial ratios: currentRatio, debtToEquity, margins, ROE, ROA."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("ratios", ticker, {"symbol": sym, "period": period})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        r = data[0] if isinstance(data, list) else data
        return {
            "current_ratio": r.get("currentRatio"),
            "debt_to_equity": r.get("debtToEquity") or r.get("debtEquityRatio"),
            "gross_profit_margin": r.get("grossProfitMargin"),
            "operating_profit_margin": r.get("operatingProfitMargin"),
            "net_profit_margin": r.get("netProfitMargin"),
            "return_on_equity": r.get("returnOnEquity") or r.get("roe"),
            "return_on_assets": r.get("returnOnAssets") or r.get("roa"),
            "price_to_book": r.get("priceToBookRatio") or r.get("pbRatio"),
            "price_to_sales": r.get("priceToSalesRatio") or r.get("pS"),
        }

    def get_income_statement(self, ticker: str, period: str = "annual") -> dict | None:
        """Income statement: revenue, gross profit, operating income, net income, EPS."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("income_stmt", ticker, {"symbol": sym, "period": period})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        i = data[0] if isinstance(data, list) else data
        return {
            "revenue": i.get("revenue"),
            "gross_profit": i.get("grossProfit") or i.get("gross_profit"),
            "operating_income": i.get("operatingIncome") or i.get("operating_income"),
            "net_income": i.get("netIncome") or i.get("net_income"),
            "eps": i.get("eps") or i.get("epsDiluted"),
            "revenue_growth": i.get("revenueGrowth") or i.get("revenue_growth"),
            "gross_margin": i.get("grossProfitRatio") or i.get("gross_margin"),
            "operating_margin": i.get("operatingIncomeRatio") or i.get("operating_margin"),
            "date": i.get("date") or i.get("fillingDate"),
            "period": i.get("period"),
        }

    def get_balance_sheet(self, ticker: str, period: str = "annual") -> dict | None:
        """Balance sheet: total assets, liabilities, equity, cash, debt."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("balance_sheet", ticker, {"symbol": sym, "period": period})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        b = data[0] if isinstance(data, list) else data
        return {
            "total_assets": b.get("totalAssets") or b.get("total_assets"),
            "total_liabilities": b.get("totalLiabilities") or b.get("total_liabilities"),
            "total_equity": b.get("totalStockholdersEquity") or b.get("stockholders_equity"),
            "cash": b.get("cashAndCashEquivalents") or b.get("cash"),
            "total_debt": b.get("totalDebt") or b.get("total_debt"),
            "current_assets": b.get("totalCurrentAssets") or b.get("current_assets"),
            "current_liabilities": b.get("totalCurrentLiabilities") or b.get("current_liabilities"),
            "date": b.get("date") or b.get("fillingDate"),
        }

    def get_cash_flow(self, ticker: str, period: str = "annual") -> dict | None:
        """Cash flow: operating, investing, financing, free cash flow."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("cash_flow", ticker, {"symbol": sym, "period": period})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        c = data[0] if isinstance(data, list) else data
        return {
            "operating_cash_flow": c.get("operatingCashFlow") or c.get("operating_cash_flow"),
            "free_cash_flow": c.get("freeCashFlow") or c.get("free_cash_flow"),
            "capital_expenditure": c.get("capitalExpenditure") or c.get("capital_expenditure"),
            "dividends_paid": c.get("dividendsPaid") or c.get("dividends_paid"),
            "net_change_in_cash": c.get("netChangeInCash") or c.get("net_change_in_cash"),
            "date": c.get("date") or c.get("fillingDate"),
        }

    def get_financial_scores(self, ticker: str) -> dict | None:
        """Financial scores: Altman Z-Score, Piotroski Score."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("financial_scores", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        s = data[0] if isinstance(data, list) else data
        return {
            "altman_z_score": s.get("altmanZScore"),
            "piotroski_score": s.get("piotroskiScore"),
            "beneish_m_score": s.get("beneishMScore"),
            "graham_number": s.get("grahamNumber"),
            "graham_net_current_asset_value": s.get("grahamNetCurrentAssetValue"),
        }

    def get_analyst_estimates(self, ticker: str, period: str = "annual") -> dict | None:
        """Analyst estimates: revenue, EPS consensus."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("analyst_estimates", ticker, {"symbol": sym, "period": period})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        e = data[0] if isinstance(data, list) else data
        return {
            "revenue_estimate": e.get("revenueEstimate") or e.get("estimatedRevenue"),
            "eps_estimate": e.get("epsEstimate") or e.get("estimatedEps"),
            "number_of_analysts": e.get("numberOfAnalysts") or e.get("analystCount"),
            "date": e.get("date"),
            "period": e.get("period"),
        }

    def get_analyst_grades(self, ticker: str) -> dict | None:
        """Analyst consensus grades: buy/hold/sell distribution."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("analyst_grades", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        g = data[0] if isinstance(data, list) else data
        return {
            "strong_buy": g.get("strongBuy"),
            "buy": g.get("buy"),
            "hold": g.get("hold"),
            "sell": g.get("sell"),
            "strong_sell": g.get("strongSell"),
            "consensus": g.get("consensus"),
            "consensus_grade": g.get("ratingBuyPercent") or g.get("consensusGrade"),
        }

    def get_price_target(self, ticker: str) -> dict | None:
        """Analyst price target consensus: targetAvg, targetHigh, targetLow."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("price_target", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        t = data[0] if isinstance(data, list) else data
        return {
            "target_avg": t.get("targetAvg") or t.get("targetMean"),
            "target_high": t.get("targetHigh"),
            "target_low": t.get("targetLow"),
            "target_median": t.get("targetMedian"),
            "consensus": t.get("consensus"),
            "number_of_analysts": t.get("numberOfAnalysts") or t.get("analystCount"),
        }

    # ── Phase 3: Advanced Features ───────────────────────────────────────────

    def get_technical_indicator(self, ticker: str, indicator_type: str = "rsi", period: int = 14) -> dict | None:
        """Technical indicator: RSI, MACD, SMA, EMA, etc."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("technical", ticker, {
            "symbol": sym,
            "type": indicator_type,
            "periodLength": str(period),
            "timeframe": "1day",
        })
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        return data[-1] if isinstance(data, list) else data

    def get_dcf(self, ticker: str) -> dict | None:
        """Discounted Cash Flow valuation."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("dcf", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        d = data[0] if isinstance(data, list) else data
        return {
            "dcf_value": d.get("dcf") or d.get("value"),
            "stock_price": d.get("stockPrice") or d.get("price"),
            "date": d.get("date"),
        }

    def get_treasury_rates(self) -> dict | None:
        """US Treasury rates: 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y."""
        data = self._fetch("treasury", "__treasury__", {})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        r = data[-1] if isinstance(data, list) else data
        return {
            "1m": r.get("month1"),
            "3m": r.get("month3"),
            "6m": r.get("month6"),
            "1y": r.get("year1"),
            "2y": r.get("year2"),
            "5y": r.get("year5"),
            "10y": r.get("year10"),
            "20y": r.get("year20"),
            "30y": r.get("year30"),
            "date": r.get("date"),
        }

    def get_insider_trading(self, ticker: str) -> list[dict] | None:
        """Insider trading transactions."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("insider", ticker, {"symbol": sym})
        if not data or not isinstance(data, list):
            return None
        results = []
        for item in data[:10]:
            results.append({
                "name": item.get("name") or item.get("insiderName"),
                "title": item.get("title") or item.get("insiderTitle"),
                "transaction_type": item.get("transactionType") or item.get("acquisitionOrDisposition"),
                "shares": item.get("securitiesTransacted") or item.get("shares"),
                "price": item.get("transactionPrice") or item.get("price"),
                "date": item.get("transactionDate") or item.get("date"),
                "link": item.get("link"),
            })
        return results if results else None

    def get_earnings_calendar(self, from_date: str, to_date: str) -> list[dict] | None:
        """Earnings calendar between dates (YYYY-MM-DD)."""
        data = self._fetch("earnings", "__earnings__", {"from": from_date, "to": to_date})
        if not data or not isinstance(data, list):
            return None
        results = []
        for item in data[:20]:
            results.append({
                "ticker": item.get("symbol") or item.get("ticker"),
                "name": item.get("name") or item.get("companyName"),
                "date": item.get("date") or item.get("reportedDate"),
                "eps_estimate": item.get("epsEstimate"),
                "eps_actual": item.get("epsActual") or item.get("eps"),
                "revenue_estimate": item.get("revenueEstimate"),
                "revenue_actual": item.get("revenueActual") or item.get("revenue"),
                "time": item.get("time") or item.get("reportTime"),
            })
        return results if results else None

    def get_dividends(self, ticker: str) -> list[dict] | None:
        """Dividend history for a ticker."""
        sym = self._resolve_symbol(ticker)
        data = self._fetch("dividends", ticker, {"symbol": sym})
        if not data or not isinstance(data, list):
            return None
        results = []
        for item in data[:8]:
            results.append({
                "date": item.get("date") or item.get("recordDate"),
                "dividend": item.get("dividend") or item.get("amount") or item.get("adjDividend"),
                "yield_pct": item.get("yield"),
            })
        return results if results else None

    def get_market_news(self, limit: int = 10, tickers: str | None = None) -> list[dict] | None:
        """General market news or per-ticker news from FMP.

        Uses /stable/news/stock-latest for general market news
        (no ticker filter) or /stable/news/stock for ticker-specific news.

        Returns list of dicts with title, summary, url, source, time, symbol.
        """
        if not self._enabled:
            return None

        if tickers:
            # Per-ticker news
            cache_key = f"news:tickers:{tickers}:{limit}"
            params = {"symbols": tickers, "limit": str(limit)}
            endpoint_path = "news/stock"
        else:
            # General market news
            cache_key = f"news:market:{limit}"
            params = {"limit": str(limit)}
            endpoint_path = "news/stock-latest"

        cached = self._cache_get("news", cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/{endpoint_path}"
        params["apikey"] = self._api_key

        try:
            with broker.acquire("fmp"):
                resp = self._client.get(url, params=params)
            if resp.status_code == 429:
                log.warning("FMP rate limited for market news")
                return None
            if resp.status_code != 200:
                log.debug("FMP market news returned %d", resp.status_code)
                return None

            data = resp.json()
            if not data or not isinstance(data, list):
                return None

            results = []
            for item in data[:limit]:
                title = item.get("title", "")
                if not title:
                    continue
                results.append({
                    "title": title,
                    "summary": item.get("text", "")[:500] if item.get("text") else "",
                    "url": item.get("url", ""),
                    "source": item.get("site", "") or item.get("source", ""),
                    "time": item.get("publishedDate", "") or item.get("date", ""),
                    "symbol": item.get("symbol", ""),
                    "image": item.get("image", ""),
                })
            if not results:
                return None
            self._cache_set("news", cache_key, results)
            return results
        except httpx.TimeoutException:
            log.warning("FMP timeout for market news")
            return None
        except Exception as exc:
            log.warning("FMP error market news: %s", exc)
            return None

    def get_stock_peers(self, ticker: str) -> list[str] | None:
        """Stock peers / competitors. Returns list of peer ticker symbols.

        Uses FMP /stable/stock-peers which returns companies in the same
        industry and of similar market cap.  Falls back to empty list on error.
        """
        sym = self._resolve_symbol(ticker)
        data = self._fetch("stock_peers", ticker, {"symbol": sym})
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        # FMP returns a list of dicts with "symbol" keys, or a flat list of symbols
        peers: list[str] = []
        for item in data:
            if isinstance(item, str):
                # Strip exchange suffixes to normalise (e.g. "AAPL" stays, "RELIANCE.NS" stays)
                peers.append(item)
            elif isinstance(item, dict):
                sym_val = item.get("symbol") or item.get("peerSymbol") or ""
                if sym_val:
                    peers.append(sym_val)
        return peers if peers else None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _resolve_symbol(self, ticker: str) -> str:
        """Map NeuralQuant tickers to FMP symbols.

        FMP uses:
        - US: plain ticker (AAPL, MSFT)
        - NSE: ticker.NS (TCS.NS, INFY.NS)
        - BSE: ticker.BO
        - Indices: special mappings (.SPX, ^VIX, etc.)
        """
        if ticker in _INDEX_MAP:
            return _INDEX_MAP[ticker]
        if ticker in _FUTURES_MAP:
            return _FUTURES_MAP[ticker]
        # Strip .NS/.BO for resolution if already present
        if ticker.endswith(".NS") or ticker.endswith(".BO"):
            return ticker
        return ticker

    def _fetch(
        self,
        endpoint: str,
        ticker: str,
        params: dict,
        cache_category: str | None = None,
    ) -> Any:
        """Rate-limited fetch with caching. Endpoint maps to /stable/{endpoint}."""
        cat = cache_category or endpoint
        cached = self._cache_get(cat, ticker)
        if cached is not None:
            return cached

        if not self._enabled:
            log.debug("FMP disabled (no API key)")
            return None

        # Map cache category to API endpoint path
        endpoint_path = self._endpoint_path(cat)
        url = f"{self.BASE_URL}/{endpoint_path}"
        params["apikey"] = self._api_key

        for attempt in range(3):
            try:
                with broker.acquire("fmp"):
                    resp = self._client.get(url, params=params)

                if resp.status_code == 429:
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    log.warning("FMP rate limited for %s/%s after 3 attempts", endpoint, ticker)
                    return None
                if resp.status_code != 200:
                    log.debug("FMP %s/%s returned %d", endpoint, ticker, resp.status_code)
                    return None

                data = resp.json()
                self._cache_set(cat, ticker, data)
                return data
            except httpx.TimeoutException:
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                log.warning("FMP timeout for %s/%s after 3 attempts", endpoint, ticker)
                return None
            except Exception as exc:
                log.warning("FMP error %s/%s: %s", endpoint, ticker, exc)
                return None
        return None

    def _endpoint_path(self, category: str) -> str:
        """Map cache category to FMP /stable/ endpoint path."""
        mapping = {
            "profile": "profile",
            "quote": "quote",
            "batch_quote": "batch-quote",
            "key_metrics": "key-metrics",
            "sector_perf": "sector-performance-snapshot",
            "movers": "biggest-gainers",  # overridden by direction in get_market_movers
            "ratios": "ratios",
            "income_stmt": "income-statement",
            "balance_sheet": "balance-sheet-statement",
            "cash_flow": "cash-flow-statement",
            "financial_scores": "financial-scores",
            "analyst_estimates": "analyst-estimates",
            "analyst_grades": "grades-consensus",
            "price_target": "price-target-consensus",
            "technical": "technical-indicators",
            "dcf": "discounted-cash-flow",
            "treasury": "treasury-rates",
            "insider": "insider-trading/search",
            "earnings": "earnings-calendar",
            "dividends": "dividends",
            "screener": "company-screener",
            "historical_prices": "historical-price-eod/full",
            "stock_peers": "stock-peers",
            "news": "news/stock-latest",  # overridden in get_market_news
        }
        return mapping.get(category, category)

    def _cache_get(self, category: str, ticker: str) -> Any | None:
        key = f"{category}:{ticker}"
        with self._lock:
            if key in self._cache:
                ts, data = self._cache[key]
                ttl = _TTLS.get(category, 900)
                if time.monotonic() - ts < ttl:
                    return data
                del self._cache[key]
        return None

    def _cache_set(self, category: str, ticker: str, data: Any) -> None:
        key = f"{category}:{ticker}"
        with self._lock:
            self._cache[key] = (time.monotonic(), data)

    def close(self) -> None:
        """Close the underlying HTTP client to free connections."""
        if self._client and not self._client.is_closed:
            self._client.close()

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: FMPClient | None = None
_client_lock = threading.Lock()


def get_fmp_client() -> FMPClient:
    """Thread-safe singleton accessor. Works without API key (returns None for all calls)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = FMPClient()
        return _client