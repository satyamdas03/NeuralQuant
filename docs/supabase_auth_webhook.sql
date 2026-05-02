-- Supabase auth webhook trigger
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
--
-- Sends a POST to NeuralQuant API when a new user signs up,
-- triggering the welcome email sequence.

-- 1. Enable pg_net extension (required for HTTP requests from Postgres)
CREATE EXTENSION IF NOT EXISTS pg_net SCHEMA extensions;

-- 2. Function that calls the NeuralQuant auth webhook
CREATE OR REPLACE FUNCTION public.notify_neuralquant_signup()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  PERFORM net.http_post(
    url := 'https://neuralquant.onrender.com/auth/webhook',
    headers := '{"Content-Type": "application/json"}'::jsonb,
    body := json_build_object(
      'type', 'INSERT',
      'record', row_to_json(NEW)
    )::text
  );
  RETURN NEW;
END;
$$;

-- 3. Trigger on auth.users INSERT
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_neuralquant_signup();