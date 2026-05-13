"""Risk management module for NeuralQuant trading signals.

Adopts patterns from polymarket-pipeline:
- Edge detection: composite_score (0-1) → edge (0-1), threshold-gated
- Quarter-Kelly position sizing with configurable bankroll and caps
- Daily drawdown tracking with circuit breaker
- Portfolio concentration risk detection

All functions are pure — no I/O, no database, no network calls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class EdgeResult:
    """Output of edge detection on a single stock."""
    ticker: str
    composite_score: float       # 0-1
    edge: float                  # 0-1, >0 = actionable
    direction: str               # "bullish" | "bearish" | "neutral"
    actionable: bool             # edge >= threshold


@dataclass
class PositionSize:
    """Kelly-derived position size for a single signal."""
    ticker: str
    edge: float
    bankroll: float
    kelly_fraction: float        # e.g. 0.25 for quarter-Kelly
    bet: float                   # recommended $ amount
    capped: bool                 # True if limited by max_bet


@dataclass
class DrawdownStatus:
    """Daily drawdown state for circuit breaker."""
    total_pnl_today: float
    daily_loss_limit: float
    remaining_budget: float
    limit_breached: bool
    warning_level: str           # "OK" | "WARNING" | "BREACHED"


@dataclass
class ConcentrationResult:
    """Portfolio concentration analysis."""
    total_value: float
    positions: dict[str, float]  # ticker → dollar value
    max_single_pct: float        # configured max (e.g. 0.20)
    overconcentrated: list[str]  # tickers exceeding max
    concentration_score: float   # 0-1, higher = more concentrated
    warning_level: str           # "OK" | "WARNING" | "HIGH"


# ── Edge detection ──────────────────────────────────────────────

def compute_edge(
    composite_score: float,
    threshold: float = 0.70,
) -> float:
    """Normalize composite_score (0-1) to edge (0-1).

    Only scores above threshold produce positive edge.
    Edge = max(0, (score - threshold) / (1.0 - threshold))

    >>> compute_edge(0.85, 0.70)
    0.5
    >>> compute_edge(0.60, 0.70)
    0.0
    """
    if composite_score >= 1.0:
        return 1.0
    if composite_score <= threshold:
        return 0.0
    return (composite_score - threshold) / (1.0 - threshold)


def compute_edge_multi(
    scores: list[tuple[str, float]],
    threshold: float = 0.70,
) -> list[EdgeResult]:
    """Compute edge for multiple stocks. Returns only those above threshold.

    Direction is always "bullish" for high scores — bearish signals
    would require a separate short-screen (future Phase 3).
    """
    results: list[EdgeResult] = []
    for ticker, score in scores:
        edge = compute_edge(score, threshold)
        results.append(EdgeResult(
            ticker=ticker,
            composite_score=score,
            edge=edge,
            direction="bullish" if edge > 0 else "neutral",
            actionable=edge > 0,
        ))
    return sorted(results, key=lambda r: r.edge, reverse=True)


# ── Kelly position sizing ──────────────────────────────────────

def size_position_kelly(
    edge: float,
    bankroll: float,
    win_probability: float = 0.55,
    kelly_fraction: float = 0.25,
    max_bet: float = 5000.0,
    min_bet: float = 1.0,
) -> PositionSize:
    """Quarter-Kelly position sizing.

    Full Kelly: f* = edge — (1-edge)/odds_ratio  (approximated)
    Quarter-Kelly: bet = bankroll * edge * kelly_fraction

    Bet is floored at min_bet and capped at max_bet.
    Returns $0.00 if edge is 0.
    """
    if edge <= 0 or bankroll <= 0:
        return PositionSize(
            ticker="",
            edge=edge,
            bankroll=bankroll,
            kelly_fraction=kelly_fraction,
            bet=0.0,
            capped=False,
        )

    raw = bankroll * edge * kelly_fraction
    bet = round(raw, 2)

    capped = False
    if bet > max_bet:
        bet = max_bet
        capped = True
    elif bet < min_bet:
        bet = 0.0

    return PositionSize(
        ticker="",
        edge=edge,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        bet=bet,
        capped=capped,
    )


def size_positions_batch(
    edges: list[EdgeResult],
    bankroll: float,
    kelly_fraction: float = 0.25,
    max_bet: float = 5000.0,
    max_positions: int = 10,
) -> list[PositionSize]:
    """Size positions for a batch of edge signals. Limits to top N."""
    results: list[PositionSize] = []
    remaining_bankroll = bankroll

    for er in edges[:max_positions]:
        if not er.actionable:
            continue
        ps = size_position_kelly(
            edge=er.edge,
            bankroll=remaining_bankroll,
            kelly_fraction=kelly_fraction,
            max_bet=max_bet,
        )
        ps.ticker = er.ticker
        if ps.bet > 0:
            results.append(ps)
            remaining_bankroll -= ps.bet

    return results


# ── Drawdown / circuit breaker ─────────────────────────────────

def compute_daily_drawdown(
    pnl_today: list[float],
    daily_loss_limit: float = 100.0,
    warning_pct: float = 0.70,
) -> DrawdownStatus:
    """Check today's PnL against daily loss limit.

    pnl_today: list of realized PnL values (negative = loss) for the current day.
    Returns limit_breached=True when total losses exceed the daily cap.
    """
    total = sum(pnl_today)
    remaining = daily_loss_limit + total  # total is negative when losing
    limit_pct_used = abs(total) / daily_loss_limit if total < 0 else 0.0

    if total <= -daily_loss_limit:
        return DrawdownStatus(
            total_pnl_today=total,
            daily_loss_limit=daily_loss_limit,
            remaining_budget=0.0,
            limit_breached=True,
            warning_level="BREACHED",
        )
    elif limit_pct_used >= warning_pct:
        return DrawdownStatus(
            total_pnl_today=total,
            daily_loss_limit=daily_loss_limit,
            remaining_budget=remaining,
            limit_breached=False,
            warning_level="WARNING",
        )
    else:
        return DrawdownStatus(
            total_pnl_today=total,
            daily_loss_limit=daily_loss_limit,
            remaining_budget=remaining,
            limit_breached=False,
            warning_level="OK",
        )


# ── Concentration risk ─────────────────────────────────────────

def compute_concentration(
    positions: dict[str, float],
    max_single_pct: float = 0.20,
) -> ConcentrationResult:
    """Detect over-concentration in portfolio.

    Uses Herfindahl-Hirschman Index (HHI) for concentration score.
    HHI = sum((value_i / total)^2), normalized to 0-1.
    """
    total = sum(positions.values())
    if total <= 0:
        return ConcentrationResult(
            total_value=0.0,
            positions=positions,
            max_single_pct=max_single_pct,
            overconcentrated=[],
            concentration_score=0.0,
            warning_level="OK",
        )

    over: list[str] = []
    hhi = 0.0
    for ticker, value in positions.items():
        pct = value / total
        if pct > max_single_pct:
            over.append(ticker)
        hhi += pct * pct

    n = len(positions)
    if n <= 1:
        concentration_score = 0.0
    else:
        # Normalize HHI: (HHI - 1/n) / (1 - 1/n) → 0-1
        normalized = (hhi - 1.0 / n) / (1.0 - 1.0 / n) if n > 1 else 0.0
        concentration_score = max(0.0, min(1.0, normalized))

    if over:
        warning = "HIGH"
    elif concentration_score > 0.5:
        warning = "WARNING"
    else:
        warning = "OK"

    return ConcentrationResult(
        total_value=total,
        positions=positions,
        max_single_pct=max_single_pct,
        overconcentrated=over,
        concentration_score=round(concentration_score, 4),
        warning_level=warning,
    )


# ── Risk profile → Kelly fraction mapping ──────────────────────

RISK_PROFILE_FRACTIONS: dict[str, float] = {
    "conservative": 0.15,
    "balanced": 0.25,
    "aggressive": 0.40,
}


def kelly_fraction_from_profile(risk_profile: str) -> float:
    """Map user risk profile to Kelly fraction."""
    return RISK_PROFILE_FRACTIONS.get(risk_profile.lower(), 0.25)
