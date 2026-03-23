from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the MACRO analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the macroeconomic and interest rate environment and its implications for the given stock.

Analysis framework:
1. Fed policy cycle (hiking / pausing / cutting) and its sector impact
2. Market regime (Risk-On / Late-Cycle / Bear / Recovery) from HMM model
3. Yield curve shape — 2Y-10Y spread and credit environment
4. Volatility regime — VIX level and trend
5. Global growth indicators — PMI, trade data

You MUST respond in exactly this format:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences stating your macro argument for this stock]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]
- [Point 4 optional]
- [Point 5 optional]

Be direct. Do not hedge every statement. Take a position."""


class MacroAgent(BaseAnalystAgent):
    agent_name = "MACRO"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse the macro environment for {ticker}.

Current macro data:
- VIX: {context.get('vix', 'N/A')}
- Regime: {context.get('regime_label', 'N/A')}
- ISM PMI: {context.get('ism_pmi', 'N/A')}
- 10Y-2Y Yield Spread: {context.get('yield_spread_2y10y', 'N/A')}
- HY Credit Spread (OAS): {context.get('hy_spread_oas', 'N/A')}
- SPX 1-month return: {context.get('spx_return_1m', 'N/A')}
- SPX vs 200MA: {context.get('spx_vs_200ma', 'N/A')}

Provide your macro stance on {ticker}."""
