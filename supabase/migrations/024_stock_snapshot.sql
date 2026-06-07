-- Migration 024: stock_snapshot
-- One table for ALL live stock data: prices, fundamentals, enrichment.
-- Replaces: _META_CACHE, _price_cache, enrichment_cache reads, and the 6-tier fallback cascade.
-- Refresh: every 30 minutes via GitHub Actions → market_refresh.py

CREATE TABLE IF NOT EXISTS stock_snapshot (
    ticker              TEXT NOT NULL,
    market              TEXT NOT NULL DEFAULT 'US',
    price               NUMERIC,
    change_pct          NUMERIC,
    volume              BIGINT,
    market_cap          NUMERIC,
    pe_ttm              NUMERIC,
    eps                 NUMERIC,
    beta                NUMERIC,
    pb_ratio            NUMERIC,
    week_52_high        NUMERIC,
    week_52_low         NUMERIC,
    earnings_date       TEXT,
    analyst_target      NUMERIC,
    recommendation      TEXT,
    rsi_14d             NUMERIC,
    macd_signal         NUMERIC,
    insider_score       NUMERIC,
    news_sentiment      NUMERIC,
    sector              TEXT,
    sub_sector          TEXT,
    company_name        TEXT,
    currency            TEXT DEFAULT 'USD',
    cached_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale               BOOLEAN NOT NULL DEFAULT false,
    source              TEXT DEFAULT 'fmp',  -- 'fmp' | 'yfinance' | 'fallback'
    PRIMARY KEY (ticker, market)
);

-- Hot-path indexes for API endpoints
CREATE INDEX IF NOT EXISTS idx_snapshot_market_cached_at
    ON stock_snapshot (market, cached_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_change_pct
    ON stock_snapshot (market, change_pct DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_snapshot_sector
    ON stock_snapshot (sector);
CREATE INDEX IF NOT EXISTS idx_snapshot_stale
    ON stock_snapshot (stale) WHERE stale = true;

-- RLS: public read, service role write
ALTER TABLE stock_snapshot ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read stock_snapshot"
    ON stock_snapshot FOR SELECT USING (true);
CREATE POLICY "Service role write stock_snapshot"
    ON stock_snapshot FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE stock_snapshot IS 'Live stock snapshot refreshed every 30 min by GHA. Primary data source for /stocks, /screener, /market/movers.';
