"""
Shared post-hoc validation for Ask AI responses.

Unifies validation that was scattered across query.py:
  - _VALIDATION_RULES constant
  - _extract_verified_values()
  - _validate_response_metrics() (metrics + summary)
  - _validate_portfolio_stocks() (rationale + summary P/E)

All corrections return (object, corrections_made_list) so callers can log/append.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import logging

logger = logging.getLogger(__name__)

# ── Validation rule definitions ────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationRule:
    patterns: list[str]       # case-insensitive name patterns to match
    ctx_key: str              # key in verified dict
    tolerance: float          # max allowed fractional deviation

    def format_value(self, ctx_val: float, currency_hint: str = "$") -> str:
        """Format corrected value based on metric type (P/E, Beta, Price, etc.)."""
        if "P_E" in self.ctx_key or self.ctx_key == "PE_TTM":
            return f"{ctx_val:.1f}x"
        if "BETA" in self.ctx_key:
            return f"{ctx_val:.2f}"
        if "PRICE" in self.ctx_key:
            cur = "₹" if "Rs" in currency_hint or "₹" in currency_hint else "$"
            return f"{cur}{ctx_val:,.2f}"
        return str(ctx_val)


VALIDATION_RULES: list[ValidationRule] = [
    ValidationRule(["P/E", "PE", "PRICE-EARNINGS"], "P_E_TTM", 0.15),
    ValidationRule(["BETA"], "BETA", 0.20),
    ValidationRule(["CURRENT PRICE", "SHARE PRICE"], "CURRENT_PRICE", 0.05),
    ValidationRule(["EPS"], "EPS", 0.15),
    ValidationRule(["P/B", "PRICE-BOOK", "PRICE TO BOOK"], "P_B", 0.20),
    ValidationRule(["MARKET CAP", "MCAP", "MKT CAP"], "MCAP", 0.20),
]


# ── Extract verified values from platform context ──────────────────────────────

def extract_verified_values(platform_ctx: str | None) -> dict[str, float]:
    """Extract [VERIFIED] and [ESTIMATE] values from platform context text."""
    if not platform_ctx:
        return {}
    verified: dict[str, float] = {}
    for m in re.finditer(
        r'(\w[\w/]*)=([\$₹]?[\d,]+\.?\d*)\s*\[(?:VERIFIED|ESTIMATE)\]', platform_ctx
    ):
        key = m.group(1).upper().replace("/", "_")
        val_str = m.group(2).replace(",", "").replace("$", "").replace("₹", "")
        try:
            verified[key] = float(val_str)
        except ValueError:
            pass
    return verified


# ── Metrics validation ─────────────────────────────────────────────────────────

def validate_metrics(
    metrics: list[Any],
    verified: dict[str, float],
    corrections: list[str] | None = None,
) -> tuple[list[Any], list[str]]:
    """Validate LLM-sourced metrics against [VERIFIED] values. Corrects in-place.

    Returns (metrics, corrections_list).
    """
    if corrections is None:
        corrections = []
    if not verified or not metrics:
        return metrics, corrections

    for metric in metrics:
        name = (metric.name or "").upper()
        value_str = str(metric.value) if metric.value else ""
        num_match = re.search(r'[\d,]+\.?\d*', value_str.replace(",", ""))
        if not num_match:
            continue
        try:
            llm_val = float(num_match.group())
        except ValueError:
            continue

        for rule in VALIDATION_RULES:
            if rule.ctx_key not in verified:
                continue
            if not any(p in name for p in rule.patterns):
                continue
            ctx_val = verified[rule.ctx_key]
            if ctx_val > 0 and abs(llm_val - ctx_val) / ctx_val > rule.tolerance:
                old_val = metric.value
                metric.value = rule.format_value(ctx_val, value_str)
                corrections.append(f"{name}: {old_val} -> {metric.value}")
                logger.info(
                    "Corrected LLM metric %s from %s to %s (verified: %s)",
                    name, old_val, metric.value, ctx_val,
                )
            break

    return metrics, corrections


# ── Summary price validation ───────────────────────────────────────────────────

_PRICE_PATTERNS = [
    (re.compile(r'\$([\d,]+\.?\d*)'), "$"),
    (re.compile(r'₹([\d,]+\.?\d*)'), "₹"),
    (re.compile(r'Rs\.?\s*([\d,]+\.?\d*)'), "Rs."),
]


def validate_summary_prices(
    summary: str,
    verified: dict[str, float],
    corrections: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Validate and correct any price claims in the LLM summary text.

    Returns (corrected_summary, corrections_list).
    """
    if corrections is None:
        corrections = []
    ctx_price = verified.get("CURRENT_PRICE")
    if not ctx_price or ctx_price <= 0 or not summary:
        return summary, corrections

    for pattern, cur_symbol in _PRICE_PATTERNS:
        for m in pattern.finditer(summary):
            try:
                claimed = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if abs(claimed - ctx_price) / ctx_price > 0.05:
                old_text = m.group(0)
                new_text = f"{cur_symbol}{ctx_price:,.2f}"
                summary = summary.replace(old_text, new_text, 1)
                corrections.append(f"Summary price: {old_text} -> {new_text}")
                logger.info(
                    "Corrected summary price from %s to %s (verified: %s)",
                    old_text, new_text, ctx_price,
                )
            break  # Only first occurrence per pattern
        if corrections:
            break

    return summary, corrections


