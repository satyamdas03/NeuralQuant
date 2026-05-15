"""StockSummaryCard building from enrichment + platform context data."""
import logging
import re as _re

from nq_api.schemas import StockSummary

log = logging.getLogger(__name__)


def _build_stock_summary(ticker: str | None, market: str, enrichment: dict, platform_ctx: str | None) -> StockSummary | None:
    """Build a StockSummary from enrichment + platform data for the quick-glance card."""
    from nq_api.data_builder import _yf_symbol, _fetch_one

    if not ticker and not enrichment and not platform_ctx:
        return None

    # Determine the ticker to use
    effective_ticker = ticker or ""
    if not effective_ticker and enrichment:
        effective_ticker = enrichment.get("symbol", "")

    # If still no ticker, try to extract from platform_ctx
    # Format: "  NVDA: ForeCast=8.1/10 | CURRENT_PRICE=$196.50 | ..." or "AAPL | Apple Inc. | ..."
    if not effective_ticker and platform_ctx:
        import re as _re
        # Try "TICKER:" format -- only match lines with ForeCast or CURRENT_PRICE to avoid
        # false matches on common English words (e.g. "TECH:" from "tech portfolio")
        m = _re.search(r"^\s*([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*:\s*(?:ForeCast|CURRENT_PRICE)", platform_ctx, _re.MULTILINE)
        if not m:
            # Broader fallback: "TICKER:" followed by stock data patterns
            m = _re.search(r"^\s*([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*:\s*\d+/10", platform_ctx, _re.MULTILINE)
        if not m:
            # Try "TICKER |" format (screener)
            m = _re.search(r"^([A-Z]{1,5}(?:\.[A-Z]{2})?)\s*\|", platform_ctx.strip())
        if m:
            effective_ticker = m.group(1)

    if not effective_ticker:
        return None

    # Auto-detect market from ticker suffix
    detected_market = market
    if effective_ticker.endswith(".NS") or effective_ticker.endswith(".BO"):
        detected_market = "IN"

    is_india = detected_market == "IN" or effective_ticker.endswith(".NS") or effective_ticker.endswith(".BO")
    cur = "Rs." if is_india else "$"

    # Try to get price/fundamentals from enrichment first
    price = enrichment.get("current_price") or enrichment.get("regularMarketPrice") or enrichment.get("finnhub_price")
    change_pct = enrichment.get("change_pct") or enrichment.get("regularMarketChangePercent")
    pe = enrichment.get("pe_ttm") or enrichment.get("trailingPE")
    pb = enrichment.get("pb_ratio") or enrichment.get("priceToBook")
    mcap = enrichment.get("market_cap") or enrichment.get("marketCap")
    high52 = enrichment.get("week_52_high") or enrichment.get("fiftyTwoWeekHigh")
    low52 = enrichment.get("week_52_low") or enrichment.get("fiftyTwoWeekLow")
    target = enrichment.get("analyst_target") or enrichment.get("targetMeanPrice")
    rec = enrichment.get("analyst_rec") or enrichment.get("recommendationKey", "")
    beta = enrichment.get("beta")
    sector = enrichment.get("sector", "")
    name = enrichment.get("long_name") or enrichment.get("shortName") or effective_ticker
    eps = enrichment.get("eps_ttm")

    # Try to get ForeCast score from platform_ctx text
    forecast_score = None
    if platform_ctx:
        import re as _re
        m = _re.search(rf"{_re.escape(effective_ticker)}.*?(\d+\.?\d*)/10", platform_ctx)
        if m:
            try:
                forecast_score = float(m.group(1))
            except ValueError:
                pass

    # Always refresh price-sensitive fields from live source.
    # Enrichment cache has 1h TTL -- price/P/E/market cap change intraday.
    # Technical indicators (RSI/MACD) are fine from cache.
    if effective_ticker:
        try:
            fund = _fetch_one(effective_ticker, detected_market, fast_pe=False)
            if fund and fund.get("_is_real"):
                live_price = fund.get("current_price")
                if live_price:
                    price = live_price
                live_chg = fund.get("change_pct")
                if live_chg is not None:
                    change_pct = live_chg
                live_pe = fund.get("pe_ttm")
                if live_pe:
                    pe = live_pe
                live_pb = fund.get("pb_ratio")
                if live_pb:
                    pb = live_pb
                live_mcap = fund.get("market_cap")
                if live_mcap:
                    mcap = live_mcap
                live_high52 = fund.get("week52_high") or fund.get("week_52_high")
                if live_high52:
                    high52 = live_high52
                live_low52 = fund.get("week52_low") or fund.get("week_52_low")
                if live_low52:
                    low52 = live_low52
                live_target = fund.get("analyst_target")
                if live_target:
                    target = live_target
                live_rec = fund.get("analyst_rec", "")
                if live_rec:
                    rec = live_rec
                live_beta = fund.get("beta")
                if live_beta:
                    beta = live_beta
                live_sector = fund.get("sector", "")
                if live_sector:
                    sector = live_sector
                live_name = fund.get("long_name", "")
                if live_name and (not name or name == effective_ticker):
                    name = live_name
                live_eps = fund.get("eps_ttm")
                if live_eps:
                    eps = live_eps
        except Exception:
            pass

    # Fallback: try score_cache for fundamentals if _fetch_one failed or returned incomplete data
    # (Finnhub may provide price but miss P/E, Beta, etc. -- score_cache often has them.)
    needs_cache = (price is None or pe is None or beta is None or mcap is None) and effective_ticker
    if needs_cache:
        try:
            from nq_api.cache import score_cache
            cached = score_cache.read_one(effective_ticker, detected_market, max_age_seconds=999999999)
            if cached:
                if price is None:
                    price = cached.get("current_price")
                if pe is None:
                    pe = cached.get("pe_ttm")
                if pb is None:
                    pb = cached.get("pb_ratio")
                if mcap is None:
                    mcap = cached.get("market_cap")
                if beta is None:
                    beta = cached.get("beta")
                if not sector:
                    sector = cached.get("sector", "")
                if not name or name == effective_ticker:
                    name = cached.get("long_name") or cached.get("name") or effective_ticker
                if change_pct is None:
                    change_pct = cached.get("change_pct")
        except Exception:
            pass

    # FMP supplement: DCF valuation, analyst target, insider trading, estimates, earnings
    if effective_ticker:
        try:
            from nq_data.fmp import get_fmp_client
            fmp = get_fmp_client()
            if fmp._enabled:
                fmp_sym = _yf_symbol(effective_ticker, detected_market)
                # DCF valuation
                if not target:
                    fmp_target = fmp.get_price_target(fmp_sym)
                    if fmp_target and fmp_target.get("target_avg") is not None:
                        target = round(float(fmp_target["target_avg"]), 2)
                # Analyst consensus
                if not rec:
                    fmp_grades = fmp.get_analyst_grades(fmp_sym)
                    if fmp_grades and fmp_grades.get("consensus"):
                        rec = fmp_grades["consensus"].lower()
        except Exception:
            pass
    if price is None and platform_ctx and effective_ticker:
        import re as _re
        cur_pat = r"Rs\." if is_india else r"\$"
        m = _re.search(
            rf"{_re.escape(effective_ticker)}.*?CURRENT_PRICE={cur_pat}([\d,]+\.?\d*)",
            platform_ctx,
        )
        if m:
            try:
                price = float(m.group(1).replace(",", ""))
            except (ValueError, IndexError):
                pass

    # Only return summary if we have at least a price
    if price is None:
        return None

    return StockSummary(
        ticker=effective_ticker,
        name=name if name else None,
        price=round(float(price), 2) if price else None,
        change_pct=round(float(change_pct), 2) if change_pct is not None else None,
        pe_ttm=round(float(pe), 1) if pe else None,
        eps_ttm=round(float(eps), 2) if eps else None,
        pb_ratio=round(float(pb), 2) if pb else None,
        market_cap=float(mcap) if mcap else None,
        week_52_high=round(float(high52), 2) if high52 else None,
        week_52_low=round(float(low52), 2) if low52 else None,
        analyst_target=round(float(target), 2) if target else None,
        analyst_recommendation=rec.upper() if rec else None,
        beta=round(float(beta), 2) if beta else None,
        sector=sector if sector else None,
        forecast_score=forecast_score,
        currency=cur,
    )
