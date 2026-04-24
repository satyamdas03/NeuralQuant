-- Referral system: codes, tracking, and bonus queries
CREATE TABLE IF NOT EXISTS public.referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  code TEXT UNIQUE NOT NULL,
  referred_email TEXT,
  referred_user_id UUID REFERENCES auth.users(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'redeemed')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Add referral_bonus_queries column to users
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS referral_bonus_queries INTEGER DEFAULT 0;

-- Index for looking up referral codes
CREATE INDEX IF NOT EXISTS idx_referrals_code ON public.referrals(code);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON public.referrals(referrer_id);

-- RLS
ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own referrals"
  ON public.referrals FOR SELECT
  USING (referrer_id = (SELECT auth.uid()));

CREATE POLICY "Users can insert own referrals"
  ON public.referrals FOR INSERT
  WITH CHECK (referrer_id = (SELECT auth.uid()));

-- Function: apply referral bonus on signup
CREATE OR REPLACE FUNCTION public.handle_referral_signup()
RETURNS TRIGGER AS $$
DECLARE
  ref_code TEXT;
  ref_row RECORD;
BEGIN
  ref_code := NEW.raw_user_meta_data->>'referral_code';

  IF ref_code IS NOT NULL THEN
    SELECT * INTO ref_row FROM public.referrals WHERE code = ref_code AND status = 'active';

    IF ref_row.id IS NOT NULL THEN
      UPDATE public.referrals SET
        status = 'redeemed',
        referred_email = NEW.email,
        referred_user_id = NEW.id
      WHERE id = ref_row.id;

      UPDATE public.users SET
        referral_bonus_queries = referral_bonus_queries + 5
      WHERE id = ref_row.referrer_id;

      UPDATE public.users SET
        referral_bonus_queries = referral_bonus_queries + 5
      WHERE id = NEW.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_referral_signup ON auth.users;
CREATE TRIGGER on_referral_signup
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_referral_signup();