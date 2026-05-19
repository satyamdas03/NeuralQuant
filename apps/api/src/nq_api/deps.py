# apps/api/src/nq_api/deps.py
"""Shared FastAPI dependencies — singletons loaded once at startup.

Heavy imports (sklearn, hmmlearn) are deferred to avoid loading ~100MB
at module level, which causes OOM on Render's 512MB instances.
"""
import os
import pickle
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_HMM_MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "signals" / "src" / "nq_signals" / "regime" / "hmm_regime.pkl"
_HMM_INDIA_MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "signals" / "src" / "nq_signals" / "regime" / "hmm_regime_india.pkl"


def _load_hmm_model():
    """Try to load fitted US HMM model. Returns None if unavailable."""
    # Defer heavy imports until actually needed
    from nq_signals.regime.hmm_detector import RegimeDetector

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


def _load_hmm_model_india():
    """Try to load fitted India HMM model. Returns None if unavailable."""
    from nq_signals.regime.hmm_detector import IndiaRegimeWrapper

    alt_path = os.environ.get("HMM_INDIA_MODEL_PATH", "")
    paths = [alt_path, str(_HMM_INDIA_MODEL_PATH)] if alt_path else [_HMM_INDIA_MODEL_PATH]
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    model_dict = pickle.load(f)
                wrapper = IndiaRegimeWrapper(model_dict)
                if wrapper._fitted:
                    logger.info(f"India HMM regime detector loaded from {p}")
                    return wrapper
            except Exception:
                logger.warning(f"Failed to load India HMM model from {p}", exc_info=True)
    logger.warning("No fitted India HMM model found — using VIX heuristic fallback")
    return None


@lru_cache(maxsize=1)
def get_signal_engine():
    from nq_signals.engine import SignalEngine
    regime_detector = _load_hmm_model()
    regime_detector_in = _load_hmm_model_india()
    return SignalEngine(regime_detector=regime_detector, regime_detector_in=regime_detector_in)


@lru_cache(maxsize=1)
def get_orchestrator():
    """Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per request."""
    from nq_api.agents.orchestrator import ParaDebateOrchestrator
    return ParaDebateOrchestrator()