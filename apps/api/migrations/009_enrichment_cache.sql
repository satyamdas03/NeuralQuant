-- Migration 009: Create enrichment_cache table
-- Stores RSI/MACD/ATR/SMA/insider/news data per ticker with 1-hour TTL
-- Populated by prewarm (top-50) and on-demand fetch, read before live compute

CREATE TABLE IF NOT EXISTS public.enrichment_cache (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker    text NOT NULL,
    market    text NOT NULL DEFAULT 'US',
    cached_at timestamptz NOT NULL DEFAULT now(),

    -- Technical indicators (from Finnhub/yfinance)
    rsi_14              double precision,
    macd_line           double precision,
    macd_signal         double precision,
    macd_hist           double precision,
    atr_14              double precision,
    sma_50              double precision,
    sma_200             double precision,
    price_vs_sma50      double precision,
    price_vs_sma200     double precision,
    volume_today        double precision,
    volume_20d_avg      double precision,
    volume_ratio        double precision,
    finnhub_price       double precision,

    -- Insider sentiment (from Finnhub/EDGAR)
    insider_cluster_score   double precision,
    insider_net_buy_ratio   double precision,
    insider_summary         text,

    -- News sentiment (from Finnhub/yfinance+VADER)
    news_sentiment_label    text,
    news_sentiment_score     double precision,
    news_buzz               double precision,
    news_bullish_pct         double precision,
    news_bearish_pct         double precision,

    -- Unique constraint: one row per ticker+market
    CONSTRAINT enrichment_cache_ticker_market_unique UNIQUE (ticker, market)
);

-- Index for fast lookups by ticker+market+freshness
CREATE INDEX IF NOT EXISTS idx_enrichment_cache_lookup
    ON public.enrichment_cache (ticker, market, cached_at DESC);

-- RLS: allow service role full access, anon read-only
ALTER TABLE public.enrichment_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON public.enrichment_cache
    FOR ALL USING (true) WITH CHECK (true);