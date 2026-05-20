"""Build runtime context injected at conversation start for QuantAstra agent."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def build_greeting_context(user_id: str | None) -> str:
    """Build the initial market + portfolio context block injected with the system prompt.

    Called once when a new LiveKit room is created. Returns a text block
    with live macro data and top AI scores.
    """
    parts: list[str] = []

    # ── Macro context ──────────────────────────────────────────────────────
    try:
        from nq_api.data_builder import fetch_real_macro

        macro = fetch_real_macro()
        if macro is not None:
            parts.append("CURRENT MARKET CONTEXT [VERIFIED live from FMP/yfinance]:")
            vix = getattr(macro, "vix", None)
            if vix is not None:
                parts.append(f"  VIX: {vix:.1f}")
            spx_ret = getattr(macro, "spx_return_1m", None)
            spx_vs_ma = getattr(macro, "spx_vs_200ma", None)
            if spx_ret is not None:
                parts.append(
                    f"  S&P 500: 1mo return {spx_ret:+.1%}"
                    + (f", vs 200MA {spx_vs_ma:+.1%}" if spx_vs_ma is not None else "")
                )
            yield_10y = getattr(macro, "yield_10y", None)
            if yield_10y is not None:
                parts.append(f"  10Y Treasury Yield: {yield_10y:.2f}%")
            fed_funds = getattr(macro, "fed_funds_rate", None)
            if fed_funds is not None:
                parts.append(f"  Fed Funds Rate: {fed_funds:.2f}%")
            hy_spread = getattr(macro, "hy_spread_oas", None)
            if hy_spread is not None:
                parts.append(f"  High-Yield Spread: {hy_spread:.0f} bps")
            cpi = getattr(macro, "cpi_yoy", None)
            if cpi is not None:
                parts.append(f"  CPI YoY: {cpi:.1f}%")
            ism = getattr(macro, "ism_pmi", None)
            if ism is not None:
                parts.append(f"  ISM PMI: {ism:.1f}")
            spread_2s10s = getattr(macro, "yield_spread_2y10y", None)
            if spread_2s10s is not None:
                parts.append(f"  2s10s Yield Spread: {spread_2s10s:.2f}%")
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

    # ── Portfolio holdings — loaded via tool call, not at startup ──────────
    # Portfolio data requires an authenticated Supabase query; the agent
    # loads it on-demand via the lookup_portfolio tool.

    return "\n".join(parts) if parts else ""
