"""Portfolio-specific logic -- intent detection, price filling, profile building."""
import logging
import re

import yfinance as yf
import pandas as pd

from nq_api.services.constants import _PORTFOLIO_KEYWORDS
from nq_api.services.prompts import _PROFILE_PROMPT_TEMPLATE
from nq_api.schemas import UserProfile

log = logging.getLogger(__name__)


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


def _validate_and_fill_portfolio_prices(
    portfolio_stocks: list[dict], market: str
) -> tuple[list[dict], list[str]]:
    """Validate and fill entry_price, target_price, stop_loss for portfolio stocks.
    Replaces 'Live N/A' placeholders with real prices and computes
    target/stop_loss deterministically from the live entry price.

    Price source priority (US): FMP quote -> yfinance -> FMP profile -> score_cache (7d)
    Price source priority (IN): yfinance (.NS) -> FMP profile -> score_cache (7d)

    Returns (corrected_stocks, fill_notes).
    """
    from nq_api.data_builder import _yf_symbol, _get_yf_session, _fetch_yf_info_cached

    if not portfolio_stocks:
        return portfolio_stocks, []

    fill_notes = []
    cur = "Rs." if market == "IN" else "$"
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
            all_tickers = [
                s.get("ticker", "")
                for s in portfolio_stocks
                if s.get("ticker")
            ]
            if market == "IN":
                # Add .NS and .BO suffix variants — some stocks are NSE, some BSE
                ns_tickers = [t if "." in t else f"{t}.NS" for t in all_tickers]
                bo_tickers = [t.replace(".NS", ".BO") for t in ns_tickers]
                all_tickers = ns_tickers + bo_tickers
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

        sym = ticker + ".NS" if market == "IN" and "." not in ticker else ticker
        live_price = None
        price_source = None

        # -- Tier 1: FMP batch_quotes result (from Phase 0 pre-fetch) --
        for lookup_key in (sym, ticker, f"{ticker}.NS", f"{ticker}.BO"):
            batch = fmp_prices.get(lookup_key, {})
            if batch and batch.get("price"):
                live_price = float(batch["price"])
                price_source = "fmp_batch"
                break

        # -- Tier 2: FMP profile fallback (individual call, works for IN stocks) --
        if not live_price or live_price <= 0:
            try:
                profile = fmp_client.get_profile(sym) if (fmp_client and fmp_client._enabled) else None
                if profile and profile.get("price"):
                    live_price = float(profile["price"])
                    price_source = "fmp_profile"
            except Exception as exc:
                log.debug("FMP profile fallback failed for %s: %s", sym, exc)

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

        # -- Price Tier 2: score_cache (up to 7 days stale) --
        if not live_price or live_price <= 0:
            try:
                from nq_api.cache.score_cache import read_one as _sc_read_one
                sc = _sc_read_one(ticker.upper(), market, max_age_seconds=604800)  # 7 days
                if sc and sc.get("current_price"):
                    live_price = float(sc["current_price"])
                    price_source = "score_cache_7d"
                    fill_notes.append(f"{ticker} price: stale cache 7d ({live_price:.2f})")
            except Exception:
                pass

        # -- Price Tier 3: _fetch_one (proven pipeline for IN stocks, FMP+yfinance) --
        if not live_price or live_price <= 0:
            try:
                from nq_api.data_builder import _fetch_one as _fo
                fund = _fo(ticker, market, fast_pe=True)
                if fund.get("current_price"):
                    live_price = float(fund["current_price"])
                    price_source = "fetch_one"
            except Exception as exc:
                log.debug("_fetch_one fallback failed for %s: %s", ticker, exc)

        if not live_price or live_price <= 0:
            # All sources failed
            stock["price_unavailable"] = True
            stock["entry_price"] = "Price unavailable"
            stock["target_price"] = "N/A"
            stock["stop_loss"] = "N/A"
            fill_notes.append(f"{ticker}: price unavailable from all sources (tried FMP_batch+FMP_profile+yf_cached+yf_direct+yf_download+score_cache+fetch_one)")
            log.warning("Portfolio price unavailable for %s/%s (market=%s)", ticker, sym, market)
            continue

        if price_source:
            log.debug("Portfolio price for %s/%s: %.2f via %s", ticker, sym, live_price, price_source)

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
            if market == "IN":
                stock["entry_price"] = f"Rs.{live_price:,.0f} (Rs.{entry_low:,.0f}-Rs.{entry_high:,.0f})"
            else:
                stock["entry_price"] = f"${live_price:,.2f} (${entry_low:,.2f}-${entry_high:,.2f})"
            fill_notes.append(f"{ticker} entry: live price {cur}{live_price:,.2f} via {price_source}")

        # Fill target_price if missing or looks like placeholder
        target_str = stock.get("target_price", "")
        if not target_str or "N/A" in target_str or "unavailable" in target_str.lower():
            target_price = live_price * 1.15
            if market == "IN":
                stock["target_price"] = f"Rs.{target_price:,.0f} (+15%)"
            else:
                stock["target_price"] = f"${target_price:,.2f} (+15%)"

        # Fill stop_loss if missing
        stop_str = stock.get("stop_loss", "")
        if not stop_str or "N/A" in stop_str or "unavailable" in stop_str.lower():
            stop_price = live_price * 0.90
            if market == "IN":
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
