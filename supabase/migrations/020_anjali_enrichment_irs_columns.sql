-- Phase 3: Add IRS (Investment Readiness Score) columns to anjali_enrichment
-- G Score = growth_score + return_score + valuation_score (-12 to +12)
-- Risk Efficiency Score = risk_score * 2.0 (-8 to +8)
-- IRS Raw = g_score + risk_eff_score (-20 to +20)
-- IRS % = ((irs_raw + 20) / 40) * 100 (0 to 100)

ALTER TABLE anjali_enrichment
  ADD COLUMN IF NOT EXISTS g_score NUMERIC,
  ADD COLUMN IF NOT EXISTS risk_eff_score NUMERIC,
  ADD COLUMN IF NOT EXISTS irs_raw NUMERIC,
  ADD COLUMN IF NOT EXISTS irs_pct NUMERIC;

CREATE INDEX IF NOT EXISTS idx_anjali_irs_pct
  ON anjali_enrichment (irs_pct DESC NULLS LAST);

COMMENT ON COLUMN anjali_enrichment.g_score IS 'Quantitative Conviction Score: growth + return + valuation, range -12 to +12';
COMMENT ON COLUMN anjali_enrichment.risk_eff_score IS 'Risk Efficiency Score: risk_score * 2.0, range -8 to +8';
COMMENT ON COLUMN anjali_enrichment.irs_raw IS 'Investment Readiness Score raw: g_score + risk_eff_score, range -20 to +20';
COMMENT ON COLUMN anjali_enrichment.irs_pct IS 'Investment Readiness Score %: ((irs_raw+20)/40)*100, range 0-100';