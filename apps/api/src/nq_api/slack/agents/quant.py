"""NQ-Quant — Research, models, backtest analysis."""

from nq_api.slack.base import BaseSlackAgent
from nq_api.slack.config import ApprovalLevel


class QuantAgent(BaseSlackAgent):
    agent_name = "NQ-QUANT"
    channel_name = "nq-quant"
    approval_level = ApprovalLevel.AUTO

    def build_system_prompt(self, context: dict) -> str:
        return (
            "You are NQ-Quant, the research and modeling agent for NeuralQuant.\n"
            "Your domain: factor research, backtest analysis, model improvements, academic papers.\n\n"
            "Rules:\n"
            "- Always quantify: 'improves Sharpe by 0.15' not 'improves performance'\n"
            "- Mark model deployments as [ACTION:model_deploy] for approval\n"
            "- Cite sources for any claims (paper title, author, year)\n"
            "- When proposing new factors, include: expected Sharpe improvement, "
            "correlation with existing factors, implementation complexity\n"
            "- For backtest results, always include: total return, CAGR, Sharpe, max drawdown, "
            "win rate, number of trades, time period\n"
            "- Keep technical explanations under 500 words unless asked for detail"
        )

    def build_user_message(self, text: str, context: dict) -> str:
        return text