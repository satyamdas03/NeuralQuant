# apps/api/src/nq_api/deps.py
"""Shared FastAPI dependencies — singletons loaded once at startup."""
from functools import lru_cache
from nq_signals.engine import SignalEngine

@lru_cache(maxsize=1)
def get_signal_engine() -> SignalEngine:
    return SignalEngine()
