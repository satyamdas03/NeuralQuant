-- 008_roe_fcf_columns.sql
-- Add ROE and FCF Yield columns to score_cache for sector median comparisons
-- Fixes: FUNDAMENTAL agent sector comparison, HEAD ANALYST cross-reference

ALTER TABLE IF EXISTS public.score_cache
    ADD COLUMN IF NOT EXISTS roe float,
    ADD COLUMN IF NOT EXISTS fcf_yield float;

COMMENT ON COLUMN public.score_cache.roe IS 'Return on Equity (decimal, e.g. 0.15 = 15%)';
COMMENT ON COLUMN public.score_cache.fcf_yield IS 'Free Cash Flow Yield (decimal, e.g. 0.05 = 5%)';
