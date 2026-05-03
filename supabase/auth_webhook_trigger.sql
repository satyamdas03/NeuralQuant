-- ============================================================
-- Supabase Auth Webhook Trigger
-- Fires POST to NeuralQuant API when a new user signs up,
-- so the welcome email sequence starts automatically.
--
-- Run this in: Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Enable pg_net extension (required for HTTP calls from Postgres)
CREATE EXTENSION IF NOT EXISTS pg_net;

-- 2. Grant pg_net access to the supabase_functions_admin role
GRANT USAGE ON SCHEMA pg_net TO supabase_functions_admin;

-- 3. Create the trigger function that calls the webhook
CREATE OR REPLACE FUNCTION public.send_welcome_webhook()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  webhook_url TEXT;
  request_id UUID;
BEGIN
  -- Get the API URL from the environment or hardcode
  -- Replace with your actual Render URL (or use a Supabase secret)
  webhook_url := 'https://neuralquant.onrender.com/auth/webhook';

  -- Only fire on INSERT (new user signup)
  IF TG_OP = 'INSERT' THEN
    SELECT INTO request_id net.http_post(
      url := webhook_url,
      headers := jsonb_build(
        'Content-Type', 'application/json'
      ),
      body := jsonb_build(
        'type', 'auth.user.created',
        'record', jsonb_build_object(
          'id', NEW.id,
          'email', NEW.email,
          'raw_user_meta_data', NEW.raw_user_meta_data
        ),
        'schema_name', 'auth',
        'table', 'users'
      )
    );
  END IF;

  RETURN NEW;
END;
$$;

-- 4. Create the trigger on auth.users
DROP TRIGGER IF EXISTS on_user_created ON auth.users;

CREATE TRIGGER on_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.send_welcome_webhook();

-- ============================================================
-- Verification: run these after creating the trigger
-- ============================================================
-- SELECT * FROM pg_trigger WHERE tgname = 'on_user_created';
-- SELECT proname, prosrc FROM pg_proc WHERE proname = 'send_welcome_webhook';