-- Add agent-critical fields to score_cache for PARA-DEBATE context enrichment.
-- These columns are populated by nightly_score.py and read by _build_context_from_cache().
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS momentum_raw NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS gross_profit_margin NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS piotroski INT;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS pb_ratio NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS beta NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS realized_vol_1y NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS short_interest_pct NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS insider_cluster_score NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS accruals_ratio NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS revenue_growth_yoy NUMERIC;
ALTER TABLE public.score_cache ADD COLUMN IF NOT EXISTS debt_equity NUMERIC;