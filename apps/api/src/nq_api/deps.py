# apps/api/src/nq_api/deps.py
"""Shared FastAPI dependencies — singletons loaded once at startup."""
import os
import pickle
import logging
from functools import lru_cache
from pathlib import Path

from nq_signals.engine import SignalEngine
from nq_signals.regime.hmm_detector import RegimeDetector

logger = logging.getLogger(__name__)

_HMM_MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "signals" / "src" / "nq_signals" / "regime" / "hmm_regime.pkl"


def _load_hmm_model() -> RegimeDetector | None:
    """Try to load fitted HMM model. Returns None if unavailable."""
    alt_path = os.environ.get("HMM_MODEL_PATH", "")
    paths = [alt_path, str(_HMM_MODEL_PATH)] if alt_path else [_HMM_MODEL_PATH]
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    detector = pickle.load(f)
                if detector._fitted:
                    logger.info(f"HMM regime detector loaded from {p}")
                    return detector
            except Exception:
                logger.warning(f"Failed to load HMM model from {p}", exc_info=True)
    logger.warning("No fitted HMM model found — regime detection will use heuristic fallback")
    return None


@lru_cache(maxsize=1)
def get_signal_engine() -> SignalEngine:
    regime_detector = _load_hmm_model()
    return SignalEngine(regime_detector=regime_detector)


@lru_cache(maxsize=1)
def get_orchestrator():
    """Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per request."""
    from nq_api.agents.orchestrator import ParaDebateOrchestrator
    return ParaDebateOrchestrator()
