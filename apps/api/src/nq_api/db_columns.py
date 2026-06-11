"""Single source of truth for Supabase column names.

Every historical column-name bug class is pinned here:
  composite vs composite_score (bug 116) · composite_at vs computed_at (bug 113)
  quantfactor schema drift (bug 121)

Names below are verified against the live schema export of 2026-06-11
(data/demo_snapshot/*.csv headers). When adding a query, import the constant —
never type the column name as a raw string.

NOTE on regime features: the HMM models were trained with feature name
`nifty_1m_return` while the macro snapshot attribute is `nifty_return_1m`.
The mapping lives in packages/signals/src/nq_signals/engine.py and is
INTENTIONAL — renaming either side breaks model loading (bug 118 fix).
"""

# ── score_cache ──────────────────────────────────────────────────────────────
COMPOSITE_SCORE = "composite_score"
COMPUTED_AT     = "computed_at"
RANK_SCORE      = "rank_score"      # score_1_10 is DERIVED from this, not stored
TICKER          = "ticker"
MARKET          = "market"
CURRENT_PRICE   = "current_price"
PE_TTM          = "pe_ttm"

# ── quantfactor_universe ─────────────────────────────────────────────────────
QF_PE_RATIO     = "pe_ratio"        # NOT pe_ttm in this table
QF_MARKET_CAP_B = "market_cap_b"    # NOT market_cap in this table
QF_COMPOSITE    = "composite_score"
QF_INDEX_GROUP  = "index_group"

# ── anjali_enrichment / quantfactor scoring ──────────────────────────────────
G_SCORE         = "g_score"
RISK_EFF_SCORE  = "risk_eff_score"
IRS_PCT         = "irs_pct"
IRS_RAW         = "irs_raw"
COMPOSITE_ANJALI = "composite_anjali_score"  # anjali_enrichment only

# ── regime features (bug 118 — canonical macro attribute name) ───────────────
NIFTY_RETURN_1M = "nifty_return_1m"
