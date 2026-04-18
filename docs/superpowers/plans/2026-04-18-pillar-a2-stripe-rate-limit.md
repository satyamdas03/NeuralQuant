# Pillar A2 Implementation Plan — Stripe Checkout + Rate Limiting

> **For agentic workers:** use superpowers:executing-plans. Checkbox syntax tracks progress.

**Goal:** Monetise NeuralQuant via Stripe Checkout (US + India accept-international) and enforce per-tier quotas on API endpoints.

**Architecture:** Stripe Checkout Sessions → webhook `/billing/webhook` writes `tier` into `public.users` → FastAPI dep `enforce_tier_quota` reads tier + increments `public.usage_log` → returns 429 when daily cap hit.

**Tech Stack:** stripe-python, FastAPI dependency injection, Supabase row updates via service-role client.

**Tier → Price mapping** (set in Stripe Dashboard, store lookup_key → tier):

| Tier | Price (USD/mo) | stripe lookup_key |
|---|---|---|
| investor | 19 | `nq_investor_monthly` |
| pro | 49 | `nq_pro_monthly` |
| api | 99 | `nq_api_monthly` |

---

## File Map

| File | Change |
|---|---|
| `apps/api/pyproject.toml` | add `stripe>=11.0` |
| `apps/api/src/nq_api/billing/__init__.py` | NEW |
| `apps/api/src/nq_api/billing/stripe_client.py` | NEW — singleton client |
| `apps/api/src/nq_api/billing/webhook.py` | NEW — signature verify + event handlers |
| `apps/api/src/nq_api/routes/billing.py` | NEW — POST /billing/checkout, POST /billing/portal, POST /billing/webhook |
| `apps/api/src/nq_api/auth/rate_limit.py` | NEW — `enforce_tier_quota` dep |
| `apps/api/src/nq_api/routes/query.py` | wire `Depends(enforce_tier_quota("query"))` |
| `apps/api/src/nq_api/routes/analyst.py` | same |
| `apps/api/src/nq_api/routes/screener.py` | same (uses `screener_refresh_seconds` as cache key) |
| `apps/web/src/app/pricing/page.tsx` | NEW — 4 plan cards, Checkout CTA |
| `apps/web/src/app/account/page.tsx` | NEW — current tier, Manage Subscription (Stripe Portal) |
| `sql/002_stripe_events.sql` | NEW — `public.stripe_events(id, type, received_at, payload)` for idempotency |
| `.env.example` | add STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_*, NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY |
| `apps/web/src/app/account/page.tsx` | account page |

---

## Task 1: SQL for idempotency

- [ ] **Step 1:** Write `sql/002_stripe_events.sql`:

```sql
CREATE TABLE IF NOT EXISTS public.stripe_events (
  id TEXT PRIMARY KEY,              -- Stripe event id (evt_...)
  type TEXT NOT NULL,
  received_at TIMESTAMPTZ DEFAULT now(),
  payload JSONB NOT NULL
);
ALTER TABLE public.stripe_events ENABLE ROW LEVEL SECURITY;
-- no public policies — service_role only
```

- [ ] **Step 2:** Run via Supabase SQL Editor.

## Task 2: Add `stripe` dep + env plumbing

- [ ] Add `stripe>=11.0` to `apps/api/pyproject.toml`, `uv sync`.
- [ ] Append to `.env.example`:
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_INVESTOR=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_API=price_...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Task 3: Stripe client singleton

- [ ] Create `apps/api/src/nq_api/billing/stripe_client.py`:
```python
import os, stripe
def get_stripe() -> "stripe":
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    return stripe
```

## Task 4: Checkout endpoint

- [ ] `POST /billing/checkout` — auth required. Body: `{"tier": "investor|pro|api"}`.
  - Look up price from env `STRIPE_PRICE_<TIER>`.
  - Create/reuse `stripe_customer_id` on `public.users` (creates Customer if missing).
  - `stripe.checkout.Session.create(mode="subscription", customer=..., line_items=[{price, qty:1}], success_url=APP_URL+"/account?upgraded=1", cancel_url=APP_URL+"/pricing")`.
  - Return `{"url": session.url}`.

