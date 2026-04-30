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

## THRESHOLDS (use these to make calls)
- VIX: <15 = low vol / Risk-On, 15-25 = normal, >25 = elevated, >35 = crisis
- India VIX: <14 = low vol / Risk-On, 14-20 = normal, >20 = elevated, >25 = crisis
- HY spread: <300bps = tight/healthy, 300-500bps = moderate, >500bps = stressed
- 2s10s spread: >100bps = normal, 0-100bps = flat/concerning, inverted = recession signal
- ISM PMI: >55 = expansion, 50-55 = moderate, <50 = contraction
- Fed funds vs CPI: real rate >0 = restrictive, <0 = accommodative
- RBI repo rate: >6.5% = restrictive, 5.5-6.5% = neutral, <5.5% = accommodative
- INR/USD: <82 = strong rupee, 82-85 = moderate, >85 = weak rupee
- SPX vs 200-MA: >5% = strong uptrend, -5% to +5% = range, <-5% = downtrend
- Nifty vs 200-MA: >5% = strong uptrend, -5% to +5% = range, <-5% = downtrend

## REASONING PROTOCOL (mandatory)
1. CITE specific data points — "VIX at 14.2, well below the 20 stress threshold"
2. COMPARE to historical norms — "HY spreads at 280bps vs 5yr avg of 380bps"
3. CONCLUDE with a clear stance — "BULL because macro tailwinds (low VIX, dovish Fed) favor growth stocks" or "BEAR because rising VIX and inverted yield curve signal recession risk"
4. If data is missing, state WHICH data and what it would change

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

Be direct. Do not hedge every statement. Take a position. You must be equally willing to output BEAR as BULL — if macro data is hostile to this stock, say BEAR."""


class MacroAgent(BaseAnalystAgent):
    agent_name = "MACRO"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        market = context.get('market', 'US')
        regime = context.get('regime_label', 'N/A')

        if market == "IN":
            return f"""Analyse the macro environment for {ticker} (Indian market / NSE).

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Current India macro data (live as of today):
- India VIX: {context.get('india_vix', 'N/A')} (typically 10-25 range; >20 = elevated fear)
- Market regime: {regime}
- RBI repo rate: {context.get('rbi_repo_rate', 'N/A')}%
- INR/USD: {context.get('inr_usd', 'N/A')} (higher = weaker rupee)
- Nifty 50 vs 200-day MA: {context.get('nifty_vs_200ma', 'N/A')}% (positive = above 200MA)
- Nifty 50 1-month return: {context.get('nifty_return_1m', 'N/A')}%
- Sensex close: {context.get('sensex_close', 'N/A')}

## India-specific framework:
1. RBI rate cycle — repo rate impacts banking, real estate, infrastructure stocks
2. INR/USD — weak rupee benefits IT exporters, hurts oil importers
3. India VIX — similar to US VIX but typically 10-25 range
4. Nifty vs 200MA — broad market trend for Indian equities
5. FII/DII flows — foreign institutional investor sentiment (use regime as proxy)

## India thresholds:
- India VIX: <14 = low vol/Risk-On, 14-20 = normal, >20 = elevated, >25 = crisis
- RBI repo rate: >6.5% = restrictive, 5.5-6.5% = neutral, <5.5% = accommodative
- INR/USD: <82 = strong rupee, 82-85 = moderate, >85 = weak rupee
- Nifty vs 200MA: >5% = strong uptrend, -5% to +5% = range, <-5% = downtrend

Provide your macro stance on {ticker}. Reference the specific numbers above in your key points."""

        # US market (default)
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
