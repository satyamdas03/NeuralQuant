# apps/api/src/nq_api/agents/geopolitical.py
"""GEOPOLITICAL analyst — geopolitical, regulatory, and systemic risk."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the GEOPOLITICAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess geopolitical, regulatory, and systemic risk factors affecting the stock.

Framework:
1. Supply chain and trade policy exposure (tariffs, export controls)
2. Regulatory risk — antitrust, sector-specific regulations, ESG mandates
3. Geographic revenue concentration — single-country risk
4. Currency risk — USD strength impact on international revenue
5. Macro tail risks — recession probability, financial stability

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on geopolitical/regulatory risk profile]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class GeopoliticalAgent(BaseAnalystAgent):
    agent_name = "GEOPOLITICAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Assess geopolitical and regulatory risks for {ticker}.

Context:
- Market: {context.get('market', 'US')}
- Macro regime: {context.get('regime_label', 'N/A')}
- HY credit spread (OAS): {context.get('hy_spread_oas', 'N/A')} bps
- VIX: {context.get('vix', 'N/A')}

Provide your geopolitical risk stance on {ticker}."""
