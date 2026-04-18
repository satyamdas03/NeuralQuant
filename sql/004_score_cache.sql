-- Phase 4 Pillar B: nightly score cache for fast screener responses.
CREATE TABLE IF NOT EXISTS public.score_cache (
  ticker TEXT NOT NULL,
  market TEXT NOT NULL CHECK (market IN ('US','IN')),
  sector TEXT,
  composite_score NUMERIC,
  rank_score INT,
  value_percentile NUMERIC,
  momentum_percentile NUMERIC,
  quality_percentile NUMERIC,
  low_vol_percentile NUMERIC,
  short_interest_percentile NUMERIC,
  current_price NUMERIC,
  analyst_target NUMERIC,
  pe_ttm NUMERIC,
  market_cap NUMERIC,
  week52_high NUMERIC,
  week52_low NUMERIC,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (ticker, market)
);

CREATE INDEX IF NOT EXISTS idx_score_cache_market_score
  ON public.score_cache(market, composite_score DESC);

CREATE INDEX IF NOT EXISTS idx_score_cache_computed_at
  ON public.score_cache(computed_at DESC);

ALTER TABLE public.score_cache ENABLE ROW LEVEL SECURITY;

-- anon can read (public screener data)
DROP POLICY IF EXISTS score_cache_public_read ON public.score_cache;
CREATE POLICY score_cache_public_read ON public.score_cache FOR SELECT USING (true);
