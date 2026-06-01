-- Phase 3: Quarterly performance testing tables
-- Tracks selection-based portfolio tests for MicroCap and SmallCap strategies

CREATE TABLE IF NOT EXISTS quarterly_test_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date DATE NOT NULL,
  quarter TEXT NOT NULL,               -- e.g. 'Q1FY27' (Apr-Jun 2026)
  test_type TEXT NOT NULL CHECK (test_type IN ('microcap', 'smallcap')),
  selected_tickers TEXT[] NOT NULL,     -- array of tickers selected
  selection_criteria JSONB NOT NULL,    -- snapshot of criteria used
  anjali_snapshot JSONB NOT NULL,       -- scores at time of selection
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quarterly_test_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES quarterly_test_runs(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  market TEXT DEFAULT 'IN',
  entry_price NUMERIC NOT NULL,         -- price on selection date
  exit_price NUMERIC,                  -- price at quarter end (NULL until evaluated)
  return_pct NUMERIC,                  -- (exit - entry) / entry * 100
  benchmark_return_pct NUMERIC,         -- Nifty50 return same period
  alpha NUMERIC,                       -- return_pct - benchmark_return_pct
  evaluated_at DATE,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_runs_quarter
  ON quarterly_test_runs (quarter, test_type);
CREATE INDEX IF NOT EXISTS idx_test_results_run
  ON quarterly_test_results (run_id);

-- RLS: service_role full access, anon read-only
ALTER TABLE quarterly_test_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE quarterly_test_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access test_runs"
  ON quarterly_test_runs FOR ALL
  TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Anon read test_runs"
  ON quarterly_test_runs FOR SELECT
  TO anon USING (true);

CREATE POLICY "Service role full access test_results"
  ON quarterly_test_results FOR ALL
  TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Anon read test_results"
  ON quarterly_test_results FOR SELECT
  TO anon USING (true);