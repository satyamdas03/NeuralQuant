"""Schema-drift wall: every db_columns constant must exist in the live-schema
snapshot headers (data/demo_snapshot/*.csv). Catches column renames permanently."""
import csv
import pathlib

from nq_api import db_columns

ROOT = pathlib.Path(__file__).resolve().parents[3]
SNAP = ROOT / "data" / "demo_snapshot"


def _headers(table: str) -> set[str]:
    with open(SNAP / f"{table}.csv", encoding="utf-8") as fh:
        return set(next(csv.reader(fh)))


def test_score_cache_columns_exist():
    cols = _headers("score_cache")
    for const in (db_columns.COMPOSITE_SCORE, db_columns.COMPUTED_AT,
                  db_columns.RANK_SCORE, db_columns.TICKER, db_columns.MARKET,
                  db_columns.CURRENT_PRICE, db_columns.PE_TTM):
        assert const in cols, f"score_cache missing {const}"


def test_quantfactor_columns_exist():
    cols = _headers("quantfactor_universe")
    for const in (db_columns.QF_PE_RATIO, db_columns.QF_MARKET_CAP_B,
                  db_columns.QF_COMPOSITE, db_columns.QF_INDEX_GROUP,
                  db_columns.G_SCORE, db_columns.RISK_EFF_SCORE,
                  db_columns.IRS_PCT, db_columns.IRS_RAW):
        assert const in cols, f"quantfactor_universe missing {const}"


def test_anjali_columns_exist():
    cols = _headers("anjali_enrichment")
    for const in (db_columns.G_SCORE, db_columns.IRS_PCT,
                  db_columns.COMPOSITE_ANJALI):
        assert const in cols, f"anjali_enrichment missing {const}"


def test_legacy_names_are_not_reintroduced():
    """The exact strings that caused bugs 113/116 must never be real columns."""
    sc = _headers("score_cache")
    assert "composite" not in sc
    assert "composite_at" not in sc
