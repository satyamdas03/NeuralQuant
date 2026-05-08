CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  risk_profile TEXT CHECK (risk_profile IN ('conservative','balanced','aggressive')),
  time_horizon TEXT CHECK (time_horizon IN ('<1yr','1-3yr','3-5yr','5yr+')),
  goal TEXT CHECK (goal IN ('wealth_building','retirement','education','passive_income','tax_saving')),
  investable_amount TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own profile"
  ON user_profiles FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
