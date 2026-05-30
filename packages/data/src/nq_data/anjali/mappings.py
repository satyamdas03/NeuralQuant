"""Column mappings from Excel headers to Supabase anjali_enrichment columns.

Each mapping: excel_header → (db_column, quintile_db_column, dtype)
  - db_column: the Supabase column name for the raw numeric value
  - quintile_db_column: the Supabase column name for the quintile color label (None if uncolored)
  - dtype: "float" or "text" — how to coerce the Excel cell value

Excel headers must EXACTLY match what build_excel.py writes (including case).
"""

# ────────────────────────────────────────────────────────────
# S&P 500 and SmallMidCap sheets use the same column layout
# (SmallMidCap has an extra "Index" column handled separately)
# ────────────────────────────────────────────────────────────
_SP500_COL_MAP: dict[str, tuple[str, str | None, str]] = {
    # Identity (no quintile)
    "Ticker": ("ticker", None, "text"),
    "Sector": ("sector", None, "text"),
    "Sub Sector": ("sub_sector", None, "text"),
    # Index group — SmallMidCap only; ignored for SP500
    "Index": ("_index_derive", None, "text"),
    # Growth (colored)
    "Sales YoY Growth": ("sales_yoy_growth", "sales_yoy_growth_quintile", "float"),
    "NetProfit YoY Growth": ("net_profit_yoy_growth", "net_profit_yoy_growth_quintile", "float"),
    "Sales TTM 1Yr Growth": ("sales_ttm_1yr_growth", "sales_ttm_1yr_growth_quintile", "float"),
    "NetProfit TTM 1Yr Growth": ("net_profit_ttm_1yr_growth", "net_profit_ttm_1yr_growth_quintile", "float"),
    "QoQ Sales Growth": ("qoq_sales_growth", "qoq_sales_growth_quintile", "float"),
    "QoQ Profit Growth": ("qoq_profit_growth", "qoq_profit_growth_quintile", "float"),
    # Returns (colored)
    "3M Return": ("return_3m", "return_3m_quintile", "float"),
    "6M Return": ("return_6m", "return_6m_quintile", "float"),
    "1Yr Return": ("return_1yr", "return_1yr_quintile", "float"),
    "2Yr Return": ("return_2yr", "return_2yr_quintile", "float"),
    # Valuation (colored)
    "PE Ratio": ("pe_ratio", "pe_ratio_quintile", "float"),
    "Future PE": ("future_pe", "future_pe_quintile", "float"),
    "TTM PEG": ("ttm_peg", "ttm_peg_quintile", "float"),
    "Future PEG": ("future_peg", "future_peg_quintile", "float"),
    # Uncolored ratios
    "PB Ratio": ("pb_ratio", None, "float"),
    "EV/Sales": ("ev_sales", None, "float"),
    "EV/EBITDA": ("ev_ebitda", None, "float"),
    # Uncolored size
    "Market Cap (B)": ("market_cap_b", None, "float"),
    "Revenue (B)": ("revenue_b", None, "float"),
    "TTM Revenue (B)": ("ttm_revenue_b", None, "float"),
    # Risk (colored)
    "QtrStd": ("qtr_std", "qtr_std_quintile", "float"),
    "YrStd": ("yr_std", "yr_std_quintile", "float"),
    "Qtr Beta": ("qtr_beta", "qtr_beta_quintile", "float"),
    "Yr Beta": ("yr_beta", "yr_beta_quintile", "float"),
    # Institutional (uncolored)
    "DII Quarter": ("dii_quarter", None, "float"),
    "DII 1Yr": ("dii_1yr", None, "float"),
    "FII Quarter": ("fii_quarter", None, "float"),
    "FII 1Yr": ("fii_1yr", None, "float"),
    # Scores (uncolored)
    "RETURN SCORE": ("return_score", None, "float"),
    "GROWTH SCORE": ("growth_score", None, "float"),
    "VALUATION SCORE": ("valuation_score", None, "float"),
    "RISK SCORE": ("risk_score", None, "float"),
}

