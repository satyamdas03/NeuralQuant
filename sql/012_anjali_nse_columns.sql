-- 012_anjali_nse_columns.sql
-- Add NSE-specific columns (Alpha, Final Score, Rebalance Date, Future Return, Strategy)
-- and SmallMidCap index group support for Anjali enrichment

ALTER TABLE public.anjali_enrichment
  ADD COLUMN IF NOT EXISTS alpha numeric,           -- NSE: alpha score (backtest-derived)
  ADD COLUMN IF NOT EXISTS final_score numeric,     -- NSE: final composite (alpha + risk)
  ADD COLUMN IF NOT EXISTS rebalance_date date,    -- NSE: portfolio rebalance date
  ADD COLUMN IF NOT EXISTS future_return numeric,   -- NSE: forward return (backtest)
  ADD COLUMN IF NOT EXISTS strategy_stocks text,   -- NSE: strategy stock list
  ADD COLUMN IF NOT EXISTS stocks_list text;         -- NSE: full stock list for index

-- Update index_group CHECK constraint to allow new groups
-- (Was just 'SP500','SP400','SP600','NIFTY200')
-- Now also includes 'SP400+SP600' (combined SmallMidCap) and 'NIFTY100'
ALTER TABLE public.anjali_enrichment DROP CONSTRAINT IF EXISTS anjali_enrichment_index_group_check;
ALTER TABLE public.anjali_enrichment ADD CONSTRAINT anjali_enrichment_index_group_check
  CHECK (index_group IN ('SP500', 'SP400', 'SP600', 'SP400+SP600', 'NIFTY100', 'NIFTY200'));

COMMENT ON COLUMN public.anjali_enrichment.alpha IS 'NSE Alpha score from Anjali backtest';
COMMENT ON COLUMN public.anjali_enrichment.final_score IS 'NSE Final Score (Alpha + Risk composite)';
COMMENT ON COLUMN public.anjali_enrichment.strategy_stocks IS 'NSE: stocks selected by Anjali strategy';