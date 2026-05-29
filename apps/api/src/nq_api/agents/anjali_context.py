"""Anjali Value Screener context builder for PARA-DEBATE agents.

Injects quintile-scored cross-sectional data into all 7 agent prompts,
giving them deep fundamental + valuation + growth + risk context
that the 5-factor engine alone doesn't provide.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_anjali_context(enrichment: dict | None) -> str:
    """Build Anjali context string for injection into agent prompts.

    Args:
        enrichment: Dict from anjali_enrichment table (via get_anjali_enrichment).
                    Keys: ticker, market, composite_anjali_score, growth_score,
                    return_score, valuation_score, risk_score, future_pe, future_peg,
                    loss_profit_yoy, loss_profit_ttm, loss_profit_qoq, etc.

    Returns:
        Formatted context string, or empty string if no enrichment available.
    """
    if not enrichment:
        return ""

    # Extract scores
    growth = enrichment.get("growth_score")
    ret = enrichment.get("return_score")
    val = enrichment.get("valuation_score")
    risk = enrichment.get("risk_score")
    composite = enrichment.get("composite_anjali_score")

    # Extract key metrics
    future_pe = enrichment.get("future_pe")
    future_peg = enrichment.get("future_peg")
    ttm_peg = enrichment.get("ttm_peg")
    pe = enrichment.get("pe_ratio")
    ev_sales = enrichment.get("ev_sales")
    ev_ebitda = enrichment.get("ev_ebitda")

    # Loss flags
    is_loss_yoy = enrichment.get("loss_profit_yoy", False)
    is_loss_ttm = enrichment.get("loss_profit_ttm", False)
    is_loss_qoq = enrichment.get("loss_profit_qoq", False)

    # Format loss flag summary
    loss_flags = []
    if is_loss_yoy:
        loss_flags.append("YoY net loss")
    if is_loss_ttm:
        loss_flags.append("TTM net loss")
    if is_loss_qoq:
        loss_flags.append("QoQ net loss")
    loss_summary = " | ".join(loss_flags) if loss_flags else "None (profitable)"

    # Build context block
    lines = [
        "\nANJALI VALUE SCREENER DATA (quintile-scored cross-sectionally vs index peers):",
    ]

    # Valuation metrics (most actionable)
    val_parts = []
    if pe is not None:
        val_parts.append(f"P/E {pe}x")
    if future_pe is not None:
        val_parts.append(f"Future P/E {future_pe}x")
    if ttm_peg is not None:
        val_parts.append(f"TTM PEG {ttm_peg}")
    if future_peg is not None:
        val_parts.append(f"Future PEG {future_peg}")
    if ev_sales is not None:
        val_parts.append(f"EV/Sales {ev_sales}")
    if ev_ebitda is not None:
        val_parts.append(f"EV/EBITDA {ev_ebitda}")
    if val_parts:
        lines.append(f"  Valuation: {' | '.join(val_parts)}")

    # Loss flags
    lines.append(f"  Is loss-making: {loss_summary}")

    # Quintile scores
    score_parts = []
    if growth is not None:
        score_parts.append(f"Growth Score: {growth}/4")
    if ret is not None:
        score_parts.append(f"Return Score: {ret}/4")
    if val is not None:
        score_parts.append(f"Valuation Score: {val}/4")
    if risk is not None:
        score_parts.append(f"Risk Score: {risk}/4")
    if composite is not None:
        score_parts.append(f"COMPOSITE ANJALI: {composite}/16")
    if score_parts:
        lines.append(f"  Quintile Scores (each -4 to +4 vs same-index peers):")
        for part in score_parts:
            lines.append(f"    {part}")

    # Scoring logic reminder (CRITICAL — agents must understand this)
    lines.append("  Scoring logic: Valuation Q1 (cheapest) = 0 not +1 (value trap risk); Q2 = +1 sweet spot.")
    lines.append("                 Risk Q1 (safest) = -0.5 (missed returns); Q4 = +1 sweet spot.")
    lines.append("                 Loss-making companies always score -1 on growth columns regardless of quintile.")

    return "\n".join(lines)