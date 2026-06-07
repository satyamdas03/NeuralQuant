-- Migration 025: quantfactor_universe
-- Static QuantFactor scores from the AnjaliValueStocks Excel sheets.
-- Refresh: weekly via GitHub Actions → quantfactor_sync.py
-- Replaces: anjali_enrichment table (data will be migrated then old table dropped)

CREATE TABLE IF NOT EXISTS quantfactor_universe (
    ticker              TEXT NOT NULL,
    market              TEXT NOT NULL DEFAULT 'US',
    index_group         TEXT,  -- 'SP500', 'SP400', 'SP600', 'NIFTY100', 'NIFTY200', etc.
    sector              TEXT,
    sub_sector          TEXT,

    -- Raw growth metrics
    sales_yoy_growth            NUMERIC,
    net_profit_yoy_growth       NUMERIC,
    sales_ttm_1yr_growth        NUMERIC,
    net_profit_ttm_1yr_growth   NUMERIC,
    qoq_sales_growth            NUMERIC,
    qoq_profit_growth           NUMERIC,

    -- Raw return metrics
    return_3m             NUMERIC,
    return_6m             NUMERIC,
    return_1yr            NUMERIC,
    return_2yr            NUMERIC,

    -- Raw valuation metrics
    pe_ratio              NUMERIC,
    future_pe             NUMERIC,
    ttm_peg               NUMERIC,
    future_peg            NUMERIC,

    -- Raw ratio metrics (uncolored)
    pb_ratio              NUMERIC,
    ev_sales              NUMERIC,
    ev_ebitda             NUMERIC,

    -- Size metrics
    market_cap_b          NUMERIC,
    revenue_b             NUMERIC,
    ttm_revenue_b         NUMERIC,

    -- Risk metrics
    qtr_std               NUMERIC,
    yr_std                NUMERIC,
    qtr_beta              NUMERIC,
    yr_beta               NUMERIC,

    -- DII/FII (India only, often empty)
    dii_quarter           NUMERIC,
    dii_1yr               NUMERIC,
    fii_quarter           NUMERIC,
    fii_1yr               NUMERIC,

    -- Quintile scores (-4 to +4)
    return_score          NUMERIC,
    growth_score          NUMERIC,
    valuation_score       NUMERIC,
    risk_score            NUMERIC,

    -- Composite scores
    composite_score       NUMERIC,  -- sum of 4 scores, range -16 to +16
    g_score               NUMERIC,  -- growth + return + valuation, range -12 to +12
    risk_eff_score        NUMERIC,  -- risk_score * 2.0, range -8 to +8
    irs_raw               NUMERIC,  -- g_score + risk_eff_score, range -20 to +20
    irs_pct               NUMERIC,  -- ((irs_raw + 20) / 40) * 100, range 0-100

    -- India-only extras
    alpha_score           NUMERIC,  -- return_score + growth_score
    final_score           NUMERIC,  -- sum of all 4 scores
    rebalance_date        TEXT,
    future_return         NUMERIC,
    strategy_stocks       TEXT,
    stocks_list           TEXT,

    -- Loss flags
    loss_profit_yoy       BOOLEAN DEFAULT false,
    loss_profit_ttm       BOOLEAN DEFAULT false,
    loss_profit_qoq       BOOLEAN DEFAULT false,

    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (ticker, market)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_qf_market_index_group
    ON quantfactor_universe (market, index_group);
CREATE INDEX IF NOT EXISTS idx_qf_sector
    ON quantfactor_universe (sector);
CREATE INDEX IF NOT EXISTS idx_qf_irs_pct
    ON quantfactor_universe (irs_pct DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_qf_composite
    ON quantfactor_universe (composite_score DESC NULLS LAST);

-- RLS: public read, service role write
ALTER TABLE quantfactor_universe ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read quantfactor_universe"
    ON quantfactor_universe FOR SELECT USING (true);
CREATE POLICY "Service role write quantfactor_universe"
    ON quantfactor_universe FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE quantfactor_universe IS 'QuantFactor static scores from AnjaliValueStocks Excel. Weekly refresh via GHA. Replaces anjali_enrichment.';
