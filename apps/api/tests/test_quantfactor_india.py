"""India universe plumbing — index_group normalization.

astra_portfolio pools filter on NIFTY100/NIFTY200/NSE250; anything else
silently drops the stock from every recommendation pool, so the mapping is
load-bearing.
"""
from nq_api.jobs.quantfactor_sync import _normalize_india_index_group


def test_collector_legacy_label_maps_to_pool():
    assert _normalize_india_index_group("LM 250") == "NIFTY200"
    assert _normalize_india_index_group("LM250") == "NIFTY200"


def test_official_labels_pass_through():
    assert _normalize_india_index_group("NIFTY100") == "NIFTY100"
    assert _normalize_india_index_group("NIFTY200") == "NIFTY200"
    assert _normalize_india_index_group("NSE250") == "NSE250"


def test_midcap_and_blank_and_unknown():
    assert _normalize_india_index_group("NIFTY MIDCAP 150") == "NIFTY200"
    assert _normalize_india_index_group(None) == "NIFTY200"
    assert _normalize_india_index_group("") == "NIFTY200"
    assert _normalize_india_index_group(float("nan")) == "NIFTY200"
    assert _normalize_india_index_group("SOMETHING ELSE") == "NSE250"
