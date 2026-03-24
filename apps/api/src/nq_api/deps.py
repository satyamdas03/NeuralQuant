# apps/api/src/nq_api/deps.py
"""Shared FastAPI dependencies — singletons loaded once at startup."""
from functools import lru_cache
from nq_signals.engine import SignalEngine


@lru_cache(maxsize=1)
def get_signal_engine() -> SignalEngine:
    return SignalEngine()


@lru_cache(maxsize=1)
def get_orchestrator():
    """Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per request."""
    from nq_api.agents.orchestrator import ParaDebateOrchestrator
    return ParaDebateOrchestrator()
