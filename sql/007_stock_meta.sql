-- Stock meta persistent cache (survives server cold starts)
CREATE TABLE IF NOT EXISTS public.stock_meta (
    ticker  TEXT    NOT NULL,
    market  TEXT    NOT NULL DEFAULT 'US',
    data    JSONB  NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, market)
);

-- Allow service_role full access, anon no access
ALTER TABLE public.stock_meta ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_meta" ON public.stock_meta
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');