"""Regression wall for the most expensive bug class: US code paths running for IN
(bugs 45, 84, 117, 124, 126)."""
import inspect
import pathlib

from nq_data.price.yf_guard import bare_ticker, normalize_ticker

ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_cache_keys_always_bare():
    assert bare_ticker(normalize_ticker("TCS", "IN")) == "TCS"
    assert bare_ticker(normalize_ticker("AAPL", "US")) == "AAPL"


def test_in_regime_uses_in_macro():
    """bug 117: live-regime path must branch to fetch_real_macro_in for IN."""
    from nq_api import data_builder
    src = inspect.getsource(data_builder)
    assert "fetch_real_macro_in" in src, "IN macro branch missing from data_builder"


def test_canonical_regime_feature_name():
    """bug 118: macro attribute is nifty_return_1m; HMM feature is nifty_1m_return.
    The mapping must exist in the signals engine — both names present."""
    from nq_api.db_columns import NIFTY_RETURN_1M
    assert NIFTY_RETURN_1M == "nifty_return_1m"
    engine_src = (ROOT / "packages" / "signals" / "src" / "nq_signals" /
                  "engine.py").read_text(encoding="utf-8")
    assert "nifty_return_1m" in engine_src and "nifty_1m_return" in engine_src, \
        "macro->HMM feature-name mapping removed (bug 118 regression)"


def test_benchmarks_per_market():
    """IN benchmark = ^NSEI ; US = ^GSPC — both must exist in the API layer."""
    blob = "\n".join(
        p.read_text(errors="ignore", encoding="utf-8")
        for p in (ROOT / "apps" / "api" / "src" / "nq_api").rglob("*.py")
    )
    assert "^NSEI" in blob, "India benchmark ^NSEI missing"
    assert "^GSPC" in blob, "US benchmark ^GSPC missing"
