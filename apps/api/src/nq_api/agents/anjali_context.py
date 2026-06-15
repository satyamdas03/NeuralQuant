"""QuantFactor Engine context builder for PARA-DEBATE agents.

Injects quintile-scored cross-sectional data into all 7 agent prompts,
giving them deep fundamental + valuation + growth + risk context
that the 5-factor engine alone doesn't provide.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_anjali_context(enrichment: dict | None) -> str:
    """Build QuantFactor context string for injection into agent prompts.

    Args:
        enrichment: Dict from anjali_enrichment table (via get_anjali_enrichment).
                    Keys: ticker, market, composite_anjali_score, growth_score,
                    return_score, valuation_score, risk_score, g_score,
                    risk_eff_score, irs_raw, irs_pct, future_pe, future_peg,
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

    # IRS scores (Phase 3)
    g_score = enrichment.get("g_score")
    risk_eff = enrichment.get("risk_eff_score")
    irs_raw = enrichment.get("irs_raw")
    irs_pct = enrichment.get("irs_pct")

    # Extract key metrics
    future_pe = enrichment.get("future_pe")
    future_peg = enrichment.get("future_peg")
    ttm_peg = enrichment.get("ttm_peg")
    pe = enrichment.get("pe_ratio")
    ev_sales = enrichment.get("ev_sales")
    ev_ebitda = enrichment.get("ev_ebitda")
    sector = enrichment.get("sector")
    market = enrichment.get("market", "US")

    # Earnings-decline flags. NOTE: these are net-profit GROWTH < 0 in a period
    # (see quantfactor_sync.py), i.e. earnings *declined* — NOT an actual net loss.
    # Labeling them "net loss" made the LLM call profitable names (e.g. AAPL)
    # loss-making. Describe them as declines so the model states it truthfully.
    is_decline_yoy = enrichment.get("loss_profit_yoy", False)
    is_decline_ttm = enrichment.get("loss_profit_ttm", False)
    is_decline_qoq = enrichment.get("loss_profit_qoq", False)

    decline_flags = []
    if is_decline_yoy:
        decline_flags.append("YoY earnings decline")
    if is_decline_ttm:
        decline_flags.append("TTM earnings decline")
    if is_decline_qoq:
        decline_flags.append("QoQ earnings decline")
    loss_summary = " | ".join(decline_flags) if decline_flags else "None (earnings growing or flat)"

    # Build context block
    lines = [
        "\nQUANTFACTOR ENGINE DATA (quintile-scored cross-sectionally vs index peers):",
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

    # Earnings-decline flags (NOT actual losses — see note above)
    lines.append(f"  Earnings trend: {loss_summary}")

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
        score_parts.append(f"COMPOSITE QF: {composite}/16")
    if score_parts:
        lines.append(f"  Quintile Scores (each -4 to +4 vs same-index peers):")
        for part in score_parts:
            lines.append(f"    {part}")

    # IRS (Investment Readiness Score) — the north star metric
    irs_parts = []
    if g_score is not None:
        irs_parts.append(f"G Score (QCS): {g_score}/12")
    if risk_eff is not None:
        irs_parts.append(f"Risk Eff Score (RES): {risk_eff}/8")
    if irs_raw is not None:
        irs_parts.append(f"IRS Raw: {irs_raw}/20")
    if irs_pct is not None:
        irs_parts.append(f"IRS%: {irs_pct}%")
    if irs_parts:
        lines.append(f"  Investment Readiness Score (IRS):")
        for part in irs_parts:
            lines.append(f"    {part}")
        # Interpret IRS thresholds
        if irs_pct is not None:
            if irs_pct > 65:
                lines.append(f"    → STRONG BUY candidate (IRS% > 65%)")
            elif irs_pct >= 45:
                lines.append(f"    → MODERATE — watchlist candidate (IRS% 45-65%)")
            elif irs_pct >= 30:
                lines.append(f"    → WEAK — avoid or sell (IRS% 30-45%)")
            else:
                lines.append(f"    → VERY WEAK — sell signal (IRS% < 30%)")
        # Sell signals
        if g_score is not None and g_score < -4:
            lines.append(f"    ⚠ SELL SIGNAL: G Score < -4 (deeply negative fundamental conviction)")
        if risk_eff is not None and risk_eff < -3.5:
            lines.append(f"    ⚠ SELL SIGNAL: Risk Eff Score < -3.5 (deeply negative risk-adjusted)")
        if g_score is not None and g_score < -0.5:
            lines.append(f"    ⚠ NEUTRAL ZONE: G Score < -0.5 — may take significant time to show returns")

    # Mining & Metals exclusion for India
    if market == "IN" and sector and sector.lower() in ("mining", "metals", "mining & metals"):
        lines.append("  🚫 EXCLUDED: Mining & Metals sector — always excluded from India recommendations")

    # Scoring logic reminder (CRITICAL — agents must understand this)
    lines.append("  Scoring logic: Valuation Q1 (cheapest) = 0 not +1 (value trap risk); Q2 = +1 sweet spot.")
    lines.append("                 Risk Q1 (safest) = -0.5 (missed returns); Q4 = +1 sweet spot.")
    lines.append("                 Loss-making companies always score -1 on growth columns regardless of quintile.")
    lines.append("                 G Score = Growth + Return + Valuation (-12 to +12).")
    lines.append("                 Risk Eff Score = Risk Score × 2.0 (-8 to +8). Q4 risk sweet spot → +2.0 per column.")
    lines.append("                 IRS = G Score + Risk Eff Score. IRS% = ((IRS+20)/40)×100. North star metric.")

    return "\n".join(lines)