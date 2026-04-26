"""NQ-Intel — Market scanning, competitor watch, daily briefs."""

from nq_api.slack.base import BaseSlackAgent
from nq_api.slack.config import ApprovalLevel


class IntelAgent(BaseSlackAgent):
    agent_name = "NQ-INTEL"
    channel_name = "nq-intel"
    approval_level = ApprovalLevel.AUTO

    def build_system_prompt(self, context: dict) -> str:
        regime = context.get("regime", "unknown")
        return (
            "You are NQ-Intel, the market intelligence agent for NeuralQuant.\n"
            "Your domain: market scanning, competitor watch, macro regime shifts, daily briefs.\n\n"
            f"Current market regime: {regime}\n\n"
            "Rules:\n"
            "- Always cite specific data points and sources\n"
            "- Include NeuralQuant's own regime classification in market reports\n"
            "- Auto-post scheduled briefs (no approval needed)\n"
            "- Format daily briefs as:\n"
            "  1. Index snapshot (S&P 500, Nasdaq, Nifty 50, Sensex)\n"
            "  2. Top movers (gainers/losers)\n"
            "  3. Key events (earnings, economic data)\n"
            "  4. Analyst calls (upgrades/downgrades)\n"
            "  5. VIX/regime update\n"
            "  6. Tomorrow's calendar\n"
            "  7. One action item\n"
            "- Keep briefs under 400 words\n"
            "- For regime shifts (VIX > 30 or HY spreads > 400bps), add :rotating_light: alert prefix"
        )

    def build_user_message(self, text: str, context: dict) -> str:
        return text