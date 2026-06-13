"""Portfolio-specific logic -- intent detection, price filling, profile building."""
import logging
import re

import yfinance as yf
import pandas as pd

from nq_api.services.constants import _PORTFOLIO_KEYWORDS
from nq_api.services.prompts import _PROFILE_PROMPT_TEMPLATE
from nq_api.schemas import UserProfile
from nq_api.cache.snapshot_cache import read_snapshot
from nq_api.services.live_price import get_live_price

log = logging.getLogger(__name__)


def _snapshot_price(ticker: str, market: str) -> float | None:
    """Live price from public.stock_snapshot (refreshed every 30 min, has IN prices
    that Render's blocked yfinance cannot fetch). Returns None when absent or <= 0."""
    try:
        row = read_snapshot(ticker.upper(), market)
        if row and row.get("price"):
            p = float(row["price"])
            return p if p > 0 else None
    except Exception:
        return None
    return None


def _is_portfolio_intent(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _PORTFOLIO_KEYWORDS)


def _build_profile_prompt(profile: UserProfile) -> str:
    return _PROFILE_PROMPT_TEMPLATE.format(
        risk_profile=profile.risk_profile,
        time_horizon=profile.time_horizon,
        goal=profile.goal,
        investable_amount=profile.investable_amount or "Not specified",
    )


async def _load_portfolio_from_supabase(user_id: str) -> list[dict]:
    """Load watchlist holdings for a user from Supabase.

    Uses service_role key to bypass RLS — caller must validate user_id.
    Returns list of {ticker, market, note, created_at} dicts.
    """
    import os
    import httpx

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        log.warning("Supabase not configured for portfolio load")
        return []

    endpoint = f"{url}/rest/v1/watchlists"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                endpoint,
                params={
                    "select": "*",
                    "user_id": f"eq.{user_id}",
                    "order": "created_at.desc",
                },
                headers=headers,
            )
            r.raise_for_status()
            rows = r.json() or []
            return [{"ticker": r["ticker"], "market": r.get("market", "US")} for r in rows]
    except Exception as exc:
        log.warning("_load_portfolio_from_supabase failed for %s: %s", user_id, exc)
        return []


def _infer_portfolio_market(portfolio_stocks: list[dict], explicit_market: str | None) -> str:
    """Auto-detect market from portfolio tickers. If explicit_market is None or 'US',
    checks if majority of stocks are IN — overrides to 'IN' when stocks are Indian."""
    if not portfolio_stocks:
        return explicit_market or "US"
    try:
        from nq_api.universe import IN_DEFAULT
        in_set = frozenset(IN_DEFAULT)
        n_in = sum(1 for s in portfolio_stocks if s.get("ticker", "").upper() in in_set)
        if n_in >= len(portfolio_stocks) * 0.5:
            return "IN"
    except Exception:
        pass
    return explicit_market or "US"


def _detect_stock_market(ticker: str) -> str:
    """Detect market (US or IN) for a single ticker."""
    if not ticker:
        return "US"
    t = ticker.upper()
    if t.endswith(".NS") or t.endswith(".BO"):
        return "IN"
    try:
        from nq_api.universe import IN_DEFAULT
        if t in frozenset(IN_DEFAULT):
            return "IN"
    except Exception:
        pass
    return "US"


