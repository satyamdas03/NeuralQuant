-- Migration 010: Add paypal_subscription_id column to users table
-- Run in Supabase Dashboard → SQL Editor

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS paypal_subscription_id text;

-- Index for webhook lookups
CREATE INDEX IF NOT EXISTS idx_users_paypal_subscription_id
ON public.users (paypal_subscription_id)
WHERE paypal_subscription_id IS NOT NULL;