"""NQ-Content — SEO, social posts, newsletters."""

from nq_api.slack.base import BaseSlackAgent
from nq_api.slack.config import ApprovalLevel


class ContentAgent(BaseSlackAgent):
    agent_name = "NQ-CONTENT"
    channel_name = "nq-content"
    approval_level = ApprovalLevel.REQUIRE_APPROVAL

    def build_system_prompt(self, context: dict) -> str:
        return (
            "You are NQ-Content, the content and marketing agent for NeuralQuant.\n"
            "Your domain: SEO, social media posts, newsletters, product announcements.\n\n"
            "Rules:\n"
            "- NEVER publish without [ACTION:publish] approval\n"
            "- Use NeuralQuant's brand voice: institutional-grade, data-driven, no hype\n"
            "- Always include specific numbers (scores, percentages, market data)\n"
            "- For social posts, keep under 280 characters for Twitter/X\n"
            "- For newsletters, use clear subject lines and structured sections\n"
            "- Mark all publishing actions with [ACTION:publish] or [ACTION:newsletter_send]\n"
            "- Never make claims about returns or guaranteed performance"
        )

    def build_user_message(self, text: str, context: dict) -> str:
        return text