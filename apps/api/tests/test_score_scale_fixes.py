"""Regression tests for 2026-08-08 score-scale / meta fixes (Session 104).

F1: /trade/signals Kelly sizing was dead — score_cache composite (qf*10, -160..+160)
    fed directly into compute_edge (expects 0-1) → every signal edge=1.0, bet uniform.
F4: Screener rows null price/P/E/sector — AIScore schema lacked display fields.
F3: /stocks/{t}/meta name="AAPL" instead of "Apple Inc." — merge never replaced
    ticker-placeholder names; FMP meta dict lacked change_pct/volume.
F5: /backtest/accuracy garbage hit_rate (-3271%) — avg composite *100 on qf*10 scale.
"""
from nq_api.score_builder import normalize_cache_composite, row_to_ai_score


class TestNormalizeCacheComposite:
    def test_0_1_passthrough(self):
        assert normalize_cache_composite(0.5) == 0.5
        assert normalize_cache_composite(0.0) == 0.0
        assert normalize_cache_composite(1.0) == 1.0

    def test_qf_times_10_scale(self):
        # stored 90 = qf 9 → (90+160)/320 = 0.78125
        assert abs(normalize_cache_composite(90.0) - 0.78125) < 1e-6
        # stored -32 = qf -3.2 → 0.4
        assert abs(normalize_cache_composite(-32.0) - 0.4) < 1e-6
        # stored 125 (IN max observed) → 0.890625
        assert abs(normalize_cache_composite(125.0) - 0.890625) < 1e-6

    def test_extremes_clamped(self):
        assert normalize_cache_composite(10000.0) == 1.0
        assert normalize_cache_composite(-10000.0) == 0.0

    def test_none(self):
        assert normalize_cache_composite(None) is None


class TestTradeSignalsEdgeDiscrimination:
    """F1: signals from score_cache rows must produce DISTINCT edges and Kelly bets."""

    def test_signals_not_uniform(self):
        from nq_api.routes.trade import _rows_to_signals

        strat = {
            "id": "momentum_breakout",
            "min_edge_score": 0.62,
            "kelly_fraction": 0.25,
            "max_bet": 4000.0,
            "risk_profile": "balanced",
        }
        rows = [
            {"ticker": "HIGH", "market": "US", "composite_score": 90.0, "current_price": 100.0},
            {"ticker": "MID",  "market": "US", "composite_score": 40.0, "current_price": 100.0},
            {"ticker": "LOW",  "market": "US", "composite_score": -40.0, "current_price": 100.0},
        ]
        signals = _rows_to_signals(rows, bankroll=10000.0, strategy=strat)

        assert len(signals) >= 2  # HIGH + MID above threshold, LOW excluded
        edges = {s["ticker"]: s["edge"] for s in signals}
        bets = {s["ticker"]: s["bet"] for s in signals}

        # HIGH (90 → norm 0.78125) has bigger edge than MID (40 → 0.625)
        assert edges["HIGH"] > edges["MID"]
        # Not the broken uniform-edge-1.0 behaviour
        assert all(e < 1.0 for e in edges.values())
        # Bets discriminate
        assert bets["HIGH"] != bets["MID"]
        # composite_score in response is normalized 0-1 (frontend multiplies by 100)
        assert all(0.0 <= s["composite_score"] <= 1.0 for s in signals)


class TestMergeMetaNamePlaceholder:
    """F3: name == ticker is a placeholder; overlay must be able to replace it."""

    def test_name_placeholder_replaced(self):
        from nq_api.routes.stocks import _merge_meta

        base = {"ticker": "AAPL", "name": "AAPL", "market_cap": None}
        overlay = {"name": "Apple Inc.", "market_cap": 3.5e12}
        merged = _merge_meta(base, overlay)
        assert merged["name"] == "Apple Inc."
        assert merged["market_cap"] == 3.5e12

    def test_real_name_not_clobbered(self):
        from nq_api.routes.stocks import _merge_meta

        base = {"ticker": "AAPL", "name": "Apple Inc."}
        overlay = {"name": "APL"}
        merged = _merge_meta(base, overlay)
        assert merged["name"] == "Apple Inc."

    def test_india_suffix_normalization(self):
        from nq_api.routes.stocks import _merge_meta

        base = {"ticker": "TCS.NS", "name": "TCS"}
        overlay = {"name": "Tata Consultancy Services"}
        merged = _merge_meta(base, overlay)
        assert merged["name"] == "Tata Consultancy Services"


class TestAIScoreDisplayFields:
    """F4: AIScore must carry display fields; row_to_ai_score populates from cache row."""

    def test_cache_row_fields_present(self):
        import pandas as pd

        row = pd.Series({
            "ticker": "NUE",
            "composite_score": 0.62,
            "regime_id": 1,
            "quality_percentile": 0.8,
            "momentum_percentile": 0.7,
            "short_interest_percentile": 0.6,
            "value_percentile": 0.5,
            "low_vol_percentile": 0.5,
            "growth_percentile": 0.55,
            "current_price": 272.0,
            "pe_ttm": 12.3,
            "market_cap": 62e9,
            "sector": "Basic Materials",
            "long_name": "Nucor Corporation",
        })
        score = row_to_ai_score(row, "US", score_1_10_override=8)
        assert score.current_price == 272.0
        assert score.pe_ttm == 12.3
        assert score.market_cap == 62e9
        assert score.sector == "Basic Materials"
        assert score.name == "Nucor Corporation"

    def test_missing_fields_none_not_crash(self):
        import pandas as pd

        row = pd.Series({"ticker": "XYZ", "composite_score": 0.5, "regime_id": 1})
        score = row_to_ai_score(row, "US")
        assert score.current_price is None
        assert score.sector is None
