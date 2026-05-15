# apps/api/src/nq_api/agents/adversarial.py
"""ADVERSARIAL analyst — devil's advocate, prioritizes bear/risk signals. May output BULL when data overwhelmingly supports it."""
from nq_api.agents.base import BaseAnalystAgent

_RAW_SYSTEM = """You are the ADVERSARIAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your PRIMARY mandate: identify risks and stress-test bullish assumptions. You are the devil's advocate — your default stance is skeptical.

However, you MUST be honest. If the data overwhelmingly supports a bullish case AND you cannot find any credible bear signals crossing your thresholds, you MUST output BULL rather than fabricating false bear arguments. A fabricated bear case is worse than no bear case — it misleads investors.

DATA INTEGRITY RULE: All numerical values below are marked [VERIFIED] — they come from live financial data APIs (FMP, yfinance), NOT from LLM training data. You MUST use ONLY these exact numbers. Never substitute values from your training data.

Challenge framework — use raw data thresholds to identify bear signals:
1. What would have to go wrong for the bull thesis to fail?
2. Are there hidden risks in the balance sheet or earnings quality?
3. Is the valuation pricing in perfection?
4. What does low short interest imply about complacency risk?
5. What is the asymmetric downside scenario?

## THRESHOLDS (use these with the [VERIFIED] data below)
- P/E >25 and revenue growth <15% = valuation pricing in perfection (strong bear signal)
- Debt/Equity >1.5 = balance sheet risk
- Momentum <25th pctile = technical weakness
- Quality percentile <40 = below-average fundamentals
- Composite score <0.5 = model disagreement with bull case
- Insider cluster <0.3 = insiders selling
- Short interest >80th pctile = smart money bearish
- RSI >70 = overbought (potential reversal)
- MACD histogram negative = bearish momentum
- Piotroski <4 = weak financial health
- P/B >5 = growth priced in, no margin of safety

## REASONING PROTOCOL (mandatory)
1. CITE specific [VERIFIED] data — "P/E at 36x [VERIFIED] with only 8% revenue growth = perfection priced in"
2. COMPARE to risk thresholds — "debt/equity at 1.8 exceeds the 1.5 danger threshold"
3. CHECK fundamentals — "piotroski only 3/9 [VERIFIED] = weak financial health"
4. FIND contradictions — "composite 0.62 [VERIFIED] but momentum only 15th pctile = model may be over-weighting stale factors"
5. CONCLUDE with clear BEAR argument — "BEAR because valuation assumes growth that fundamentals don't support"

You MUST output BEAR, NEUTRAL, or BULL based on the data. Default to BEAR when bear signals cross thresholds. Output BULL only when data is overwhelmingly positive AND no bear signals cross any threshold — be honest, don't fabricate.

Response format — strictly:
STANCE: [BEAR|NEUTRAL|BULL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences — your honest assessment citing the provided data figures]
KEY_POINTS:
- [Risk 1 - must cite specific [VERIFIED] numbers from the provided data]
- [Risk 2 - must cite specific [VERIFIED] numbers from the provided data]
- [Risk 3 - must cite specific [VERIFIED] numbers from the provided data]"""


