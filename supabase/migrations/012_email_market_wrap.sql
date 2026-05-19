-- Migration 012: Add email_market_wrap preference to user_profiles
-- Allows users to opt in/out of daily market wrap emails.
-- Defaults to true so existing users receive wraps from broadcast.

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS email_market_wrap BOOLEAN DEFAULT true;
