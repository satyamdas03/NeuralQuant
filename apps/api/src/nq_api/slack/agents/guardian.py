"""NQ-Guardian — Security, performance, regression monitoring."""

from nq_api.slack.base import BaseSlackAgent
from nq_api.slack.config import ApprovalLevel


class GuardianAgent(BaseSlackAgent):
    agent_name = "NQ-GUARDIAN"
    channel_name = "nq-guardian"
    approval_level = ApprovalLevel.NOTIFY

    def build_system_prompt(self, context: dict) -> str:
        return (
            "You are NQ-Guardian, the security and reliability agent for NeuralQuant.\n"
            "Your domain: security audits, performance monitoring, regression detection, uptime checks.\n\n"
            "Rules:\n"
            "- Auto-report findings (no approval needed for reports)\n"
            "- Escalate critical security issues with :rotating_light: prefix\n"
            "- Never modify production data without approval\n"
            "- When reporting metrics, include specific numbers and trends\n"
            "- For performance issues, include p95 latency, error rates, and Supabase query times\n"
            "- Keep responses under 300 words for monitoring reports"
        )

    def build_user_message(self, text: str, context: dict) -> str:
        return text