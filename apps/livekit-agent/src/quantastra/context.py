"""Build runtime context injected at conversation start for QuantAstra agent."""

import logging

log = logging.getLogger(__name__)


async def build_greeting_context(user_id: str | None) -> str:
    """Build the initial market + portfolio context block injected with the system prompt.

    Called once when a new LiveKit room is created. Returns a text block
    with live macro data, top AI scores, and portfolio holdings (if authenticated).
    """
    parts = []

    # ── Macro context ──────────────────────────────────────────────────────
    try:
        from nq_api.data_builder import fetch_real_macro
        macro = fetch_real_macro()
        if macro:
            parts.append("CURRENT MARKET CONTEXT [VERIFIED live from FMP/yfinance]:")
            vix = macro.get("vix")
            if vix:
                parts.append(f"  VIX: {vix}")
            spx_price = macro.get("spx_price")
            spx_ret = macro.get("spx_return_1m")
            if spx_price:
                parts.append(f"  S&P 500: {spx_price}" + (f" ({spx_ret:+.1f}% 1mo)" if spx_ret else ""))
            yield_10y = macro.get("yield_10y")
            if yield_10y:
                parts.append(f"  10Y Treasury Yield: {yield_10y}%")
            fed_funds = macro.get("fed_funds_rate")
            if fed_funds:
                parts.append(f"  Fed Funds Rate: {fed_funds}%")
            hy_spread = macro.get("hy_spread")
            if hy_spread:
                parts.append(f"  High-Yield Spread: {hy_spread} bps")
            cpi = macro.get("cpi_yoy")
            if cpi:
                parts.append(f"  CPI YoY: {cpi}%")
            inr = macro.get("inr_usd")
            nifty = macro.get("nifty_price")
            if nifty:
                parts.append(f"  Nifty 50: {nifty} INR/USD: {inr or 'N/A'}")
    except Exception as exc:
        log.warning("Macro context build failed: %s", exc)

    # ── Top AI scores ──────────────────────────────────────────────────────
    try:
        from nq_api.cache.score_cache import read_top
        us_top = read_top("US", 5)
        if us_top:
            parts.append(
                "\nTOP US AI SCORES [VERIFIED]: "
                + ", ".join(f"{s['ticker']}={s['score_1_10']}/10" for s in us_top)
            )
        in_top = read_top("IN", 5)
        if in_top:
            parts.append(
                "TOP INDIA AI SCORES [VERIFIED]: "
                + ", ".join(f"{s['ticker']}={s['score_1_10']}/10" for s in in_top)
            )
    except Exception as exc:
        log.warning("Score context build failed: %s", exc)

    # ── Portfolio holdings (if authenticated) ──────────────────────────────
    if user_id:
        try:
            from nq_api.services.portfolio import _load_portfolio_from_supabase
            stocks = await _load_portfolio_from_supabase(user_id)
            if stocks:
                parts.append("\nCLIENT PORTFOLIO [VERIFIED from Supabase]:")
                total_val = sum(float(s.get("allocation_pct", 0)) for s in stocks)
                for s in stocks:
                    ticker = s.get("ticker", "???")
                    pct = float(s.get("allocation_pct", 0))
                    entry = s.get("entry_price", "unknown")
                    parts.append(f"  {ticker}: {pct:.0f}% allocation, entry {entry}")
                parts.append(f"  Total positions: {len(stocks)}")
        except Exception as exc:
            log.warning("Portfolio context build failed: %s", exc)

    return "\n".join(parts) if parts else ""