# ────────────────────────────────────────────────────────────
# NSE 100 (Indian) sheet
# ────────────────────────────────────────────────────────────
_NSE_COL_MAP: dict[str, tuple[str, str | None, str]] = {
    # Identity
    "Index Name": ("index_name", None, "text"),
    "NseCode": ("ticker", None, "text"),
    "Sector": ("sector", None, "text"),
    "Sub Sector": ("sub_sector", None, "text"),
    # Growth (colored; Indian sheet omits QoQ columns)
    "Sales YoY Growth": ("sales_yoy_growth", "sales_yoy_growth_quintile", "float"),
    "NetProfit YoY Growth": ("net_profit_yoy_growth", "net_profit_yoy_growth_quintile", "float"),
    "Sales TTM 1Yr Growth": ("sales_ttm_1yr_growth", "sales_ttm_1yr_growth_quintile", "float"),
    "NetProfit TTM 1Yr Growth": ("net_profit_ttm_1yr_growth", "net_profit_ttm_1yr_growth_quintile", "float"),
    # Returns (colored)
    "3M Return": ("return_3m", "return_3m_quintile", "float"),
    "6M Return": ("return_6m", "return_6m_quintile", "float"),
    "1Yr Return": ("return_1yr", "return_1yr_quintile", "float"),
    "2Yr Return": ("return_2yr", "return_2yr_quintile", "float"),
    # Valuation (colored)
    "PE Ratio": ("pe_ratio", "pe_ratio_quintile", "float"),
    "Future PE": ("future_pe", "future_pe_quintile", "float"),
    "TTM PEG": ("ttm_peg", "ttm_peg_quintile", "float"),
    "Future PEG": ("future_peg", "future_peg_quintile", "float"),
    # Composite scores (uncolored)
    "Alpha": ("alpha", None, "float"),
    "Risk": ("risk_score", None, "float"),
    "Final Score": ("final_score", None, "float"),
    # Institutional (uncolored)
    "DII Quarter": ("dii_quarter", None, "float"),
    "DII 1Yr": ("dii_1yr", None, "float"),
    "FII Quarter": ("fii_quarter", None, "float"),
    "FII 1Yr": ("fii_1yr", None, "float"),
    # Risk (colored)
    "QtrStd": ("qtr_std", "qtr_std_quintile", "float"),
    "YrStd": ("yr_std", "yr_std_quintile", "float"),
    "Qtr Beta": ("qtr_beta", "qtr_beta_quintile", "float"),
    "Yr Beta": ("yr_beta", "yr_beta_quintile", "float"),
    # Category scores (uncolored)
    "RETURN SCORE": ("return_score", None, "float"),
    "GROWTH SCORE": ("growth_score", None, "float"),
    "VALUATION SCORE": ("valuation_score", None, "float"),
    "RISK SCORE": ("risk_score", None, "float"),
    # Admin (uncolored)
    "Rebalance Date": ("rebalance_date", None, "text"),
    "Future Return": ("future_return", None, "float"),
    "Strategy Stocks": ("strategy_stocks", None, "text"),
    "Stocks List": ("stocks_list", None, "text"),
}

# Maps Index column values to index_group codes
INDEX_GROUP_MAP = {
    "MidCap 400": "SP400",
    "SmallCap 600": "SP600",
}

# Sheet name → metadata for ingestion
SHEET_META = {
    "S&P 500 Analysis": {
        "market": "US",
        "index_group": "SP500",
        "col_map": _SP500_COL_MAP,
    },
    "SmallMidCap Analysis": {
        "market": "US",
        "index_group_derive": "Index",
        "col_map": _SP500_COL_MAP,
    },
    "NSE 100 Analysis": {
        "market": "IN",
        "index_group": "NSE250",
        "col_map": _NSE_COL_MAP,
    },
}