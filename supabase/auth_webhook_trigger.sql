-- ============================================================
-- Supabase Auth Webhook — Welcome Email on Signup
--
-- Run in: Supabase Dashboard → SQL Editor
-- This fires POST to /auth/webhook when a new user signs up.
-- ============================================================

-- Step 1: Enable pg_net extension (required for HTTP calls from Postgres)
CREATE EXTENSION IF NOT EXISTS pg_net SCHEMA extensions;

-- Step 2: Create the database webhook trigger
-- Uses supabase_functions.http_request (built into Supabase)
DROP TRIGGER IF EXISTS on_user_created ON auth.users;

CREATE TRIGGER on_user_created
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION supabase_functions.http_request(
  'https://neuralquant.onrender.com/auth/webhook',
  'POST',
  '{"Content-Type":"application/json"}',
  '{}',
  '5000'
);