def _validate_and_fill_portfolio_prices(
    portfolio_stocks: list[dict], market: str
) -> tuple[list[dict], list[str]]:
    """Validate and fill entry_price, target_price, stop_loss for portfolio stocks.
    Replaces 'Live N/A' placeholders with real prices and computes
    target/stop_loss deterministically from the live entry price.

    Each stock is resolved with its own market (US/IN) — mixed-market portfolios
    (e.g. "invest ₹10L in India + $5K in US") work correctly.

    Returns (corrected_stocks, fill_notes).
    """
    from nq_api.data_builder import _get_yf_session, _fetch_yf_info_cached

    if not portfolio_stocks:
        return portfolio_stocks, []

    fill_notes = []
    _CACHED_PATTERN = re.compile(
        r"(?:cached|enter near|enter at|market price|current price"
        r"|stale|estimated|not available|price not found|n/a"
        r"|currently trading|approx|around ~?\$|enter \w+ price)", re.IGNORECASE
    )

    # -- Phase 0: FMP batch_quotes pre-fetch (single API call, ~200ms, most reliable) --
    fmp_prices: dict[str, dict] = {}
    fmp_client = None
    try:
        from nq_data.fmp import get_fmp_client
        fmp_client = get_fmp_client()
        if fmp_client._enabled:
            all_tickers: list[str] = []
            for s in portfolio_stocks:
                t = s.get("ticker", "")
                if not t:
                    continue
                all_tickers.append(t)  # bare ticker for US stocks
                sm = _detect_stock_market(t)
                if sm == "IN" and "." not in t:
                    all_tickers.append(f"{t}.NS")
                    all_tickers.append(f"{t}.BO")
            if all_tickers:
                fmp_prices = fmp_client.get_batch_quotes(all_tickers) or {}
                log.debug("FMP batch_quotes: requested %d tickers, got %d prices",
                          len(all_tickers), len(fmp_prices))
    except Exception as exc:
        log.debug("FMP batch_quotes pre-fetch failed: %s", exc)

    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        if not ticker:
            continue

        stock_market = _detect_stock_market(ticker)
        cur = "Rs." if stock_market == "IN" else "$"
        sym = ticker + ".NS" if stock_market == "IN" and "." not in ticker else ticker
        live_price = None
        price_source = None

        # -- Tier 1: FMP batch_quotes result (from Phase 0 pre-fetch) --
        for lookup_key in (ticker, sym, f"{ticker}.NS", f"{ticker}.BO"):
            batch = fmp_prices.get(lookup_key, {})
            if batch and batch.get("price"):
                live_price = float(batch["price"])
                price_source = "fmp_batch"
                break

        # -- Tier 2: FMP profile fallback (individual call) --
        if (not live_price or live_price <= 0) and fmp_client and fmp_client._enabled:
            try:
                profile = fmp_client.get_profile(sym)
                if profile and profile.get("price"):
                    live_price = float(profile["price"])
                    price_source = "fmp_profile"
            except Exception as exc:
                log.debug("FMP profile fallback failed for %s: %s", sym, exc)

        # -- Tier 2b: nq-openbb yfinance proxy (reliable on Render, US + IN) --
        if not live_price or live_price <= 0:
            lp, lp_source = get_live_price(ticker, stock_market)
            if lp:
                live_price = lp
                price_source = lp_source
                fill_notes.append(f"{ticker} price: {lp_source} ({live_price:.2f})")

        # -- Tier 3: yfinance (cached + direct) --
        if not live_price or live_price <= 0:
            info = _fetch_yf_info_cached(sym)
            if info.get("_cached_ok"):
                live_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if live_price and live_price > 0:
                    price_source = "yfinance_cached"
            if not live_price or live_price <= 0:
                try:
                    t = yf.Ticker(sym, session=_get_yf_session())
                    info_direct = t.info or {}
                    live_price = info_direct.get("currentPrice") or info_direct.get("regularMarketPrice")
                    if live_price and live_price > 0:
                        price_source = "yfinance_direct"
                except Exception as exc:
                    log.debug("yfinance direct failed for %s: %s", sym, exc)

        # -- Tier 4: yf.download (often more reliable than Ticker.info on cloud) --
        if not live_price or live_price <= 0:
            try:
                import yfinance as yf
                hist = yf.download(sym, period="5d", progress=False, auto_adjust=True,
                                   threads=False, session=_get_yf_session())
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    close = hist["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close[sym] if sym in close.columns else close.iloc[:, 0]
                    close = close.dropna()
                    if len(close) > 0:
                        live_price = float(close.iloc[-1])
                        price_source = "yf_download"
            except Exception as exc:
                log.debug("yf.download failed for %s: %s", sym, exc)

        # -- Tier 4b: stock_snapshot (30-min refresh, reliable for IN on Render) --
        if not live_price or live_price <= 0:
            snap_price = _snapshot_price(ticker, stock_market)
            if snap_price:
                live_price = snap_price
                price_source = "stock_snapshot"
                fill_notes.append(f"{ticker} price: stock_snapshot ({live_price:.2f})")

        # -- Tier 5: score_cache (up to 7 days stale) --
        if not live_price or live_price <= 0:
            try:
                from nq_api.cache.score_cache import read_one as _sc_read_one
                sc = _sc_read_one(ticker.upper(), stock_market, max_age_seconds=604800)  # 7 days
                if sc and sc.get("current_price"):
                    live_price = float(sc["current_price"])
                    price_source = "score_cache_7d"
                    fill_notes.append(f"{ticker} price: stale cache 7d ({live_price:.2f})")
            except Exception:
                pass

        # -- Tier 6: _fetch_one with correct market --
        if not live_price or live_price <= 0:
            try:
                from nq_api.data_builder import _fetch_one as _fo
                fund = _fo(ticker, stock_market, fast_pe=True)
                if fund.get("current_price"):
                    live_price = float(fund["current_price"])
                    price_source = "fetch_one"
            except Exception as exc:
                log.debug("_fetch_one fallback failed for %s/%s: %s", ticker, stock_market, exc)

        if not live_price or live_price <= 0:
            # All sources failed
            stock["price_unavailable"] = True
            stock["entry_price"] = "Price unavailable"
            stock["target_price"] = "N/A"
            stock["stop_loss"] = "N/A"
            fill_notes.append(f"{ticker}: price unavailable from all sources (tried FMP_batch+FMP_profile+yf_cached+yf_direct+yf_download+score_cache+fetch_one)")
            log.warning("Portfolio price unavailable for %s/%s (market=%s)", ticker, sym, stock_market)
            continue

        if price_source:
            log.debug("Portfolio price for %s/%s: %.2f via %s (market=%s)", ticker, sym, live_price, price_source, stock_market)

        entry_str = stock.get("entry_price", "")
        needs_fill = (
            not entry_str
            or "N/A" in entry_str
            or "Live N/A" in entry_str
            or "unavailable" in entry_str.lower()
            or "enter at market" in entry_str.lower()
            or "enter near" in entry_str.lower()
            or "market price" in entry_str.lower()
            or "current price" in entry_str.lower()
            or _CACHED_PATTERN.search(entry_str)
        )

        # If entry_price has text but no digits, it's LLM placeholder — force fill
        if not needs_fill and entry_str:
            if not any(c.isdigit() for c in entry_str):
                needs_fill = True

        # Check if existing entry price is stale (>5% off live)
        entry_off = 0.0
        if not needs_fill and entry_str:
            nums = re.findall(r'[\d,]+\.?\d*', entry_str)
            if nums:
                try:
                    entry_num = float(nums[0].replace(",", ""))
                    if entry_num > 0:
                        entry_off = abs(live_price - entry_num) / entry_num
                        if entry_off > 0.05:
                            needs_fill = True
                except ValueError:
                    pass

        if needs_fill:
            # Compute entry range: live price +/-2%
            entry_low = live_price * 0.98
            entry_high = live_price * 1.02
            if stock_market == "IN":
                stock["entry_price"] = f"Rs.{live_price:,.0f} (Rs.{entry_low:,.0f}-Rs.{entry_high:,.0f})"
            else:
                stock["entry_price"] = f"${live_price:,.2f} (${entry_low:,.2f}-${entry_high:,.2f})"
            fill_notes.append(f"{ticker} entry: live price {cur}{live_price:,.2f} via {price_source}")

        # Fill target_price if missing or looks like placeholder
        target_str = stock.get("target_price", "")
        if not target_str or "N/A" in target_str or "unavailable" in target_str.lower():
            target_price = live_price * 1.15
            if stock_market == "IN":
                stock["target_price"] = f"Rs.{target_price:,.0f} (+15%)"
            else:
                stock["target_price"] = f"${target_price:,.2f} (+15%)"

        # Fill stop_loss if missing
        stop_str = stock.get("stop_loss", "")
        if not stop_str or "N/A" in stop_str or "unavailable" in stop_str.lower():
            stop_price = live_price * 0.90
            if stock_market == "IN":
                stock["stop_loss"] = f"Rs.{stop_price:,.0f} (-10%)"
            else:
                stock["stop_loss"] = f"${stop_price:,.2f} (-10%)"

        # Recompute risk_reward if missing or looks placeholder-ish
        rr_str = stock.get("risk_reward", "")
        if not rr_str or "N/A" in rr_str:
            try:
                nums_entry = re.findall(r'[\d,]+\.?\d*', stock.get("entry_price", ""))
                nums_target = re.findall(r'[\d,]+\.?\d*', stock.get("target_price", ""))
                nums_stop = re.findall(r'[\d,]+\.?\d*', stock.get("stop_loss", ""))
                if nums_entry and nums_target and nums_stop:
                    e = float(nums_entry[0].replace(",", ""))
                    t = float(nums_target[0].replace(",", ""))
                    s = float(nums_stop[0].replace(",", ""))
                    if e > 0 and s > 0:
                        reward = abs(t - e)
                        risk = abs(e - s)
                        if risk > 0:
                            rr = reward / risk
                            stock["risk_reward"] = f"1:{rr:.1f}"
            except (ValueError, ZeroDivisionError):
                pass

    # Safety net: stocks that escaped needs_fill but have placeholder text
    for stock in portfolio_stocks:
        if stock.get("price_unavailable"):
            continue  # already flagged
        ep = stock.get("entry_price", "")
        if ep and _CACHED_PATTERN.search(ep):
            # Already-filled prices ($154.32 ...) won't match. Only
            # LLM-generated placeholders that slipped past needs_fill.
            stock["entry_price"] = "Price unavailable"
            stock["price_unavailable"] = True
            fill_notes.append(f"{stock.get('ticker','?')}: placeholder in entry_price after fill")

    return portfolio_stocks, fill_notes
