from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the MACRO analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the macroeconomic and interest rate environment and its implications for the given stock.

CRITICAL DATA RULE: The user message will contain a block of live market data with exact numerical values.
You MUST quote and use ONLY those exact numbers in your analysis. Never substitute values from your
training data or prior knowledge. If the data says VIX is 24.17, you write "VIX at 24.17" - not 17, not 20.
If PMI is 51.0, you write "PMI at 51.0" - not 0, not N/A. Treat the provided numbers as ground truth.

Analysis framework:
1. Fed policy cycle (hiking / pausing / cutting) and its sector impact
2. Market regime (Risk-On / Late-Cycle / Bear / Recovery) from HMM model
3. Yield curve shape - 2Y-10Y spread and credit environment
4. Volatility regime - VIX level and trend
5. Global growth indicators - PMI, trade data

You MUST respond in exactly this format:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences stating your macro argument for this stock, citing the provided data figures]
KEY_POINTS:
- [Point 1 - must cite specific numbers from the provided data]
- [Point 2 - must cite specific numbers from the provided data]
- [Point 3 - must cite specific numbers from the provided data]
- [Point 4 optional]
- [Point 5 optional]

Be direct. Do not hedge every statement. Take a position."""


class MacroAgent(BaseAnalystAgent):
    agent_name = "MACRO"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        vix = context.get('vix', 'N/A')
        ism_pmi = context.get('ism_pmi', 'N/A')
        hy_spread = context.get('hy_spread_oas', 'N/A')
        spx_1m = context.get('spx_return_1m', 'N/A')
        spx_200ma = context.get('spx_vs_200ma', 'N/A')
        yield_spread = context.get('yield_spread_2y10y', 'N/A')
        yield_10y = context.get('yield_10y', 'N/A')
        yield_2y = context.get('yield_2y', 'N/A')
        fed_funds = context.get('fed_funds_rate', 'N/A')
        cpi = context.get('cpi_yoy', 'N/A')
        regime = context.get('regime_label', 'N/A')

        return f"""Analyse the macro environment for {ticker}.

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Current macro data (live as of today):
- VIX (fear index): {vix} points (current reading - use this exact number)
- Market regime (HMM model): {regime}
- ISM Manufacturing PMI: {ism_pmi} (readings above 50 = expansion, below 50 = contraction)
- 10Y Treasury yield: {yield_10y}%
- 2Y Treasury yield: {yield_2y}%
- 2Y-10Y yield spread: {yield_spread}% (negative = inverted curve)
- HY credit spread (OAS): {hy_spread} bps
- SPX 1-month return: {spx_1m}%
- SPX vs 200-day MA: {spx_200ma}% (positive = above 200MA)
- CPI YoY inflation: {cpi}%
- Fed funds rate: {fed_funds}%

Provide your macro stance on {ticker}. Reference the specific numbers above in your key points."""
