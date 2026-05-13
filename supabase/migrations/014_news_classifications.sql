-- Migration 014: news_classifications table
-- Stores LLM-classified headlines for signal generation and backtesting.
-- Written by news_pipeline.py (packages/data/src/nq_data/news_pipeline.py).
-- Read by live pipeline for signal-to-order bridge.

CREATE TABLE IF NOT EXISTS news_classifications (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    headline TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'finnhub',
    published_at TIMESTAMPTZ,
    direction TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    materiality DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    rationale TEXT,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(ticker, headline)
);

CREATE INDEX IF NOT EXISTS idx_news_class_ticker ON news_classifications (ticker, classified_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_class_direction ON news_classifications (direction, classified_at DESC);

ALTER TABLE news_classifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read news_class" ON news_classifications FOR SELECT USING (true);
CREATE POLICY "Service write news_class" ON news_classifications FOR INSERT WITH CHECK (true);
