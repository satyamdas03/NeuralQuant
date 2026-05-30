-- Anjali enrichment data from AnjaliValueStocks screener
-- Updated twice daily via GHA cron + sync workflow
-- PK: (ticker, market, index_group) — one row per stock per index

CREATE TABLE IF NOT EXISTS anjali_enrichment (
    ticker         TEXT NOT NULL,
    market         TEXT NOT NULL,
    index_group    TEXT NOT NULL,
    sector         TEXT,
    sub_sector     TEXT,
    index_name     TEXT,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Growth raw metrics
    sales_yoy_growth              FLOAT,
    net_profit_yoy_growth         FLOAT,
    sales_ttm_1yr_growth          FLOAT,
    net_profit_ttm_1yr_growth     FLOAT,
    qoq_sales_growth              FLOAT,
    qoq_profit_growth             FLOAT,

    -- Growth quintile colors
    sales_yoy_growth_quintile              TEXT,
    net_profit_yoy_growth_quintile         TEXT,
    sales_ttm_1yr_growth_quintile          TEXT,
    net_profit_ttm_1yr_growth_quintile     TEXT,
    qoq_sales_growth_quintile              TEXT,
    qoq_profit_growth_quintile             TEXT,

    -- Returns raw metrics
    return_3m     FLOAT,
    return_6m     FLOAT,
    return_1yr    FLOAT,
    return_2yr    FLOAT,

    -- Returns quintile colors
    return_3m_quintile   TEXT,
    return_6m_quintile   TEXT,
    return_1yr_quintile  TEXT,
    return_2yr_quintile  TEXT,

    -- Valuation raw metrics
    pe_ratio      FLOAT,
    future_pe     FLOAT,
    ttm_peg       FLOAT,
    future_peg    FLOAT,

    -- Valuation quintile colors
    pe_ratio_quintile      TEXT,
    future_pe_quintile     TEXT,
    ttm_peg_quintile       TEXT,
    future_peg_quintile    TEXT,

    -- Uncolored ratios & size
    pb_ratio        FLOAT,
    ev_sales        FLOAT,
    ev_ebitda       FLOAT,
    market_cap_b    FLOAT,
    revenue_b       FLOAT,
    ttm_revenue_b   FLOAT,

    -- Risk raw metrics
    qtr_std    FLOAT,
    yr_std     FLOAT,
    qtr_beta   FLOAT,
    yr_beta    FLOAT,

    -- Risk quintile colors
    qtr_std_quintile   TEXT,
    yr_std_quintile    TEXT,
    qtr_beta_quintile  TEXT,
    yr_beta_quintile   TEXT,

    -- Institutional (DII/FII)
    dii_quarter   FLOAT,
    dii_1yr       FLOAT,
    fii_quarter   FLOAT,
    fii_1yr       FLOAT,

    -- Category scores
    return_score     FLOAT,
    growth_score     FLOAT,
    valuation_score  FLOAT,
    risk_score       FLOAT,

    -- Indian composite scores
    alpha        FLOAT,
    final_score  FLOAT,

    -- Indian admin columns
    rebalance_date    TEXT,
    future_return     FLOAT,
    strategy_stocks   TEXT,
    stocks_list       TEXT,

    PRIMARY KEY (ticker, market, index_group)
);

-- Constraints
ALTER TABLE anjali_enrichment ADD CONSTRAINT chk_anjali_market
    CHECK (market IN ('US', 'IN'));
ALTER TABLE anjali_enrichment ADD CONSTRAINT chk_anjali_index_group
    CHECK (index_group IN ('SP500', 'SP400', 'SP600', 'NSE250'));

-- Indexes for common queries
CREATE INDEX idx_anjali_market_index_group
    ON anjali_enrichment(market, index_group);
CREATE INDEX idx_anjali_fetched_at
    ON anjali_enrichment(fetched_at DESC);
CREATE INDEX idx_anjali_sector
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

-- Helpful comment
COMMENT ON TABLE anjali_enrichment IS 'Stock screening data from AnjaliValueStocks, refreshed twice daily via GHA cron. Quintile colors: DG/LG/White/LR/DR.';