"""Agent configuration: channel mappings, model assignments, approval levels."""

from __future__ import annotations

import os
from enum import Enum


class ApprovalLevel(str, Enum):
    AUTO = "auto"
    NOTIFY = "notify"
    REQUIRE_APPROVAL = "require"


# Model selection — follows existing pattern from agents/base.py
SONNET_MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6")
HAIKU_MODEL = os.environ.get("NQ_FAST_MODEL", "claude-haiku-4-5-20251001")

# Financial actions that ALWAYS require human approval, regardless of agent
FINANCIAL_APPROVAL_ACTIONS = {"billing_change", "refund", "pricing_change", "trade"}

AGENT_CONFIGS: dict[str, dict] = {
    "NQ-ENGINEER": {
        "channel": "nq-engineer",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.NOTIFY,
        "requires_approval_for": ["deploy", "merge"],
        "description": "Code, CI/CD, deploys, bug fixes",
    },
    "NQ-GUARDIAN": {
        "channel": "nq-guardian",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.NOTIFY,
        "requires_approval_for": [],
        "description": "Security, performance, regression monitoring",
    },
    "NQ-CONTENT": {
        "channel": "nq-content",
        "model": SONNET_MODEL,
        "approval_level": ApprovalLevel.REQUIRE_APPROVAL,
        "requires_approval_for": ["publish", "newsletter_send"],
        "description": "SEO, social posts, newsletters",
    },
    "NQ-ANALYST-OPS": {
        "channel": "nq-analyst-ops",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.AUTO,
        "requires_approval_for": [],
        "description": "Scoring pipeline, data quality checks",
    },
    "NQ-QUANT": {
        "channel": "nq-quant",
        "model": SONNET_MODEL,
        "approval_level": ApprovalLevel.AUTO,
        "requires_approval_for": ["model_deploy"],
        "description": "Research, new models, backtest analysis",
    },
    "NQ-BIZ": {
        "channel": "nq-biz",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.REQUIRE_APPROVAL,
        "requires_approval_for": ["billing_change", "refund", "pricing_change"],
        "description": "Billing, metrics, analytics, Stripe ops",
    },
    "NQ-INTEL": {
        "channel": "nq-intel",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.AUTO,
        "requires_approval_for": [],
        "description": "Market scanning, competitor watch, daily briefs",
    },
    "NQ-SUPPORT": {
        "channel": "nq-support",
        "model": HAIKU_MODEL,
        "approval_level": ApprovalLevel.AUTO,
        "requires_approval_for": [],
        "description": "User feedback, onboarding, FAQ responses",
    },
}

# Map from channel name → agent config key
CHANNEL_TO_AGENT: dict[str, str] = {
    cfg["channel"]: name for name, cfg in AGENT_CONFIGS.items()
}

# Slack tokens — from environment
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")

# Populated at runtime from Slack API after connection
CHANNEL_MAP: dict[str, str] = {}  # {"C09XXXX": "nq-engineer", ...}