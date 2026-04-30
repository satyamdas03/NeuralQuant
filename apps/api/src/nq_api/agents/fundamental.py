# apps/api/src/nq_api/agents/fundamental.py
"""FUNDAMENTAL analyst - financial quality, valuation, earnings trajectory."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the FUNDAMENTAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the company's financial quality, valuation, and earnings trajectory.

CRITICAL DATA RULE: The user message will contain a block of live financial data with exact numerical values.
You MUST use ONLY those exact numbers in your analysis. Never infer, estimate, or substitute values from
your training data. If gross profit margin is stated as 71.1%, you write "71.1% gross margin" - not 1%, not 70%.
If P/E is 36.3x, write "36.3x P/E" - not 3x. Treat every provided figure as authoritative and current.

Framework:
1. Profitability quality - Piotroski F-Score, gross margins, accruals (earnings quality)
2. Valuation - P/E, P/FCF, EV/EBITDA relative to sector and history
3. Earnings trajectory - estimate revisions, surprise history, guidance
4. Balance sheet strength - debt levels, interest coverage, cash generation
5. Capital allocation - buybacks, dividends, capex efficiency (ROIC)

## THRESHOLDS (use these to make calls)
- Piotroski F-Score: >7 = strong, 4-7 = moderate, <4 = weak
- Gross margin: >60% = strong, 30-60% = moderate, <30% = weak
- P/E: <15 = undervalued (if quality high), 15-25 = fair, >25 = expensive (unless high growth)
- P/B: <1.5 = value, 1.5-4 = fair, >4 = expensive
- ROE: >20% = strong, 10-20% = moderate, <10% = weak, NEGATIVE = value destruction (automatic BEAR)
- Debt/Equity: <0.5 = strong, 0.5-1.5 = moderate, >1.5 = concerning
- Revenue growth: >20% = strong, 5-20% = moderate, <5% = weak, NEGATIVE = shrinking (BEAR signal)
- FCF yield: >8% = strong, 3-8% = moderate, <3% = weak

## RED FLAGS (automatic BEAR triggers — if ANY of these are true, you MUST output BEAR)
- Negative ROE: company is destroying shareholder value
- P/E >25 with ROE <10%: overvalued for the return generated
- Piotroski <3: poor financial health across multiple metrics
- Gross margin <25%: structurally weak business
- Debt/Equity >2.0: balance sheet risk

## REASONING PROTOCOL (mandatory)
1. CITE specific data points — never say "good fundamentals", say "Piotroski 8/9, gross margin 68%"
2. COMPARE to sector average or benchmark — "P/E 14 vs sector median 22"
3. CONCLUDE with a "why this stance" edge statement — "BULL because quality metrics are in top quartile" or "BEAR because P/E at 36x with only 8% revenue growth prices in perfection"
4. If data is missing, state WHICH data points are missing and what they would change

Response format - strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on fundamental investment merit, citing the provided data figures]
KEY_POINTS:
- [Point 1 - must cite specific numbers from the provided data]
- [Point 2 - must cite specific numbers from the provided data]
- [Point 3 - must cite specific numbers from the provided data]

You must be equally willing to output BEAR as BULL — if valuation is stretched or quality is weak, say BEAR."""


class FundamentalAgent(BaseAnalystAgent):
    agent_name = "FUNDAMENTAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        # gross_profit_margin comes in as a decimal (e.g. 0.711 = 71.1%) - convert to %
        raw_gpm = context.get('gross_profit_margin', None)
        if raw_gpm is not None and raw_gpm != 'N/A':
            gpm_display = f"{float(raw_gpm) * 100:.1f}%"
        else:
            gpm_display = 'N/A'

        # pe_ttm and pb_ratio
        pe = context.get('pe_ttm', 'N/A')
        pb = context.get('pb_ratio', 'N/A')
        beta = context.get('beta', 'N/A')

        # ROE display
        raw_roe = context.get('roe', None)
        if raw_roe is not None and raw_roe != 'N/A':
            roe_display = f"{float(raw_roe) * 100:.1f}%"
        else:
            roe_display = 'N/A'

        # Revenue growth display
        rev_g = context.get('revenue_growth', None)
        rev_display = f"{rev_g}%" if rev_g is not None and rev_g != 'N/A' else 'N/A'

        # Debt/Equity
        de = context.get('debt_equity', None)
        de_display = f"{de}" if de is not None and de != 'N/A' else 'N/A'

        # Sector median comparison
        sector = context.get('sector', '')
        sector_section = ""
        if sector and sector != 'Unknown':
            sector_lines = []
            sector_fields = [
                ('sector_median_pe_ttm', 'P/E', 'x'),
                ('sector_median_roe', 'ROE', '%'),
                ('sector_median_gross_profit_margin', 'Gross margin', '%'),
                ('sector_median_debt_equity', 'D/E', ''),
                ('sector_median_composite_score', 'Composite', ''),
            ]
            for key, label, unit in sector_fields:
                val = context.get(key)
                if val is not None:
                    if unit == '%':
                        sector_lines.append(f"  {label}: {float(val) * 100:.1f}%")
                    else:
                        sector_lines.append(f"  {label}: {val}{unit}")
            if sector_lines:
                sector_section = f"""
Sector median ({sector}):
{chr(10).join(sector_lines)}

Compare this stock's metrics to the sector median above when making your assessment."""

        return f"""Analyse the fundamental investment merit of {ticker}.

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Financial data (live as of today):
- Piotroski F-Score: {context.get('piotroski', 'N/A')} / 9 (higher = stronger fundamentals)
- Gross profit margin: {gpm_display}
- ROE: {roe_display}
- Revenue growth YoY: {rev_display}
- Debt/Equity: {de_display}
- Quality composite percentile: {context.get('quality_percentile', 'N/A')} (0-1 scale, higher = better quality vs universe)
- Trailing P/E ratio: {pe}x
- Price-to-Book ratio: {pb}x
- Beta (market sensitivity): {beta}
- Accruals ratio: {context.get('accruals_ratio', 'N/A')} (lower/negative is better - indicates cash earnings quality)
- Market cap: {context.get('market_cap', 'N/A')}
- 52-week range: {context.get('week52_low', 'N/A')} – {context.get('week52_high', 'N/A')}
- Analyst target mean: {context.get('analyst_target_mean', 'N/A')}
- AI composite score: {context.get('composite_score', 'N/A')} (0-1 scale)
{sector_section}
Provide your fundamental stance on {ticker}. Reference the specific numbers above in your key points."""
