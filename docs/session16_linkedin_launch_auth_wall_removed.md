---
name: Session 16 — LinkedIn Launch, Auth Wall Removed, Guest Access
description: LinkedIn launch post posted via Composio API (2 attempts). Auth wall removed — all routes public, guest access with IP-based rate limiting. Visitor tracking added. RESEND_FROM fixed. 4 commits pushed. 2026-05-05.
type: project
originSessionId: b93bc8d3-de2c-4003-929a-85343beddbc7
---
# Session 16 (2026-05-05): LinkedIn Launch + Auth Wall Removal + Guest Access

## LinkedIn Launch Posts

### Post 1 (DELETED — login was broken)
- **Post ID**: `urn:li:share:7457367951164461056`
- **Time**: ~3:22 PM IST, Monday (suboptimal)
- **Result**: User deleted it because login/signup was broken ("Database error saving new user")
- **Root causes**: (1) `.env.production` had trailing `\n` in NEXT_PUBLIC_SITE_URL, (2) SITE_URL still pointed to vercel.app not neuralquant.co, (3) RESEND_FROM used unverified neuralquant.ai domain, (4) Supabase redirect URLs likely missing neuralquant.co

### Post 2 (LIVE — after fixes)
- **Post ID**: `urn:li:share:7457393947758469120`
- **Time**: ~8:50 PM IST, Monday
- **Comment text**: "Try it free → https://neuralquant.co / Ask AI anything about any stock → neuralquant.co/ask / Watch 7 agents debate your stock → neuralquant.co/query / No signup needed. US + India markets."

## Auth Wall Removal — Complete

### Why
User reported login/signup broken ("Database error saving new user" + "neuralquant.co domain not verified" for Resend). Decision: remove auth wall entirely for launch, let users use app without login, track via IP.

### Frontend Changes

1. **`middleware.ts`** — Removed `PROTECTED` routes array and auth redirect entirely. Middleware still refreshes Supabase session cookies for logged-in users but never blocks unauthenticated visitors. All routes now public.

2. **`page.tsx` (landing)** — "Get started free" → `/dashboard` (was `/signup`). Removed auth redirect for logged-in users. Removed `dynamic = "force-dynamic"` and `createClient` import (no longer needed). All pricing CTAs updated from `/signup` to `/dashboard`.

3. **`dashboard/page.tsx`** — Removed auth check before Ask AI queries. Previously checked `supabase.auth.getSession()` and showed "Sign in required" message. Now sends query directly — backend handles optional auth.

### Backend Changes

4. **`rate_limit.py`** — Added `enforce_guest_quota(endpoint)` dependency. Works like `enforce_tier_quota` but:
   - Authed users: normal tier limits
   - Anonymous users: free-tier limits tracked by SHA-256 hash of client IP (prefix `guest_`)
   - Uses `_ip_to_guest_id(request)` to create stable guest identifier from `x-forwarded-for` header

5. **`screener.py`** — Changed POST `/screener` from `enforce_tier_quota("screener")` to `enforce_guest_quota("screener")`. Type changed from `User` to `User | None`.

6. **`backtest.py`** — Changed POST `/backtest` from `enforce_tier_quota("backtest")` to `enforce_guest_quota("backtest")`. Type changed from `User` to `User | None`.

7. **`notify.py`** — Fixed `RESEND_FROM` default from `"NeuralQuant <alerts@neuralquant.ai>"` (unverified domain) to `"NeuralQuant <alerts@neuralquant.co>"`.

8. **`main.py`** — Added IP-based visitor tracking middleware:
   - `_visitor_store: dict[str, set[str]]` — in-memory, keyed by date string, values are sets of IP hashes
   - Logs unique IP hashes per day (SHA-256, first 16 chars)
   - Prunes dates older than 7 days
   - Skips health checks, docs, webhooks
   - New endpoint: `GET /stats/visitors` returns `{date: unique_count}` dict

9. **`.env.production`** — Fixed `NEXT_PUBLIC_SITE_URL` from `"https://neuralquant.vercel.app\n"` to `"https://neuralquant.co"` (removed trailing `\n`, updated domain). Fixed `NEXT_PUBLIC_API_URL` removed trailing `\n`.

10. **`referral.ts`**, **`sitemap.ts`** — Updated fallback from `neuralquant.vercel.app` to `neuralquant.co`. Added `.trim()` to env var reads as safety against whitespace.

11. **`config.py`** — Updated `FRONTEND_URL` default from `neuralquant.vercel.app` to `neuralquant.co`.

## Commits Pushed (Session 16)

| Commit | Description |
|--------|-------------|
| `3610604` | fix: update all URLs from vercel.app to neuralquant.co, trim env var whitespace |
| `607f8d1` | feat: remove auth wall, enable guest access, add visitor tracking |

## Vercel Deployment

- GitHub API showed stale deployment (sha `1314cd7` from May 4)
- Manually triggered `npx vercel --prod` to deploy `607f8d1`
- Verified: `curl https://www.neuralquant.co/` shows `href="/dashboard"` (not `/signup`)
- Dashboard accessible without auth (200, no redirect)

## Render Upgrade

User upgraded to Render Pro plan (no more 512MB OOM risk). Should handle 100 concurrent users for PARA-DEBATE now.

## Routes That Still Require Auth (user-specific data)

- `/watchlist` — personal watchlist CRUD
- `/alerts` — alert subscriptions/deliveries
- `/checkout` — PayPal subscription
- `/referrals` — referral code
- `/broker` — broker account/positions
- `/account` — account settings
- `/team` — team tasks/standups
- `/market-wrap` — broadcast

## Routes Now Public (guest access)

- `/dashboard` — market overview + Ask AI
- `/stocks/{ticker}` — stock scores, charts, meta
- `/screener` — preview (cache) + full (with IP rate limit)
- `/query/v2` + `/query/v2/stream` — Ask AI
- `/analyst` + `/analyst/stream` — PARA-DEBATE
- `/backtest` — with IP rate limit
- `/market/*` — overview, news, sectors, movers
- `/sentiment/*` — news sentiment, social buzz
- `/pricing`, `/compare`, `/sources`, `/best-stocks/*`

## Supabase Dashboard Changes (Manual by User)

1. Authentication → URL Configuration → Site URL: `https://neuralquant.co`
2. Authentication → URL Configuration → Redirect URLs: added `https://neuralquant.co/auth/callback`
3. Vercel dashboard: `NEXT_PUBLIC_SITE_URL=https://neuralquant.co`, `NEXT_PUBLIC_API_URL=https://neuralquant.onrender.com`

## Next Steps

1. Monitor LinkedIn post engagement (Golden Hour critical)
2. Prepare follow-up posts for launch week
3. PayPal sandbox → live mode
4. Run 3-year backtest and publish (expert's #2 critical gap)
5. Antler India/Sydney pre-seed application
6. Create LinkedIn company page