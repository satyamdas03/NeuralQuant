-- Phase 3: Mobile push notification tokens
-- Stores Expo push tokens for iOS/Android push notifications

CREATE TABLE IF NOT EXISTS mobile_push_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  token TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, platform)
);

-- RLS: users manage their own tokens
ALTER TABLE mobile_push_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own push tokens"
  ON mobile_push_tokens FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert own push tokens"
  ON mobile_push_tokens FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users delete own push tokens"
  ON mobile_push_tokens FOR DELETE
  USING (auth.uid() = user_id);

CREATE POLICY "Service role full access push tokens"
  ON mobile_push_tokens FOR ALL
  TO service_role USING (true) WITH CHECK (true);