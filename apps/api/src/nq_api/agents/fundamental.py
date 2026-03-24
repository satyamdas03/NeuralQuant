# apps/api/src/nq_api/agents/fundamental.py
"""FUNDAMENTAL analyst — financial quality, valuation, earnings trajectory."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the FUNDAMENTAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the company's financial quality, valuation, and earnings trajectory.

Framework:
1. Profitability quality — Piotroski F-Score, gross margins, accruals (earnings quality)
2. Valuation — P/E, P/FCF, EV/EBITDA relative to sector and history
3. Earnings trajectory — estimate revisions, surprise history, guidance
4. Balance sheet strength — debt levels, interest coverage, cash generation
5. Capital allocation — buybacks, dividends, capex efficiency (ROIC)

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on fundamental investment merit]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class FundamentalAgent(BaseAnalystAgent):
    agent_name = "FUNDAMENTAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse the fundamental investment merit of {ticker}.

Financial data:
- Piotroski F-Score: {context.get('piotroski', 'N/A')} / 9
- Quality composite percentile: {context.get('quality_percentile', 'N/A')}
- Gross profit margin: {context.get('gross_profit_margin', 'N/A')}
- Accruals ratio: {context.get('accruals_ratio', 'N/A')} (lower is better — indicates cash earnings)
- AI composite score: {context.get('composite_score', 'N/A')}

Provide your fundamental stance on {ticker}."""
