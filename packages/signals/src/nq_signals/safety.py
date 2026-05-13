"""Safety gate — blocks orders until explicit enablement + risk checks pass.

Follows Polymarket Pipeline pattern: dry-run default, hard caps, circuit breaker.
Pure functions with no I/O. Risk math delegated to nq_signals.risk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class SafetyGate:
    dry_run: bool = True
    trade_enabled: bool = False
    daily_loss_limit: float = 100.0
    max_bet: float = 5000.0
    max_positions: int = 10


@dataclass
class SafetyCheck:
    passed: bool
    reason: str = ""
    dry_run_note: str | None = None


def load_safety_gate() -> SafetyGate:
    """Read safety configuration from environment variables.

    All defaults are SAFE: trading disabled, dry-run enabled.
    """
    return SafetyGate(
        trade_enabled=os.environ.get("TRADE_ENABLED", "false").lower() == "true",
        dry_run=os.environ.get("DRY_RUN", "true").lower() == "true",
        daily_loss_limit=float(os.environ.get("DAILY_LOSS_LIMIT", "100.0")),
        max_bet=float(os.environ.get("MAX_BET_DEFAULT", "5000.0")),
        max_positions=int(os.environ.get("MAX_POSITIONS_DEFAULT", "10")),
    )


def check_order(
    bet: float,
    gate: SafetyGate,
    daily_pnl: float,
    current_positions: int,
) -> SafetyCheck:
    """Run every safety gate on a proposed order. Returns first failure reason.

    Gates in order:
    1. TRADE_ENABLED
    2. Daily loss limit (circuit breaker)
    3. Max positions
    4. Max bet
    5. Dry-run (always last — lets other checks fail first)
    """
    if not gate.trade_enabled and not gate.dry_run:
        return SafetyCheck(False, "Trading disabled. Set TRADE_ENABLED=true in Render env vars.")

    if daily_pnl <= -gate.daily_loss_limit:
        return SafetyCheck(
            False,
            f"Daily loss limit ${gate.daily_loss_limit:.0f} reached (PnL: ${daily_pnl:.2f}). "
            "Resets midnight UTC.",
        )

    if current_positions >= gate.max_positions:
        return SafetyCheck(
            False,
            f"Max positions reached ({current_positions}/{gate.max_positions}). "
            "Close existing positions first.",
        )

    if bet > gate.max_bet:
        return SafetyCheck(
            False,
            f"Bet ${bet:.2f} exceeds max ${gate.max_bet:.2f}.",
        )

    if gate.dry_run:
        return SafetyCheck(
            True,
            "Dry run",
            f"[DRY RUN] Would have placed order for ${bet:.2f}. "
            "Set DRY_RUN=false to execute live.",
        )

    return SafetyCheck(True, "Order approved for live execution.")
