-- 011_anjali_enrichment.sql
-- Anjali Value Screener enrichment data — quintile-scored cross-sectional analysis
-- Populated nightly by the anjali collector pipeline

CREATE TABLE IF NOT EXISTS public.anjali_enrichment (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker                text NOT NULL,
  market                text NOT NULL CHECK (market IN ('US', 'IN')),
  index_group           text,           -- 'SP500','SP400','SP600','NIFTY200'

  -- Growth
  sales_yoy_growth      numeric,
  net_profit_yoy_growth numeric,
  sales_ttm_growth      numeric,
  net_profit_ttm_growth numeric,
  qoq_sales_growth      numeric,
  qoq_profit_growth      numeric,

  -- Returns
  return_3m  numeric,
  return_6m  numeric,
  return_1yr numeric,
  return_2yr numeric,

  -- Valuation
  pe_ratio    numeric,
  future_pe   numeric,
  ttm_peg     numeric,
  future_peg  numeric,
  pb_ratio    numeric,
  ev_sales    numeric,
  ev_ebitda   numeric,

  -- Size (uncolored, informational)
  market_cap_bn numeric,
  revenue_bn    numeric,
  ttm_revenue_bn numeric,

  -- Risk
  qtr_std  numeric,
  yr_std   numeric,
  qtr_beta numeric,
  yr_beta  numeric,

  -- India-specific (NULL until DII/FII fetcher built in Phase 2)
  dii_quarter numeric,
  dii_1yr     numeric,
  fii_quarter numeric,
  fii_1yr     numeric,

  -- Quintile scores (each -4 to +4, composite -16 to +16)
  return_score           numeric,
  growth_score           numeric,
  valuation_score        numeric,
  risk_score             numeric,
  composite_anjali_score numeric,

  -- Loss flags (override growth scoring to -1)
  loss_profit_yoy boolean DEFAULT false,
  loss_profit_ttm boolean DEFAULT false,
  loss_profit_qoq boolean DEFAULT false,

  data_collected_at timestamptz,
  refreshed_at      timestamptz DEFAULT now(),

  UNIQUE (ticker, market)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_anjali_ticker  ON public.anjali_enrichment (ticker, market);
CREATE INDEX IF NOT EXISTS idx_anjali_comp    ON public.anjali_enrichment (composite_anjali_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_anjali_market  ON public.anjali_enrichment (market);
CREATE INDEX IF NOT EXISTS idx_anjali_index   ON public.anjali_enrichment (index_group);

-- RLS: read for all authenticated users, write only for service role
ALTER TABLE public.anjali_enrichment ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anjali_enrichment_read_authenticated"
  ON public.anjali_enrichment FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "anjali_enrichment_read_anon"
  ON public.anjali_enrichment FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "anjali_enrichment_write_service"
  ON public.anjali_enrichment FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Comment for documentation
COMMENT ON TABLE public.anjali_enrichment IS
  'Quintile-scored cross-sectional stock data from the Anjali Value Screener pipeline. Populated nightly by GHA or Render Cron.';