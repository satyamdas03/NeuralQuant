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

        # Additional profitability fields
        def _pct(val):
            if val is not None and val != 'N/A':
                return f"{float(val) * 100:.1f}%"
            return 'N/A'

        def _fmt(val, fmt=".2f"):
            if val is not None and val != 'N/A':
                return f"{float(val):{fmt}}"
            return 'N/A'

        roa_display = _pct(context.get('roa'))
        opm_display = _pct(context.get('operating_margin'))
        npm_display = _pct(context.get('profit_margin'))
        eg_display = _fmt(context.get('earnings_growth_yoy'), ".1f")
        ev_rev_display = _fmt(context.get('ev_revenue'))
        ev_ebitda_display = _fmt(context.get('ev_ebitda'))
        peg_display = _fmt(context.get('trailing_peg_ratio'))
        cr_display = _fmt(context.get('current_ratio'))
        qr_display = _fmt(context.get('quick_ratio'))
        fwd_eps_display = _fmt(context.get('forward_eps'))
        bv_display = _fmt(context.get('book_value'))
        div_yield_display = _pct(context.get('dividend_yield'))
        payout_display = _pct(context.get('payout_ratio'))

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

        # Data quality warnings
        dq_flags = context.get('_data_quality_flags', [])
        dq_section = ""
        if dq_flags:
            dq_section = "\n⚠ DATA QUALITY WARNINGS (these values are unreliable — treat with low confidence):\n"
            dq_section += "\n".join(f"  • {f}" for f in dq_flags)

        # ── Expanded analyst enrichment fields (20+ field expansion) ──
        def _fmt_pct(val):
            """Format a decimal (0.15 = 15%) as percentage string."""
            if val is not None and val != 'N/A':
                try:
                    return f"{float(val) * 100:.1f}%"
                except (TypeError, ValueError):
                    return 'N/A'
            return 'N/A'

        def _fmt_int(val):
            """Format large numbers with K/M/B suffix."""
            if val is not None and val != 'N/A':
                try:
                    v = int(val)
                    if v >= 1_000_000_000:
                        return f"{v/1_000_000_000:.1f}B"
                    elif v >= 1_000_000:
                        return f"{v/1_000_000:.1f}M"
                    elif v >= 1_000:
                        return f"{v/1_000:.1f}K"
                    return f"{v:,}"
                except (TypeError, ValueError):
                    return 'N/A'
            return 'N/A'

        roic_display = _fmt(context.get('roic'))
        short_ratio_display = _fmt(context.get('short_ratio'))
        avg_volume_display = _fmt_int(context.get('avg_volume'))
        institutional_pct_display = _fmt_pct(context.get('institutional_pct'))
        insider_pct_display = _fmt_pct(context.get('insider_pct'))
        analyst_target_high = _fmt(context.get('analyst_target_high'))
        analyst_target_low = _fmt(context.get('analyst_target_low'))
        forward_pe_display = _fmt(context.get('forward_pe'))
        rev_per_share_display = _fmt(context.get('revenue_per_share'))
        fcf_display = _fmt(context.get('free_cashflow'), ".0f")
        num_analysts = context.get('number_of_analyst_opinions', 'N/A')
        rev_growth_yoy_display = _fmt(context.get('revenue_growth_yoy'), ".1f")
        fifty_day_avg_display = _fmt(context.get('fifty_day_avg'))
        two_hundred_day_avg_display = _fmt(context.get('two_hundred_day_avg'))

        return f"""Analyse the fundamental investment merit of {ticker}.

IMPORTANT: Every value below marked [VERIFIED] is LIVE data from FMP/yfinance — authoritative. Use ONLY these exact numbers. Never substitute from training data. If a field shows N/A, it is genuinely unavailable — do not fabricate.

Financial data [VERIFIED] (live as of today):
- Piotroski F-Score: {context.get('piotroski', 'N/A')} / 9 [VERIFIED] (higher = stronger fundamentals)
- Gross profit margin: {gpm_display} [VERIFIED]
- Operating margin: {opm_display} [VERIFIED]
- Net profit margin: {npm_display} [VERIFIED]
- ROE: {roe_display} [VERIFIED]
- ROA: {roa_display} [VERIFIED]
- ROIC (Return on Invested Capital): {roic_display} [VERIFIED]
- Revenue growth YoY: {rev_display} [VERIFIED]
- Earnings growth YoY: {eg_display}% [VERIFIED]
- Debt/Equity: {de_display} [VERIFIED]
- Current ratio: {cr_display} [VERIFIED]
- Quick ratio: {qr_display} [VERIFIED]
- Quality composite percentile: {context.get('quality_percentile', 'N/A')} [VERIFIED] (0-1 scale)
- Trailing P/E ratio: {pe}x [VERIFIED]
- Forward P/E ratio: {forward_pe_display}x [VERIFIED]
- Price-to-Book ratio: {pb}x [VERIFIED]
- PEG ratio (trailing): {peg_display} [VERIFIED]
- EV/Revenue: {ev_rev_display}x [VERIFIED]
- EV/EBITDA: {ev_ebitda_display}x [VERIFIED]
- Beta (market sensitivity): {beta} [VERIFIED]
- Accruals ratio: {context.get('accruals_ratio', 'N/A')} [VERIFIED] (lower/negative = better)
- Market cap: {context.get('market_cap', 'N/A')} [VERIFIED]
- 52-week range: {context.get('week52_low', 'N/A')} – {context.get('week52_high', 'N/A')} [VERIFIED]
- 50-day moving average: {fifty_day_avg_display} [VERIFIED]
- 200-day moving average: {two_hundred_day_avg_display} [VERIFIED]
- Analyst target mean: {context.get('analyst_target_mean', 'N/A')} [VERIFIED]
- Analyst target high: {analyst_target_high} [VERIFIED]
- Analyst target low: {analyst_target_low} [VERIFIED]
- Number of analysts: {num_analysts} [VERIFIED]
- Forward EPS: {fwd_eps_display} [VERIFIED]
- Book value per share: {bv_display} [VERIFIED]
- Dividend yield: {div_yield_display} [VERIFIED]
- Payout ratio: {payout_display} [VERIFIED]
- Short ratio: {short_ratio_display} [VERIFIED] (days to cover)
- Short interest % of float: {context.get('short_interest_pct', 'N/A')} [VERIFIED]
- Average volume: {avg_volume_display} [VERIFIED]
- Institutional ownership: {institutional_pct_display} [VERIFIED]
- Insider ownership: {insider_pct_display} [VERIFIED]
- Free cashflow: {fcf_display} [VERIFIED]
- Revenue per share: {rev_per_share_display} [VERIFIED]
- AI composite score: {context.get('composite_score', 'N/A')} [VERIFIED] (0-1 scale)
{sector_section}{dq_section}
Provide your fundamental stance on {ticker}. Reference the specific numbers above in your key points."""
