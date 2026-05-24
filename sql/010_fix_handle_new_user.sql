-- Fix: handle_new_user trigger robustness + diagnostic
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/ajkhyayrbqiuvnsmqrdz/sql/new

-- 1. Verify public.users table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'users'
ORDER BY ordinal_position;

-- 2. Verify trigger exists
SELECT tgname, tgtype, tgenabled
FROM pg_trigger
WHERE tgname = 'on_auth_user_created' AND tgrelid = 'auth.users'::regclass;

-- 3. Re-create the function with robust error handling
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  -- Insert into public.users; ignore if row already exists
  INSERT INTO public.users (id, email, tier)
  VALUES (NEW.id, NEW.email, 'free')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
EXCEPTION WHEN OTHERS THEN
  -- Log error but don't block auth.users creation
  RAISE WARNING 'handle_new_user failed for user %: %', NEW.id, SQLERRM;
  RETURN NEW;
END;
$$;

-- 4. Ensure trigger is installed (re-create to be safe)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 5. Test: manually call the function with a test value
-- DO $$
-- DECLARE
--   test_id UUID := gen_random_uuid();
-- BEGIN
--   RAISE NOTICE 'Testing handle_new_user with id=%', test_id;
--   -- Actually need to insert into auth.users to test trigger...
--   -- Skip automated test — verify via sign-up flow
-- END;
-- $$;
