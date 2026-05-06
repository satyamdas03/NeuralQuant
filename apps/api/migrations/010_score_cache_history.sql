-- score_cache_history: append-only snapshot of daily scores for walk-forward validation
-- Unlike score_cache (UPSERT/overwrite), this table INSERTs every nightly run,
-- building historical depth needed for accuracy metrics.

CREATE TABLE IF NOT EXISTS score_cache_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    composite_score DOUBLE PRECISION,
    score_1_10 INTEGER,
    regime_id INTEGER,
    regime_label TEXT,
    quality_percentile DOUBLE PRECISION,
    momentum_percentile DOUBLE PRECISION,
    value_percentile DOUBLE PRECISION,
    low_vol_percentile DOUBLE PRECISION,
    short_interest_percentile DOUBLE PRECISION,
    insider_percentile DOUBLE PRECISION,
    pe_ttm DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    gross_profit_margin DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_score_cache_history_ticker ON score_cache_history(ticker, market);
CREATE INDEX IF NOT EXISTS idx_score_cache_history_date ON score_cache_history(computed_at);

-- RLS: service_role can do everything, anon read-only
ALTER TABLE score_cache_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON score_cache_history FOR ALL USING (true) WITH CHECK (true);