## Task 5: Portal endpoint

- [ ] `POST /billing/portal` — auth required. `stripe.billing_portal.Session.create(customer=user.stripe_customer_id, return_url=APP_URL+"/account")`. Return `{"url": session.url}`.

## Task 6: Webhook

- [ ] `POST /billing/webhook` — no auth, raw body.
  - `event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)`.
  - Upsert into `public.stripe_events` on PK — if conflict, return 200 (idempotent).
  - Handle:
    - `checkout.session.completed` → on completed subscription, fetch `subscription.items.price.lookup_key` → map to tier → update `users.tier`, `stripe_subscription_id`, `subscription_status`.
    - `customer.subscription.updated` → sync `subscription_status` (active/past_due/canceled), reset `tier='free'` on cancel.
    - `customer.subscription.deleted` → `tier='free'`.
  - Return 200.

## Task 7: Rate limiter dep

- [ ] `apps/api/src/nq_api/auth/rate_limit.py`:
```python
from fastapi import Depends, HTTPException
from .deps import get_current_user
from .models import User, TIER_LIMITS
def enforce_tier_quota(endpoint: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        # count today's usage_log rows for (user.id, endpoint)
        # if >= TIER_LIMITS[user.tier].<queries|backtest>_per_day: raise 429
        # else insert usage_log row, return user
        ...
    return dep
```
- [ ] Write 4 tests: under-cap passes, at-cap 429, wrong-endpoint isolated, api-tier unlimited.

## Task 8: Wire quota deps on expensive routes

- [ ] `/query` → `enforce_tier_quota("query")`.
- [ ] `/analyst` → `enforce_tier_quota("analyst")`.
- [ ] `/backtest` (comes in Pillar D) → `enforce_tier_quota("backtest")`.
- [ ] `/screener` → pass through cache TTL from `TIER_LIMITS.screener_refresh_seconds`.

## Task 9: Frontend pricing page

- [ ] `apps/web/src/app/pricing/page.tsx` — 4 tier cards. Clicking a paid tier hits `POST /billing/checkout`, then `window.location = data.url`. Free tier → `/signup`.

## Task 10: Account page

- [ ] `apps/web/src/app/account/page.tsx` — show `authedApi.me()` result (tier, limits). "Manage subscription" button → `POST /billing/portal` → redirect to `data.url`.

## Task 11: Webhook endpoint whitelisted for CORS + proxy

- [ ] Stripe posts raw; exclude `/billing/webhook` from CORS auth headers — FastAPI CORSMiddleware default is fine since Stripe sends no `Origin`.
- [ ] Render: add public endpoint, ensure POST body size limit ≥ 1MB.

## Task 12: Smoke test

- [ ] Stripe CLI: `stripe listen --forward-to localhost:8000/billing/webhook`.
- [ ] Trigger checkout via pricing page with 4242 test card.
- [ ] Verify `users.tier` updates to `investor`.
- [ ] Hit `/query` 11 times on `free` → expect 429 on 11th.
- [ ] Commit + push.

## Risks

- **Webhook signature drift** if `STRIPE_WEBHOOK_SECRET` not set → reject all events. Fail loud in prod.
- **Idempotency** enforced via `stripe_events` PK; Stripe retries 3x.
- **Tier downgrade race** — if user cancels mid-request, next request sees `free`. Acceptable.
- **India GST/OIDAR:** Stripe India requires OIDAR registration above ₹20L/yr. Defer until GMV near threshold; show tax-inclusive pricing via Stripe Tax once enabled.

## Success metrics

- Checkout success rate > 95% in Stripe dashboard
- p95 webhook latency < 500ms
- Zero `users.tier` drift between Stripe status and DB after 24h
- Free-tier user hits rate limit at exactly quota, tier upgrade restores access