# ── Convenience: full response validation ──────────────────────────────────────

def validate_response(
    metrics: list[Any],
    summary: str,
    verified: dict[str, float],
) -> tuple[list[Any], str, list[str]]:
    """Run metrics + summary price validation. Convenience for the common pattern.

    Returns (corrected_metrics, corrected_summary, corrections_list).
    """
    corrections: list[str] = []
    validate_metrics(metrics, verified, corrections)
    corrected_summary, _ = validate_summary_prices(summary, verified, corrections)
    if corrections and corrected_summary and "Corrected" not in corrected_summary:
        corrected_summary += f" [Corrected metrics: {'; '.join(corrections)}]"
    return metrics, corrected_summary, corrections


# ── Portfolio stock validation ─────────────────────────────────────────────────

def _fetch_portfolio_real_data(
    portfolio_stocks: list[dict], market: str
) -> dict[str, dict]:
    """Batch-fetch real yfinance data for all portfolio stocks."""
    from nq_api.data_builder import _fetch_yf_info_cached

    ticker_to_real: dict[str, dict] = {}
    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        if not ticker:
            continue
        # Per-stock IN detection — avoids CME.NS / AAPL.NS 404s in mixed portfolios
        is_in = ticker.upper().endswith((".NS", ".BO"))
        if not is_in and market == "IN":
            try:
                from nq_api.universe import IN_DEFAULT
                is_in = ticker.upper() in frozenset(IN_DEFAULT)
            except Exception:
                pass
        sym = ticker + ".NS" if is_in and "." not in ticker else ticker
        info = _fetch_yf_info_cached(sym)
        if not info.get("_cached_ok"):
            continue
        real_pe = info.get("trailingPE")
        real_beta = info.get("beta")
        real_div = info.get("dividendYield")
        if real_div is not None and real_div < 1:
            real_div = real_div * 100
        ticker_to_real[ticker] = {"pe": real_pe, "beta": real_beta, "div": real_div}
    return ticker_to_real


