---
name: Session 17 — Landing Page Sign In Button Removed
description: Removed "Sign In" button from landing page. Frontend-only change, no Render redeploy. Commit b7332b7 deployed to Vercel. 2026-05-05.
type: project
originSessionId: b93bc8d3-de2c-4003-929a-85343beddbc7
---

# Session 17 (2026-05-05): Landing Page Sign In Button Removed

## What Changed

Removed the "Sign in" `<Link href="/login">` button from the hero section of the landing page (`apps/web/src/app/page.tsx`).

**Before:** Hero had two buttons side-by-side — "Get started free" (GradientButton → `/dashboard`) and "Sign in" (Link → `/login`).

**After:** Hero has only "Get started free" (GradientButton → `/dashboard`). The `flex flex-wrap gap-3` wrapper became a simple `<div>`.

## Why

Guest access was already enabled in Session 16 (auth wall removed). The "Sign in" button split visitor attention. Removing it funnels all visitors directly to the dashboard, which works without login.

## Files Changed

1. **`apps/web/src/app/page.tsx`** — Removed the `<Link href="/login">` Sign In button and simplified the wrapper div.

## Deployment

- **Commit**: `b7332b7` — `fix: remove Sign In button from landing page`
- **Pushed to**: master
- **Render**: No redeploy needed (frontend-only change)
- **Vercel**: Deployed via `npx vercel --prod` from `apps/web/`
- **Verified**: `curl https://www.neuralquant.co/` returns zero occurrences of "Sign in" on the landing page

## No Backend Changes

This was purely a frontend change. No API routes, middleware, or rate limiting were modified.

## Next Steps

1. Monitor LinkedIn post #2 engagement
2. PayPal sandbox → live mode
3. Run 3-year backtest and publish (expert's #2 critical gap)
4. Antler India/Sydney pre-seed application
5. Create LinkedIn company page