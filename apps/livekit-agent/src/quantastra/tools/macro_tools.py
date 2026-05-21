"""Macroeconomic tools mixin — regime, VIX, yield curve, market regime."""

from __future__ import annotations

import json
import logging

from livekit.agents import function_tool

log = logging.getLogger(__name__)


class MacroToolsMixin:
    """Macroeconomic data tools — regime, VIX, yield curve, market regime."""

    @function_tool
    async def get_macro_context(self) -> str:
        """Get comprehensive macro context: VIX, yield curve (normal/inverted),
        10Y and 2Y yields, Fed funds rate, CPI inflation, HY credit spreads,
        ISM manufacturing PMI, S&P 500 returns. Use for macro backdrop.

        VOICE: Tell the macro story conversationally. "The macro picture is
        constructive — VIX is calm at eighteen, the Fed is on hold at four
        and a quarter percent, inflation has cooled to under three percent,
        and credit markets are healthy with tight spreads."
        Don't recite field names like a dashboard readout.
        """
        try:
            from nq_api.data_builder import fetch_real_macro

            macro = fetch_real_macro()
            if not macro:
                return json.dumps({"status": "unavailable", "reason": "Macro data temporarily unavailable"})

            result = {
                "status": "ok",
                "vix": getattr(macro, "vix", None),
                "vix_level": _vix_label(getattr(macro, "vix", 0) or 0),
                "spx_return_1m": getattr(macro, "spx_return_1m", None),
                "spx_vs_200ma": getattr(macro, "spx_vs_200ma", None),
                "yield_10y": getattr(macro, "yield_10y", None),
                "yield_2y": getattr(macro, "yield_2y", None),
                "yield_curve": "inverted" if (getattr(macro, "yield_2y", 0) or 0) > (getattr(macro, "yield_10y", 0) or 0) else "normal",
                "yield_spread_2y10y": getattr(macro, "yield_spread_2y10y", None),
                "fed_funds_rate": getattr(macro, "fed_funds_rate", None),
                "hy_spread_oas": getattr(macro, "hy_spread_oas", None),
                "hy_spread_level": _hy_label(getattr(macro, "hy_spread_oas", 0) or 0),
                "cpi_yoy": getattr(macro, "cpi_yoy", None),
                "ism_pmi": getattr(macro, "ism_pmi", None),
                "fred_sourced": getattr(macro, "fred_sourced", False),
            }
            result = {k: v for k, v in result.items() if v is not None}
            return json.dumps(result, default=str)
        except Exception as exc:
            log.error("get_macro_context failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_regime_label(self) -> str:
        """Get the current market regime label (e.g. RISK_ON, RISK_OFF, NEUTRAL)
        based on NeuralQuant's HMM model. The regime helps determine appropriate
        strategy — aggressive in RISK_ON, defensive in RISK_OFF.

        Use when client asks about market conditions or what strategy to use.
        """
        try:
            from nq_api.cache.score_cache import read_top

            top = read_top("US", 1)
            if top and top[0].get("regime_label"):
                regime = top[0]["regime_label"]
            else:
                from nq_api.data_builder import fetch_real_macro
                macro = fetch_real_macro()
                regime = getattr(macro, "regime_label", None) or "UNKNOWN"

            return json.dumps({"status": "ok", "regime": regime})
        except Exception as exc:
            log.error("get_regime_label failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})

    @function_tool
    async def get_vix_level(self) -> str:
        """Get the current VIX (Volatility Index) level with interpretation.
        Returns VIX value and classification (complacent/low/moderate/elevated/high/extreme).

        Use when client asks about market volatility or fear levels.
        """
        try:
            import asyncio
            import yfinance as yf

            def _fetch():
                t = yf.Ticker("^VIX")
                info = t.fast_info or {}
                return info.get("lastPrice") or info.get("regularMarketPrice")

            vix = await asyncio.to_thread(_fetch)
            if not vix:
                return json.dumps({"status": "unavailable", "reason": "VIX data unavailable"})

            return json.dumps({
                "status": "ok",
                "vix": vix,
                "level": _vix_label(vix),
                "implication": _vix_implication(vix),
            })
        except Exception as exc:
            log.error("get_vix_level failed: %s", exc)
            return json.dumps({"status": "error", "reason": str(exc)})


def _vix_label(vix: float) -> str:
    if vix < 12:
        return "complacent"
    elif vix < 16:
        return "low"
    elif vix < 22:
        return "moderate"
    elif vix < 30:
        return "elevated"
    elif vix < 40:
        return "high"
    else:
        return "extreme"


def _vix_implication(vix: float) -> str:
    if vix < 12:
        return "Extremely low fear — historically precedes corrections. Consider hedging."
    elif vix < 16:
        return "Low volatility — favorable for trend-following and momentum strategies."
    elif vix < 22:
        return "Normal volatility — balanced approach appropriate."
    elif vix < 30:
        return "Elevated fear — widen stop-losses, reduce position sizes, favor quality."
    else:
        return "High fear — defensive posture, raise cash, favor low-volatility sectors."


def _hy_label(spread: float) -> str:
    if spread < 300:
        return "tight"
    elif spread < 500:
        return "normal"
    elif spread < 700:
        return "elevated"
    else:
        return "stressed"
