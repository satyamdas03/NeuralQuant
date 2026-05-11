-- Migration 012: score_cache_history table
-- Stores historical snapshots of score_cache for walk-forward validation on /performance page.
-- The nightly_score GHA script and score_cache.upsert_scores() both write here.

CREATE TABLE IF NOT EXISTS score_cache_history (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    composite_score DOUBLE PRECISION,
    score_1_10 INTEGER,
    regime_id INTEGER DEFAULT 1,
    regime_label TEXT DEFAULT 'Risk-On',
    quality_percentile DOUBLE PRECISION DEFAULT 0.5,
    momentum_percentile DOUBLE PRECISION DEFAULT 0.5,
    value_percentile DOUBLE PRECISION DEFAULT 0.5,
    low_vol_percentile DOUBLE PRECISION DEFAULT 0.5,
    short_interest_percentile DOUBLE PRECISION DEFAULT 0.5,
    insider_percentile DOUBLE PRECISION DEFAULT 0.5,
    pe_ttm DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    gross_profit_margin DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for walk-forward queries: distinct dates per market
CREATE INDEX IF NOT EXISTS idx_score_history_market_date ON score_cache_history (market, computed_at);
CREATE INDEX IF NOT EXISTS idx_score_history_ticker ON score_cache_history (ticker, market);

-- RLS: allow anonymous reads (performance page is public)
ALTER TABLE score_cache_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read score history" ON score_cache_history FOR SELECT USING (true);
CREATE POLICY "Service role write score history" ON score_cache_history FOR INSERT WITH CHECK (true);