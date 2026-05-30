-- 012_anjali_enrichment.sql
-- Anjali enrichment data from AnjaliValueStocks screener
-- PK: (ticker, market, index_group) — one row per stock per index

-- NOTE: This table likely already exists. If running fresh, uncomment CREATE TABLE below.
-- If migrating an existing table, just run the ALTER statements.

-- Drop all existing index_group constraints (different migration runs used different names)
ALTER TABLE anjali_enrichment DROP CONSTRAINT IF EXISTS chk_anjali_index_group;
ALTER TABLE anjali_enrichment DROP CONSTRAINT IF EXISTS anjali_enrichment_index_group_check;

-- Add unified constraint covering ALL values used anywhere in the codebase:
-- SP500, SP400, SP600: US universe groups
-- SP400+SP600: combined SmallMidCap (Excel ingestor fallback)
-- NIFTY100: Indian NSE 100 (Excel "NSE 100 Analysis" sheet)
-- NIFTY200: Indian NSE 200 (yfinance collector nightly job)
-- NSE250: legacy alias for NIFTY100 (Excel ingestor SHEET_META mapping)
ALTER TABLE anjali_enrichment ADD CONSTRAINT chk_anjali_index_group
    CHECK (index_group IN ('SP500', 'SP400', 'SP600', 'SP400+SP600', 'NIFTY100', 'NIFTY200', 'NSE250'));

-- Create table block (skip if table exists)
-- CREATE TABLE IF NOT EXISTS anjali_enrichment (
--     ticker         TEXT NOT NULL,
--     market         TEXT NOT NULL,
--     index_group    TEXT NOT NULL,
--     sector         TEXT,
--     sub_sector     TEXT,
--     index_name     TEXT,
--     fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
--     sales_yoy_growth              FLOAT,
--     net_profit_yoy_growth         FLOAT,
--     sales_ttm_1yr_growth          FLOAT,
--     net_profit_ttm_1yr_growth     FLOAT,
--     qoq_sales_growth              FLOAT,
--     qoq_profit_growth             FLOAT,
--     sales_yoy_growth_quintile              TEXT,
--     net_profit_yoy_growth_quintile         TEXT,
--     sales_ttm_1yr_growth_quintile           TEXT,
--     net_profit_ttm_1yr_growth_quintile      TEXT,
--     qoq_sales_growth_quintile               TEXT,
--     qoq_profit_growth_quintile              TEXT,
--     return_3m     FLOAT,
--     return_6m     FLOAT,
--     return_1yr    FLOAT,
--     return_2yr    FLOAT,
--     return_3m_quintile   TEXT,
--     return_6m_quintile   TEXT,
--     return_1yr_quintile  TEXT,
--     return_2yr_quintile  TEXT,
--     pe_ratio      FLOAT,
--     future_pe     FLOAT,
--     ttm_peg       FLOAT,
--     future_peg    FLOAT,
--     pe_ratio_quintile      TEXT,
--     future_pe_quintile     TEXT,
--     ttm_peg_quintile        TEXT,
--     future_peg_quintile     TEXT,
--     pb_ratio        FLOAT,
--     ev_sales        FLOAT,
--     ev_ebitda       FLOAT,
--     market_cap_b    FLOAT,
--     revenue_b       FLOAT,
--     ttm_revenue_b   FLOAT,
--     qtr_std    FLOAT,
--     yr_std     FLOAT,
--     qtr_beta   FLOAT,
--     yr_beta    FLOAT,
--     qtr_std_quintile   TEXT,
--     yr_std_quintile    TEXT,
--     qtr_beta_quintile  TEXT,
--     yr_beta_quintile   TEXT,
--     dii_quarter   FLOAT,
--     dii_1yr       FLOAT,
--     fii_quarter   FLOAT,
--     fii_1yr       FLOAT,
--     return_score     FLOAT,
--     growth_score     FLOAT,
--     valuation_score  FLOAT,
--     risk_score       FLOAT,
--     alpha        FLOAT,
--     final_score  FLOAT,
--     rebalance_date    TEXT,
--     future_return     FLOAT,
--     strategy_stocks   TEXT,
--     stocks_list       TEXT,
--     PRIMARY KEY (ticker, market, index_group)
-- );

-- Indexes (idempotent — CREATE IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_anjali_market_index_group
    ON anjali_enrichment(market, index_group);
CREATE INDEX IF NOT EXISTS idx_anjali_fetched_at
    ON anjali_enrichment(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_anjali_sector
    ON anjali_enrichment(sector);

-- RLS: service role has full access, anon read-only
ALTER TABLE anjali_enrichment ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can do anything on anjali_enrichment"
    ON anjali_enrichment FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Anon can read anjali_enrichment"
    ON anjali_enrichment FOR SELECT
    USING (true);

COMMENT ON TABLE anjali_enrichment IS 'Stock screening data from AnjaliValueStocks, refreshed nightly. Index groups: SP500, SP400, SP600, SP400+SP600, NIFTY100, NIFTY200, NSE250.';