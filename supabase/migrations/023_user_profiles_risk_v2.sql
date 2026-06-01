-- Phase 3: Add QuantAstra risk profile to user_profiles
-- 3 risk levels: low, high, very_high
-- Set via the 3-question risk profiling flow in QuantAstra

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS astra_risk_profile TEXT
    CHECK (astra_risk_profile IN ('low', 'high', 'very_high')),
  ADD COLUMN IF NOT EXISTS risk_profile_set_at TIMESTAMPTZ;

COMMENT ON COLUMN user_profiles.astra_risk_profile IS 'QuantAstra risk profile: low (LM250 only), high (LM250+SmallCap+MicroCap), very_high (+Turnaround)';
COMMENT ON COLUMN user_profiles.risk_profile_set_at IS 'Timestamp when risk profile was last set/changed';