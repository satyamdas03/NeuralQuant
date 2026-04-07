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

Response format - strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on fundamental investment merit, citing the provided data figures]
KEY_POINTS:
- [Point 1 - must cite specific numbers from the provided data]
- [Point 2 - must cite specific numbers from the provided data]
- [Point 3 - must cite specific numbers from the provided data]"""


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

        return f"""Analyse the fundamental investment merit of {ticker}.

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Financial data (live as of today):
- Piotroski F-Score: {context.get('piotroski', 'N/A')} / 9 (higher = stronger fundamentals)
- Gross profit margin: {gpm_display} (this is the actual gross margin percentage - use this exact figure)
- Quality composite percentile: {context.get('quality_percentile', 'N/A')} (0-1 scale, higher = better quality vs universe)
- Trailing P/E ratio: {pe}x
- Price-to-Book ratio: {pb}x
- Beta (market sensitivity): {beta}
- Accruals ratio: {context.get('accruals_ratio', 'N/A')} (lower/negative is better - indicates cash earnings quality)
- AI composite score: {context.get('composite_score', 'N/A')} (0-1 scale)

Provide your fundamental stance on {ticker}. Reference the specific numbers above in your key points."""
