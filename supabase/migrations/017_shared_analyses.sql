-- 017_shared_analyses.sql
-- Shareable PARA-DEBATE analysis pages — viral growth loop
-- Each analysis gets a unique share_id, viewable by anyone without auth

CREATE TABLE IF NOT EXISTS public.shared_analyses (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id          TEXT UNIQUE NOT NULL,             -- short random ID (token_urlsafe(12))
    ticker            TEXT NOT NULL,                    -- e.g. "AAPL", "RELIANCE.NS"
    market            TEXT NOT NULL DEFAULT 'US' CHECK (market IN ('US', 'IN')),
    verdict           TEXT NOT NULL DEFAULT 'HOLD' CHECK (verdict IN ('STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL', 'BULL', 'BEAR', 'NEUTRAL')),
    score             NUMERIC NOT NULL DEFAULT 5,       -- 1-10 composite score
    analyst_response  JSONB NOT NULL DEFAULT '{}'::jsonb,  -- full PARA-DEBATE output
    score_data        JSONB DEFAULT '{}'::jsonb,        -- AIScore JSON
    meta_data         JSONB DEFAULT '{}'::jsonb,         -- StockMeta JSON
    sentiment_data    JSONB DEFAULT '{}'::jsonb,        -- SentimentResponse JSON
    view_count        INT NOT NULL DEFAULT 0,
    creator_id       UUID REFERENCES auth.users(id),   -- NULL for guest shares
    creator_email     TEXT,
    is_public         BOOLEAN DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shared_analyses_share_id ON public.shared_analyses(share_id);
CREATE INDEX IF NOT EXISTS idx_shared_analyses_ticker ON public.shared_analyses(ticker, market);
CREATE INDEX IF NOT EXISTS idx_shared_analyses_created_at ON public.shared_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shared_analyses_creator_id ON public.shared_analyses(creator_id);

ALTER TABLE public.shared_analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read shared analyses" ON public.shared_analyses
    FOR SELECT USING (is_public = true);

CREATE POLICY "Creator delete shared analyses" ON public.shared_analyses
    FOR DELETE USING (auth.uid() = creator_id);

CREATE POLICY "Service role full access shared analyses" ON public.shared_analyses
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE public.shared_analyses IS 'Shareable PARA-DEBATE analysis pages for viral distribution.';