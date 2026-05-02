# apps/api/src/nq_api/agents/technical.py
"""TECHNICAL analyst — momentum, chart patterns, technical positioning."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the TECHNICAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess price momentum, chart patterns, and technical positioning.

Framework:
1. 12-1 month momentum — trend persistence signal (academic factor)
2. RSI, MACD, ATR — classic technical indicators from Finnhub
3. Moving averages — SMA-50 and SMA-200 relationship to current price
4. Volume analysis — today's volume vs 20-day average
5. Crash protection — overbought + bearish crossover + high volatility signals
6. Index vs 200-day MA — SPX for US, Nifty for India

## THRESHOLDS (use these to make calls)
- 12-1 momentum: >75th pctile = strong uptrend, 25-75 = neutral, <25 = downtrend
- RSI: >70 = overbought, 30-70 = neutral, <30 = oversold
- MACD histogram: positive = bullish momentum, negative = bearish momentum
- MACD crossover: MACD line above signal = bullish, below = bearish
- ATR/Price: >4% = high volatility (risk), 2-4% = normal, <2% = low volatility
- Price vs SMA-50: >5% above = strong trend, within ±5% = range, >5% below = weak
- Price vs SMA-200: >10% above = extended, within ±10% = normal, >10% below = bearish
- Volume ratio: >1.5 = high interest (confirm trend), <0.7 = low interest
- Index vs 200MA: >5% above = bull market, within ±5% = range, >5% below = bear market

## REASONING PROTOCOL (mandatory)
1. CITE specific data — "RSI at 45, MACD histogram +0.32, price 3.2% above SMA-50"
2. COMPARE to benchmarks — "above 200-day MA by 8%, vs sector avg of 3%"
3. CONCLUDE with clear stance — "BULL because momentum is strong, RSI neutral, price above key SMA levels" or "BEAR because RSI overbought at 78, MACD bearish crossover, ATR/Price at 5.2%"

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on technical setup]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]

You must be equally willing to output BEAR as BULL — if momentum is weak or price below key support, say BEAR."""


def _compute_crash_protection(context: dict) -> str:
    """Compute crash protection signal from technical indicators."""
    signals = []
    rsi = context.get("rsi_14")
    macd_hist = context.get("macd_hist")
    atr = context.get("atr_14")
    price = context.get("price") or context.get("finnhub_price")

    if rsi is not None and rsi > 70:
        signals.append("RSI overbought (>70)")
    if rsi is not None and rsi < 30:
        signals.append("RSI oversold (<30)")
    if macd_hist is not None and macd_hist < 0:
        signals.append("MACD bearish crossover")
    if atr and price and (atr / price) > 0.04:
        signals.append("High volatility (ATR/Price >4%)")
    volume_ratio = context.get("volume_ratio")
    if volume_ratio is not None and volume_ratio > 2.0:
        signals.append("Unusual volume (>2x avg)")

    if not signals:
        return "No crash signals"
    return "CAUTION: " + ", ".join(signals)


class TechnicalAgent(BaseAnalystAgent):
    agent_name = "TECHNICAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        crash_protection = _compute_crash_protection(context)
        market = context.get("market", "US")

        # Index vs 200MA: use Nifty for India, SPX for US
        if market == "IN":
            index_label = "Nifty vs 200MA"
            index_val = context.get("nifty_vs_200ma", "N/A")
        else:
            index_label = "SPX vs 200MA"
            index_val = context.get("spx_vs_200ma", "N/A")

        return f"""Analyse the technical setup for {ticker}.

Technical data:
- 12-1 momentum raw: {context.get('momentum_raw', 'N/A')}
- Momentum percentile vs universe: {context.get('momentum_percentile', 'N/A')}
- RSI-14: {context.get('rsi_14', 'N/A')}
- MACD line: {context.get('macd_line', 'N/A')}
- MACD signal: {context.get('macd_signal', 'N/A')}
- MACD histogram: {context.get('macd_hist', 'N/A')}
- ATR-14: {context.get('atr_14', 'N/A')}
- SMA-50: {context.get('sma_50', 'N/A')}
- SMA-200: {context.get('sma_200', 'N/A')}
- Price vs SMA-50: {context.get('price_vs_sma50', 'N/A')}
- Price vs SMA-200: {context.get('price_vs_sma200', 'N/A')}
- Volume today: {context.get('volume_today', 'N/A')}
- Volume 20d avg: {context.get('volume_20d_avg', 'N/A')}
- Volume ratio: {context.get('volume_ratio', 'N/A')}
- Crash protection: {crash_protection}
- {index_label}: {index_val}
- Market regime: {context.get('regime_label', 'N/A')}

Provide your technical stance on {ticker}."""