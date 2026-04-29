-- Add meta fields to score_cache for /meta endpoint fallback on Render
-- These columns are populated by nightly_score.py and read by /stocks/{ticker}/meta
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS long_name TEXT;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS analyst_rec TEXT;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS earnings_date TEXT;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS dividend_yield NUMERIC;