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
        """Get comprehensive macroeconomic context including VIX, yield curve,
        Fed funds rate, CPI, HY spreads, currency rates, and market regime label.

        Use when client asks about the macro environment, interest rates,
        inflation, or wants to understand the broader economic backdrop.
        """
        try:
            from nq_api.data_builder import fetch_real_macro

            macro = fetch_real_macro()
            if not macro:
                return json.dumps({"status": "unavailable", "reason": "Macro data temporarily unavailable"})

            result = {
                "status": "ok",
                "vix": macro.get("vix"),
                "vix_level": _vix_label(macro.get("vix", 0) or 0),
                "spx_price": macro.get("spx_price"),
                "spx_return_1m": macro.get("spx_return_1m"),
                "spx_return_3m": macro.get("spx_return_3m"),
                "yield_10y": macro.get("yield_10y"),
                "yield_2y": macro.get("yield_2y"),
                "yield_curve": "inverted" if (macro.get("yield_2y", 0) or 0) > (macro.get("yield_10y", 0) or 0) else "normal",
                "fed_funds_rate": macro.get("fed_funds_rate"),
                "hy_spread": macro.get("hy_spread"),
                "hy_spread_level": _hy_label(macro.get("hy_spread", 0) or 0),
                "cpi_yoy": macro.get("cpi_yoy"),
                "nifty_price": macro.get("nifty_price"),
                "inr_usd": macro.get("inr_usd"),
                "regime_label": macro.get("regime_label", "UNKNOWN"),
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
                regime = macro.get("regime_label", "UNKNOWN") if macro else "UNKNOWN"

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
