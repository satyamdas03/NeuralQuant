-- 013: signal_log table for trading signal calibration
-- Stores every signal (live and dry-run) with entry/exit tracking, PnL, and resolution.

CREATE TABLE IF NOT EXISTS signal_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id UUID DEFAULT gen_random_uuid() UNIQUE,
    ticker TEXT NOT NULL,
    signal_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    market TEXT NOT NULL DEFAULT 'US',
    direction TEXT NOT NULL DEFAULT 'bullish' CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    composite_score DOUBLE PRECISION DEFAULT 0.0,
    edge DOUBLE PRECISION DEFAULT 0.0,
    entry_price DOUBLE PRECISION DEFAULT 0.0,
    exit_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_date TIMESTAMPTZ,
    strategy TEXT NOT NULL DEFAULT 'default',
    bet DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_signal_log_ticker_date ON signal_log (ticker, signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_signal_log_market_date ON signal_log (market, signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_signal_log_resolved ON signal_log (resolved, resolution_date DESC);
CREATE INDEX IF NOT EXISTS idx_signal_log_strategy ON signal_log (strategy, signal_date DESC);

-- Enable RLS
ALTER TABLE signal_log ENABLE ROW LEVEL SECURITY;

-- Service role can do everything
CREATE POLICY "Service role full access on signal_log" ON signal_log
    FOR ALL USING (auth.role() = 'service_role');

-- Anonymous read-only (for dashboard)
CREATE POLICY "Anonymous read on signal_log" ON signal_log
    FOR SELECT USING (true);

COMMENT ON TABLE signal_log IS 'Trading signal log with entry/exit tracking, PnL resolution, and calibration metrics.';