class AdversarialAgent(BaseAnalystAgent):
    agent_name = "ADVERSARIAL"
    system_prompt = _RAW_SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        """Build message with specialist outputs (sequential mode)."""
        bull_thesis = context.get("bull_thesis", "No bull thesis provided.")
        bear_thesis = context.get("bear_thesis", "No bear thesis provided.")
        specialist_outputs = context.get("specialist_outputs", {})

        specialist_lines = []
        for name, data in specialist_outputs.items():
            kp = data.get('key_points', [])
            kp_text = f" | Key: {', '.join(kp[:3])}" if kp else ""
            specialist_lines.append(
                f"  [{name}] {data.get('stance', '?')} ({data.get('conviction', '?')}): "
                f"{data.get('thesis', 'No thesis')}{kp_text}"
            )
        specialist_section = "\n".join(specialist_lines) if specialist_lines else "No specialist data available."

        return f"""Find the strongest possible bear case for {ticker}.

IMPORTANT: Use ONLY the [VERIFIED] figures below. Do not substitute values from memory or training data.

INDIVIDUAL SPECIALIST OUTPUTS (challenge these individually):
{specialist_section}

BULL THESIS (aggregated from bullish agents):
{bull_thesis}

BEAR THESIS (aggregated from bearish agents):
{bear_thesis}

{self._build_data_section(context)}

Stress-test this thesis and provide the best bear argument. Reference the specific [VERIFIED] numbers above.
Look for contradictions between agents and challenge overconfident stances with weak data."""

    def _build_user_message_raw(self, ticker: str, context: dict) -> str:
        """Build message from raw context only (parallel mode — no specialist outputs)."""
        return f"""Find the strongest possible bear case for {ticker}.

IMPORTANT: Use ONLY the [VERIFIED] figures below. Every value marked [VERIFIED] comes from live financial APIs. Do not substitute values from your training data.

{self._build_data_section(context)}

Use the THRESHOLDS from your system prompt to identify bear signals. For each data point, check if it crosses a danger threshold.
Build a structured bear argument citing specific [VERIFIED] numbers. If NO thresholds are crossed and data is overwhelmingly positive, output BULL honestly. A fake bear case is worse than no bear case."""

    def _build_data_section(self, context: dict) -> str:
        """Shared data section with [VERIFIED] markers on all live data."""
        def _v(key, fmt=None, suffix=""):
            val = context.get(key)
            if val is None:
                return "N/A"
            if fmt:
                return f"{fmt(val)}{suffix}"
            return f"{val}{suffix}"

        return f"""Key data [VERIFIED — live as of today]:
- AI composite score: {_v('composite_score')} [VERIFIED]
- Quality percentile: {_v('quality_percentile')} [VERIFIED]
- Momentum percentile: {_v('momentum_percentile')} [VERIFIED]
- Value percentile: {_v('value_percentile')} [VERIFIED]
- Low-vol percentile: {_v('low_vol_percentile')} [VERIFIED]
- P/E ratio: {_v('pe_ttm')}x [VERIFIED]
- P/B ratio: {_v('pb_ratio')}x [VERIFIED]
- Beta: {_v('beta')} [VERIFIED]
- Piotroski score: {_v('piotroski')}/9 [VERIFIED]
- ROE: {_v('roe')} [VERIFIED]
- Gross margin: {_v('gross_profit_margin')} [VERIFIED]
- Accruals ratio: {_v('accruals_ratio')} [VERIFIED]
- Debt/Equity: {_v('debt_equity')} [VERIFIED]
- Revenue growth: {_v('revenue_growth')}% [VERIFIED]
- Short interest: {_v('short_interest_pct')}% of float [VERIFIED]
- Insider cluster score: {_v('insider_cluster_score')} [VERIFIED]
- 52-week high: {_v('week52_high')} [VERIFIED]
- 52-week low: {_v('week52_low')} [VERIFIED]
- Analyst target: {_v('analyst_target_mean')} [VERIFIED]
- Market cap: {_v('market_cap')} [VERIFIED]
- RSI-14: {_v('rsi_14')} [VERIFIED]
- MACD histogram: {_v('macd_hist')} [VERIFIED]
- Realized volatility: {_v('realized_vol_1y')} [VERIFIED]
- Regime: {context.get('regime_label', 'N/A')} [VERIFIED]

Data quality: {', '.join(context.get('_data_quality_flags', ['all fields available']))}"""

    def run_raw(self, ticker: str, context: dict) -> dict:
        """Run adversarial with raw context only (no specialist outputs)."""
        return self.run(ticker, context, _msg_override=self._build_user_message_raw(ticker, context))