def validate_portfolio_stocks(
    portfolio_stocks: list[dict],
    market: str,
    summary: str = "",
    corrections: list[str] | None = None,
) -> tuple[list[dict], str, list[str]]:
    """Validate P/E, Beta, Yield claims in portfolio rationale + summary against real data.

    Returns (corrected_portfolio_stocks, corrected_summary, corrections_list).
    """
    if corrections is None:
        corrections = []
    if not portfolio_stocks:
        return portfolio_stocks, summary, corrections

    ticker_to_real = _fetch_portfolio_real_data(portfolio_stocks, market)

    # ── Validate per-stock rationale ──
    for stock in portfolio_stocks:
        ticker = stock.get("ticker", "")
        real = ticker_to_real.get(ticker)
        if not real:
            continue
        rationale = stock.get("rationale", "")
        if not rationale:
            continue

        # P/E claims — 10% tolerance (tighter than 20% to catch stock-to-stock swaps)
        for pe_pat in [
            re.compile(r"P/E\s*(?:of|at|is|:|=)?\s*\D{0,15}(\d+\.?\d*)", re.I),
            re.compile(r"(\d+\.?\d*)\s*x?\s*P/E\b", re.I),
        ]:
            for m in pe_pat.finditer(rationale):
                claimed = float(m.group(1))
                if (
                    real["pe"]
                    and real["pe"] > 0
                    and abs(claimed - real["pe"]) / real["pe"] > 0.10
                ):
                    old_r = rationale
                    rationale = re.sub(
                        re.escape(m.group(0)),
                        f"P/E {real['pe']:.1f}",
                        rationale,
                        count=1,
                        flags=re.I,
                    )
                    if rationale != old_r:
                        corrections.append(
                            f"{ticker} P/E: {claimed:.1f}x -> {real['pe']:.1f}x"
                        )

        # Beta claims — 25% tolerance
        for m in re.finditer(
            r"beta\s*(?:of|at|is|:|=)?\s*(\d+\.?\d*)", rationale, re.I
        ):
            claimed = float(m.group(1))
            if real["beta"] and abs(claimed - real["beta"]) / max(real["beta"], 0.1) > 0.25:
                old_r = rationale
                rationale = re.sub(
                    r"beta\s*(?:of|at|is|:|=)?\s*" + re.escape(m.group(1)),
                    f"beta {real['beta']:.2f}",
                    rationale,
                    count=1,
                    flags=re.I,
                )
                if rationale != old_r:
                    corrections.append(
                        f"{ticker} Beta: {claimed:.2f} -> {real['beta']:.2f}"
                    )

        # Yield claims — 30% tolerance
        if real["div"] and real["div"] > 0:
            for m in re.finditer(
                r"~?(\d+\.?\d*)%\s*(?:yield|dividend)", rationale, re.I
            ):
                claimed = float(m.group(1))
                if abs(claimed - real["div"]) / real["div"] > 0.30:
                    old_r = rationale
                    rationale = re.sub(
                        r"~?" + re.escape(m.group(1)) + r"%\s*(?=yield|dividend)",
                        f"~{real['div']:.1f}%",
                        rationale,
                        count=1,
                        flags=re.I,
                    )
                    if rationale != old_r:
                        corrections.append(
                            f"{ticker} Yield: {claimed:.1f}% -> {real['div']:.1f}%"
                        )

        if rationale != stock.get("rationale", ""):
            stock["rationale"] = rationale

    # ── Validate summary P/E claims near ticker mentions ──
    if summary and ticker_to_real:
        for ticker, real in ticker_to_real.items():
            if not real["pe"]:
                continue
            pattern = re.compile(
                rf"({re.escape(ticker)}[^.\n]{{0,70}}P/E\s*(?:of|at|is|:|=)?\s*\D{{0,15}})(\d+\.?\d*)",
                re.I,
            )
            for m in pattern.finditer(summary):
                claimed = float(m.group(2))
                if abs(claimed - real["pe"]) / real["pe"] > 0.10:
                    old_text = m.group(0)
                    new_text = f"{m.group(1)}{real['pe']:.1f}"
                    summary = summary.replace(old_text, new_text, 1)
                    corrections.append(
                        f"{ticker} summary P/E: {claimed:.1f}x -> {real['pe']:.1f}x"
                    )

    return portfolio_stocks, summary, corrections
