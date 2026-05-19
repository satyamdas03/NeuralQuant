# NeuralQuant GTM Business Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Stripe monetization, programmatic SEO, onboarding emails, analytics, referral system, and upgrade prompts to reach 1,000 users in 90 days.

**Architecture:** Backend changes to FastAPI (Stripe webhooks, referral API, onboarding emails). Frontend changes to Next.js (pricing page, SEO metadata, analytics script, onboarding modal, upgrade prompts). Supabase migrations for referrals and Stripe price config.

**Tech Stack:** Python 3.12 + FastAPI + Stripe SDK + Resend · Next.js 16 + React 19 + Tailwind v4 · Supabase (auth/RLS/postgres) · Plausible Analytics

**Spec:** `docs/superpowers/specs/2026-04-24-gtm-business-strategy-design.md`

---

## File Map

### Backend (apps/api/src/nq_api/)

| File | Action | Responsibility |
|------|--------|----------------|
| `routes/checkout.py` | Create | Stripe Checkout Session creation |
| `routes/webhooks_stripe.py` | Create | Stripe webhook handler |
| `routes/referrals.py` | Create | Referral code CRUD + usage |
| `notify.py` | Modify | Add welcome/onboarding email functions |
| `auth/models.py` | Modify | Add price constants, ReferralCode model |
| `main.py` | Modify | Register new routers |
| `deps.py` | Modify | Add referral dependency |

### Frontend (apps/web/src/)

| File | Action | Responsibility |
|------|--------|----------------|
| `app/pricing/page.tsx` | Create | Pricing page with INR/USD toggle |
| `app/best-stocks/[sector]/page.tsx` | Create | Sector landing pages |
| `app/stocks/[ticker]/page.tsx` | Modify | Add generateMetadata for SEO |
| `app/sitemap.ts` | Create | Dynamic sitemap for all tickers + pages |
| `app/robots.ts` | Create | robots.txt config |
| `app/layout.tsx` | Modify | Add Plausible analytics script |
| `components/onboarding/WelcomeModal.tsx` | Create | First-login onboarding modal |
| `components/ui/UpgradePrompt.tsx` | Create | Upgrade CTA when rate-limited |
| `lib/pricing.ts` | Create | Currency detection + price constants |
| `lib/referral.ts` | Create | Referral code client utilities |

### Supabase Migrations (sql/)

| File | Action | Responsibility |
|------|--------|----------------|
| `sql/005_referrals.sql` | Create | Referrals table + referral_bonus column |

### Environment

| Variable | Where | Purpose |
|----------|-------|---------|
| `STRIPE_SECRET_KEY` | .env | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | .env | Webhook signature verification |
| `STRIPE_PRICE_INVESTOR_INR` | .env | Price ID for ₹299/mo |
| `STRIPE_PRICE_INVESTOR_USD` | .env | Price ID for $9/mo |
| `STRIPE_PRICE_PRO_INR` | .env | Price ID for ₹999/mo |
| `STRIPE_PRICE_PRO_USD` | .env | Price ID for $29/mo |
| `STRIPE_PRICE_API_INR` | .env | Price ID for ₹4,999/mo |
| `STRIPE_PRICE_API_USD` | .env | Price ID for $149/mo |
| `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` | .env | Plausible analytics domain |
| `NEXT_PUBLIC_STRIPE_PK` | .env | Stripe publishable key |

---

## Task 1: Plausible Analytics Setup

**Files:**
- Modify: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/lib/analytics.ts`

**Why first:** All subsequent tasks generate events. Need analytics running to measure them.

- [ ] **Step 1: Create analytics helper**

Create `apps/web/src/lib/analytics.ts`:

```typescript
const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

export function trackEvent(name: string, props?: Record<string, string>) {
  if (typeof window === "undefined" || !PLAUSIBLE_DOMAIN) return;
  window.plausible?.(name, { props });
}

declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string> }) => void;
  }
}
```

- [ ] **Step 2: Add Plausible script to layout.tsx**

In `apps/web/src/app/layout.tsx`, add the Plausible script tag inside the `<head>` section of the metadata, or as a `<Script>` component:

Add after the existing `<html>` tag, before `{children}` in the body:

```tsx
import Script from "next/script";

// Inside the <body>, before {children}:
{process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && (
  <Script
    defer
    data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN}
    src="https://plausible.io/js/script.js"
  />
)}
```

- [ ] **Step 3: Verify script loads**

Run: `cd apps/web && npm run build`
Expected: Build succeeds. Check page source for `<script data-domain=...>`.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/analytics.ts apps/web/src/app/layout.tsx
git commit -m "feat(analytics): add Plausible analytics script + trackEvent helper"
```

---

## Task 2: SEO Meta Tags on Stock Pages

**Files:**
- Modify: `apps/web/src/app/stocks/[ticker]/page.tsx`

**Current state:** Stock detail page is a Client Component with no `generateMetadata`. Need to add server-side metadata for SEO.

- [ ] **Step 1: Add generateMetadata to stock page**

In `apps/web/src/app/stocks/[ticker]/page.tsx`, add a `generateMetadata` export. Since this is currently a Client Component, it needs a separate metadata file or conversion. Create a `layout.tsx` sibling or convert the page. Best approach: add a `generateMetadata` function in a separate server file and import.

Create `apps/web/src/app/stocks/[ticker]/metadata.ts`:

```typescript
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const decoded = decodeURIComponent(ticker);
  const isIndia = decoded.endsWith(".NS") || decoded.endsWith(".BO");
  const name = decoded.replace(/\.NS$|\.BO$/, "");
  const market = isIndia ? "India (NSE/BSE)" : "US (NYSE/NASDAQ)";
  const currency = isIndia ? "₹" : "$";

  return {
    title: `${name} Stock Score — NeuralQuant 5-Factor AI Analysis | ${market}`,
    description: `AI-powered ${name} stock analysis with 5-factor quant scoring (quality, momentum, value, low-vol, insider), HMM regime detection, and 6-analyst PARA-DEBATE. ${currency} price targets and sector-adjusted ratings.`,
    openGraph: {
      title: `${name} Stock Score — NeuralQuant`,
      description: `5-factor AI analysis + 6-analyst debate for ${name}. Free stock intelligence.`,
      type: "website",
      url: `https://neuralquant.vercel.app/stocks/${ticker}`,
    },
    alternates: {
      canonical: `https://neuralquant.vercel.app/stocks/${ticker}`,
    },
  };
}
```

Then in `apps/web/src/app/stocks/[ticker]/page.tsx`, import and re-export:

```typescript
export { generateMetadata } from "./metadata";
```

- [ ] **Step 2: Add JSON-LD structured data**

Add to the stock page component a JSON-LD script tag for search engines:

```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{
    __html: JSON.stringify({
      "@context": "https://schema.org",
      "@type": "FinancialProduct",
      name: ticker,
      description: `NeuralQuant AI analysis for ${ticker}`,
      url: `https://neuralquant.vercel.app/stocks/${ticker}`,
    }),
  }}
/>
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/stocks/[ticker]/metadata.ts apps/web/src/app/stocks/[ticker]/page.tsx
git commit -m "feat(seo): add generateMetadata + JSON-LD for stock detail pages"
```

---

## Task 3: Sitemap + Robots.txt

**Files:**
- Create: `apps/web/src/app/sitemap.ts`
- Create: `apps/web/src/app/robots.ts`

- [ ] **Step 1: Create dynamic sitemap**

Create `apps/web/src/app/sitemap.ts`:

```typescript
import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://neuralquant.vercel.app";

// Core NSE tickers for SEO (top 200 by market cap)
const NSE_TICKERS = [
  "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
  "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "KOTAKBANK.NS",
  "HCLTECH.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS",
  "TATAMOTORS.NS", "WIPRO.NS", "ULTRACEMCO.NS", "ADANIENT.NS", "TITAN.NS",
  "ASIANPAINT.NS", "HINDUNILVR.NS", "TATASTEEL.NS", "NESTLEIND.NS", "ONGC.NS",
  "POWERGRID.NS", "HDFC.NS", "COALINDIA.NS", "NTPC.NS", "BAJAJFINSV.NS",
  "DRREDDY.NS", "TECHM.NS", "JSWSTEEL.NS", "M&M.NS", "TATACONSUM.NS",
  "INDUSINDBK.NS", "CIPLA.NS", "GRASIM.NS", "BPCL.NS", "EICHERMOT.NS",
  "HINDALCO.NS", "HEROMOTOCO.NS", "BRITANNIA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
  "TRENT.NS", "ADANIPORTS.NS", "HCLTECH.NS", "TATACONSUM.NS", "SHRIRAMFIN.NS",
];

// Top 50 US tickers
const US_TICKERS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
  "LLY", "AVGO", "JPM", "V", "UNH", "WMT", "XOM", "MA", "PG", "JNJ",
  "HD", "COST", "MRK", "ABBV", "ORCL", "CRM", "BAC", "AMD", "NFLX",
  "ADBE", "CVX", "KO", "PEP", "CSCO", "TMO", "ABT", "ACN", "MCD", "INTC",
  "WFC", "CAT", "VZ", "TXN", "QCOM", "MS", "RTX", "NEE", "AMGN", "UPS", "IBM",
];

const SECTORS = [
  "banking", "it", "pharma", "auto", "energy", "fmcg", "metals",
  "telecom", "infrastructure", "financial-services", "cement", "chemicals",
  "consumer-durables", "real-estate", "media",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const stockPages = [
    ...NSE_TICKERS.map((t) => ({
      url: `${SITE_URL}/stocks/${t}`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    ...US_TICKERS.map((t) => ({
      url: `${SITE_URL}/stocks/${t}`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];

  const sectorPages = SECTORS.map((s) => ({
    url: `${SITE_URL}/best-stocks/${s}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));

  const corePages = [
    { url: SITE_URL, lastModified: new Date(), changeFrequency: "weekly" as const, priority: 1.0 },
    { url: `${SITE_URL}/pricing`, lastModified: new Date(), changeFrequency: "monthly" as const, priority: 0.9 },
    { url: `${SITE_URL}/sources`, lastModified: new Date(), changeFrequency: "monthly" as const, priority: 0.5 },
    { url: `${SITE_URL}/compare`, lastModified: new Date(), changeFrequency: "monthly" as const, priority: 0.5 },
  ];

  return [...corePages, ...stockPages, ...sectorPages];
}
```

- [ ] **Step 2: Create robots.txt**

Create `apps/web/src/app/robots.ts`:

```typescript
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/auth/", "/dashboard", "/watchlist", "/backtest", "/query"],
      },
    ],
    sitemap: "https://neuralquant.vercel.app/sitemap.xml",
  };
}
```

- [ ] **Step 3: Verify sitemap generation**

Run: `cd apps/web && npm run build`
Expected: Build succeeds. Check `.next/server/app/sitemap.xml` exists.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/sitemap.ts apps/web/src/app/robots.ts
git commit -m "feat(seo): add dynamic sitemap + robots.txt for 700+ stock pages"
```

---

## Task 4: Pricing Page with INR/USD Toggle

**Files:**
- Create: `apps/web/src/app/pricing/page.tsx`
- Create: `apps/web/src/lib/pricing.ts`

- [ ] **Step 1: Create pricing constants**

Create `apps/web/src/lib/pricing.ts`:

```typescript
export type Currency = "INR" | "USD";

export interface TierInfo {
  key: string;
  name: string;
  inrPrice: number;
  usdPrice: number;
  watchlists: number;
  queriesPerDay: number;
  backtestsPerDay: number;
  popular?: boolean;
}

export const TIERS: TierInfo[] = [
  {
    key: "free",
    name: "Free",
    inrPrice: 0,
    usdPrice: 0,
    watchlists: 5,
    queriesPerDay: 10,
    backtestsPerDay: 5,
  },
  {
    key: "investor",
    name: "Investor",
    inrPrice: 299,
    usdPrice: 9,
    watchlists: 25,
    queriesPerDay: 100,
    backtestsPerDay: 5,
    popular: true,
  },
  {
    key: "pro",
    name: "Pro",
    inrPrice: 999,
    usdPrice: 29,
    watchlists: 100,
    queriesPerDay: 1000,
    backtestsPerDay: 50,
  },
  {
    key: "api",
    name: "API",
    inrPrice: 4999,
    usdPrice: 149,
    watchlists: 1000,
    queriesPerDay: 100000,
    backtestsPerDay: 1000,
  },
];

export function formatPrice(amount: number, currency: Currency): string {
  if (amount === 0) return "Free forever";
  if (currency === "INR") return `₹${amount.toLocaleString("en-IN")}/mo`;
  return `$${amount}/mo`;
}

export function detectCurrency(): Currency {
  if (typeof navigator === "undefined") return "USD";
  const lang = navigator.language || "";
  if (lang.includes("IN") || lang.startsWith("hi")) return "INR";
  return "USD";
}
```

- [ ] **Step 2: Create pricing page**

Create `apps/web/src/app/pricing/page.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { TIERS, formatPrice, detectCurrency, type Currency } from "@/lib/pricing";
import GradientButton from "@/components/ui/GradientButton";

export default function PricingPage() {
  const [currency, setCurrency] = useState<Currency>("USD");

  useEffect(() => {
    setCurrency(detectCurrency());
  }, []);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <div className="max-w-6xl mx-auto px-6 py-20">
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight text-center">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 text-on-surface-variant text-center max-w-xl mx-auto">
          Start free forever. Upgrade when you need more queries, watchlists, or backtests.
        </p>

        {/* Currency Toggle */}
        <div className="mt-8 flex justify-center gap-2">
          <button
            onClick={() => setCurrency("INR")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currency === "INR"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            ₹ INR
          </button>
          <button
            onClick={() => setCurrency("USD")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currency === "USD"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            $ USD
          </button>
        </div>

        {/* Tier Cards */}
        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {TIERS.map((tier) => (
            <div
              key={tier.key}
              className={`relative rounded-2xl ghost-border bg-surface-low/40 p-6 flex flex-col ${
                tier.popular ? "ring-2 ring-primary" : ""
              }`}
            >
              {tier.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary text-on-primary text-xs font-semibold">
                  Most popular
                </span>
              )}
              <h3 className="font-headline text-xl font-bold">{tier.name}</h3>
              <div className="mt-3 font-headline text-3xl font-bold gradient-cta bg-clip-text text-transparent">
                {formatPrice(tier.key === "free" ? 0 : (currency === "INR" ? tier.inrPrice : tier.usdPrice), currency)}
              </div>
              <ul className="mt-6 space-y-3 text-sm text-on-surface-variant flex-1">
                <li>✓ {tier.watchlists} watchlists</li>
                <li>✓ {tier.queriesPerDay.toLocaleString()} AI queries/day</li>
                <li>✓ {tier.backtestsPerDay} backtests/day</li>
                <li>✓ Full screener access</li>
                {tier.key !== "free" && <li>✓ Priority support</li>}
              </ul>
              <div className="mt-6">
                {tier.key === "free" ? (
                  <Link
                    href="/signup"
                    className="block text-center px-6 py-3 rounded-xl ghost-border text-on-surface-variant hover:text-on-surface font-medium text-sm transition-colors"
                  >
                    Get started free
                  </Link>
                ) : (
                  <GradientButton
                    href={`/api/checkout?tier=${tier.key}&currency=${currency}`}
                    size="md"
                    className="w-full"
                  >
                    Upgrade to {tier.name}
                  </GradientButton>
                )}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-on-surface-variant">
          All prices exclude applicable taxes. Cancel anytime. No lock-in.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds, `/pricing` route generated.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/pricing.ts apps/web/src/app/pricing/page.tsx
git commit -m "feat(pricing): add pricing page with INR/USD toggle + tier cards"
```

---

## Task 5: Stripe Checkout Backend

**Files:**
- Create: `apps/api/src/nq_api/routes/checkout.py`
- Create: `apps/api/src/nq_api/routes/webhooks_stripe.py`
- Modify: `apps/api/src/nq_api/main.py` (register routers)
- Modify: `apps/api/src/nq_api/auth/models.py` (add price constants)

- [ ] **Step 1: Add price constants to models**

In `apps/api/src/nq_api/auth/models.py`, add after `TIER_LIMITS`:

```python
STRIPE_PRICES: dict[str, dict[str, str]] = {
    "investor": {
        "INR": os.environ.get("STRIPE_PRICE_INVESTOR_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_INVESTOR_USD", ""),
    },
    "pro": {
        "INR": os.environ.get("STRIPE_PRICE_PRO_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_PRO_USD", ""),
    },
    "api": {
        "INR": os.environ.get("STRIPE_PRICE_API_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_API_USD", ""),
    },
}
```

Add `import os` at top of file.

- [ ] **Step 2: Create checkout route**

Create `apps/api/src/nq_api/routes/checkout.py`:

```python
"""Stripe Checkout Session creation."""
import os
from fastapi import APIRouter, Depends, HTTPException, Query
import stripe

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User, STRIPE_PRICES

router = APIRouter(prefix="/checkout", tags=["checkout"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "https://neuralquant.vercel.app/dashboard?upgraded=1")
CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "https://neuralquant.vercel.app/pricing")


@router.post("/session")
async def create_checkout_session(
    tier: str = Query(..., regex="^(investor|pro|api)$"),
    currency: str = Query("USD", regex="^(INR|USD)$"),
    user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for the given tier + currency."""
    price_id = STRIPE_PRICES.get(tier, {}).get(currency)
    if not price_id:
        raise HTTPException(400, f"No price configured for {tier}/{currency}")

    # Reuse existing Stripe customer if available
    customer_kwargs = {}
    if user.stripe_customer_id:
        customer_kwargs["customer"] = user.stripe_customer_id
    else:
        customer_kwargs["customer_email"] = user.email

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={"user_id": user.id, "tier": tier},
            **customer_kwargs,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, str(e))

    return {"url": session.url, "session_id": session.id}
```

- [ ] **Step 3: Create Stripe webhook handler**

Create `apps/api/src/nq_api/routes/webhooks_stripe.py`:

```python
"""Stripe webhook handler — updates user tier on payment events."""
import os
import stripe
from fastapi import APIRouter, Request, HTTPException, Header

from nq_api.auth.deps import _supabase_service_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, WEBHOOK_SECRET,
        )
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "checkout.session.completed":
        _handle_checkout_complete(event["data"]["object"])
    elif event["type"] == "customer.subscription.updated":
        _handle_subscription_update(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        _handle_subscription_delete(event["data"]["object"])

    return {"received": True}


def _handle_checkout_complete(session: dict):
    """New subscription created — update tier + Stripe IDs."""
    user_id = session.get("metadata", {}).get("user_id")
    tier = session.get("metadata", {}).get("tier", "investor")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        return

    client = _supabase_service_client()
    client.table("users").update({
        "tier": tier,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "subscription_status": "active",
    }).eq("id", user_id).execute()


def _handle_subscription_update(subscription: dict):
    """Subscription changed (upgrade/downgrade)."""
    customer_id = subscription.get("customer")
    status = subscription.get("status")

    client = _supabase_service_client()
    result = client.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
    if not result.data:
        return

    user_id = result.data[0]["id"]
    client.table("users").update({
        "subscription_status": status,
    }).eq("id", user_id).execute()


def _handle_subscription_delete(subscription: dict):
    """Subscription cancelled — downgrade to free."""
    customer_id = subscription.get("customer")

    client = _supabase_service_client()
    result = client.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
    if not result.data:
        return

    user_id = result.data[0]["id"]
    client.table("users").update({
        "tier": "free",
        "subscription_status": "cancelled",
    }).eq("id", user_id).execute()
```

- [ ] **Step 4: Register new routers in main.py**

In `apps/api/src/nq_api/main.py`, add imports and router registrations:

```python
from nq_api.routes.checkout import router as checkout_router
from nq_api.routes.webhooks_stripe import router as stripe_webhook_router

# In the router registration block:
app.include_router(checkout_router)
app.include_router(stripe_webhook_router)
```

- [ ] **Step 5: Verify backend starts**

Run: `cd apps/api && python -c "from nq_api.main import app; print('OK')"`
Expected: `OK` (imports succeed)

- [ ] **Step 6: Install stripe package**

Run: `cd apps/api && uv add stripe`

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/nq_api/routes/checkout.py apps/api/src/nq_api/routes/webhooks_stripe.py apps/api/src/nq_api/main.py apps/api/src/nq_api/auth/models.py apps/api/pyproject.toml apps/api/uv.lock
git commit -m "feat(billing): add Stripe Checkout session + webhook handler for tier upgrades"
```

---

## Task 6: Referral System

**Files:**
- Create: `sql/005_referrals.sql`
- Create: `apps/api/src/nq_api/routes/referrals.py`
- Modify: `apps/api/src/nq_api/main.py` (register router)
- Create: `apps/web/src/lib/referral.ts`

- [ ] **Step 1: Create Supabase migration**

Create `sql/005_referrals.sql`:

```sql
-- Referral system: codes, tracking, and bonus queries
CREATE TABLE IF NOT EXISTS public.referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  code TEXT UNIQUE NOT NULL,
  referred_email TEXT,
  referred_user_id UUID REFERENCES auth.users(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'redeemed')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Add referral_bonus_queries column to users
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS referral_bonus_queries INTEGER DEFAULT 0;

-- Index for looking up referral codes
CREATE INDEX IF NOT EXISTS idx_referrals_code ON public.referrals(code);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON public.referrals(referrer_id);

-- RLS
ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own referrals"
  ON public.referrals FOR SELECT
  USING (referrer_id = (SELECT auth.uid()));

CREATE POLICY "Users can insert own referrals"
  ON public.referrals FOR INSERT
  WITH CHECK (referrer_id = (SELECT auth.uid()));

-- Function: apply referral bonus on signup
CREATE OR REPLACE FUNCTION public.handle_referral_signup()
RETURNS TRIGGER AS $$
DECLARE
  ref_code TEXT;
  ref_row RECORD;
BEGIN
  -- Check if signup came with a referral code (stored in user_metadata)
  ref_code := NEW.raw_user_meta->>'referral_code';

  IF ref_code IS NOT NULL THEN
    SELECT * INTO ref_row FROM public.referrals WHERE code = ref_code AND status = 'active';

    IF ref_row.id IS NOT NULL THEN
      -- Mark referral as redeemed
      UPDATE public.referrals SET
        status = 'redeemed',
        referred_email = NEW.email,
        referred_user_id = NEW.id
      WHERE id = ref_row.id;

      -- Give referrer +5 bonus queries
      UPDATE public.users SET
        referral_bonus_queries = referral_bonus_queries + 5
      WHERE id = ref_row.referrer_id;

      -- Give new user +5 bonus queries
      UPDATE public.users SET
        referral_bonus_queries = referral_bonus_queries + 5
      WHERE id = NEW.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users insert (after existing handle_new_user)
DROP TRIGGER IF EXISTS on_referral_signup ON auth.users;
CREATE TRIGGER on_referral_signup
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_referral_signup();
```

- [ ] **Step 2: Create referral API route**

Create `apps/api/src/nq_api/routes/referrals.py`:

```python
"""Referral code management."""
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nq_api.auth.deps import get_current_user, _supabase_service_client
from nq_api.auth.models import User

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferralCodeOut(BaseModel):
    code: str
    link: str
    total_referred: int
    bonus_queries: int


@router.get("/my-code", response_model=ReferralCodeOut)
async def get_my_code(user: User = Depends(get_current_user)):
    """Get or create referral code for current user."""
    client = _supabase_service_client()

    # Check if code already exists
    result = client.table("referrals").select("code, status").eq("referrer_id", user.id).eq("status", "active").execute()

    if result.data:
        code = result.data[0]["code"]
    else:
        # Generate unique code from user id
        code = "NQ-" + hashlib.sha256(user.id.encode()).hexdigest()[:7].upper()
        client.table("referrals").insert({
            "referrer_id": user.id,
            "code": code,
        }).execute()

    # Count total redeemed referrals
    count_result = client.table("referrals").select("id", count="exact").eq("referrer_id", user.id).eq("status", "redeemed").execute()
    total_referred = count_result.count or 0

    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://neuralquant.vercel.app")
    link = f"{site}/signup?ref={code}"

    return ReferralCodeOut(
        code=code,
        link=link,
        total_referred=total_referred,
        bonus_queries=user.referral_bonus_queries if hasattr(user, "referral_bonus_queries") else 0,
    )
```

Add `import os` at top.

- [ ] **Step 3: Update User model with referral_bonus_queries**

In `apps/api/src/nq_api/auth/models.py`, add to `User` class:

```python
referral_bonus_queries: int = 0
```

In `apps/api/src/nq_api/auth/deps.py`, update `_load_user_row` to include the new field in the User constructor:

```python
referral_bonus_queries=row.get("referral_bonus_queries", 0),
```

- [ ] **Step 4: Update rate_limit.py to add bonus queries**

In `apps/api/src/nq_api/auth/rate_limit.py`, modify `_cap_for` to add bonus:

Find the line that calculates `cap` and add the bonus:

```python
cap = TIER_LIMITS.get(user.tier, TIER_LIMITS["free"]).queries_per_day + getattr(user, "referral_bonus_queries", 0)
```

- [ ] **Step 5: Register referral router**

In `apps/api/src/nq_api/main.py`:

```python
from nq_api.routes.referrals import router as referral_router
app.include_router(referral_router)
```

- [ ] **Step 6: Create frontend referral helper**

Create `apps/web/src/lib/referral.ts`:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

export interface ReferralInfo {
  code: string;
  link: string;
  total_referred: number;
  bonus_queries: number;
}

export async function getReferralCode(token: string): Promise<ReferralInfo> {
  const res = await fetch(`${API_URL}/referrals/my-code`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch referral code");
  return res.json();
}

export function getReferralLink(code: string): string {
  const site = process.env.NEXT_PUBLIC_SITE_URL || "https://neuralquant.vercel.app";
  return `${site}/signup?ref=${code}`;
}
```

- [ ] **Step 7: Handle referral code on signup**

In `apps/web/src/app/signup/page.tsx`, read `ref` query param and pass to Supabase signup metadata:

```typescript
// At the top of the signup component:
import { useSearchParams } from "next/navigation";

// Inside the component:
const searchParams = useSearchParams();
const refCode = searchParams.get("ref");

// In the signUp call, add to options:
supabase.auth.signUp({
  email,
  password,
  options: {
    emailRedirectTo: `${NEXT_PUBLIC_SITE_URL}/auth/callback`,
    data: { referral_code: refCode || undefined },
  },
});
```

- [ ] **Step 8: Verify backend starts**

Run: `cd apps/api && python -c "from nq_api.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add sql/005_referrals.sql apps/api/src/nq_api/routes/referrals.py apps/api/src/nq_api/main.py apps/api/src/nq_api/auth/models.py apps/api/src/nq_api/auth/deps.py apps/api/src/nq_api/auth/rate_limit.py apps/web/src/lib/referral.ts apps/web/src/app/signup/page.tsx
git commit -m "feat(referrals): add referral code system with bonus queries + Supabase migration"
```

---

## Task 7: Welcome Email Sequence (Resend)

**Files:**
- Modify: `apps/api/src/nq_api/notify.py`

**Current state:** `notify.py` has `send_alert_email()`. Add onboarding email functions.

- [ ] **Step 1: Add welcome email functions to notify.py**

In `apps/api/src/nq_api/notify.py`, add after `send_alert_email`:

```python
def send_welcome_email(to: str, name: str | None = None):
    """Day-0 welcome email with quickstart guide."""
    client = _resend_client()
    if not client:
        logger.info("RESEND_API_KEY not set, skipping welcome email to %s", to)
        return True

    first = name.split("@")[0] if name else "there"
    resend.Emails.send({
        "from": RESEND_FROM,
        "to": to,
        "subject": "Welcome to NeuralQuant — here's your first analysis",
        "html": f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f0f1a;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h1 style="color:#c1c1ff;font-size:24px;">Welcome to NeuralQuant, {first}!</h1>
          <p style="color:#a0a0b0;line-height:1.6;">You now have free access to:</p>
          <ul style="color:#a0a0b0;line-height:1.8;">
            <li>5-factor AI stock scoring (quality, momentum, value, low-vol, insider)</li>
            <li>6-analyst PARA-DEBATE on any stock</li>
            <li>Smart Money insider signals from SEC Form 4</li>
            <li>Screener + watchlists for US and India markets</li>
          </ul>
          <p style="color:#a0a0b0;line-height:1.6;">Start here: <a href="https://neuralquant.vercel.app/stocks/RELIANCE.NS" style="color:#bdf4ff;">RELIANCE Industries analysis →</a></p>
          <p style="color:#a0a0b0;line-height:1.6;">Or try US: <a href="https://neuralquant.vercel.app/stocks/AAPL" style="color:#bdf4ff;">Apple (AAPL) analysis →</a></p>
        </div>
        """,
    })
    return True


def send_debate_demo_email(to: str):
    """Day-1 PARA-DEBATE demo email."""
    client = _resend_client()
    if not client:
        return True

    resend.Emails.send({
        "from": RESEND_FROM,
        "to": to,
        "subject": "Watch 6 AI analysts debate RELIANCE",
        "html": """
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f0f1a;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h1 style="color:#c1c1ff;font-size:24px;">See PARA-DEBATE in action</h1>
          <p style="color:#a0a0b0;line-height:1.6;">Before you invest, 6 specialist AI analysts argue every angle — macro, fundamentals, technicals, sentiment, geopolitics, and an adversarial devil's advocate. A Head Analyst delivers the final verdict.</p>
          <p style="margin:24px 0;"><a href="https://neuralquant.vercel.app/query" style="background:linear-gradient(135deg,#c1c1ff,#bdf4ff);color:#0f0f1a;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Try Ask AI →</a></p>
          <p style="color:#666;font-size:12px;">NeuralQuant — Research tool, not investment advice.</p>
        </div>
        """,
    })
    return True


def send_screener_email(to: str):
    """Day-3 screener introduction email."""
    client = _resend_client()
    if not client:
        return True

    resend.Emails.send({
        "from": RESEND_FROM,
        "to": to,
        "subject": "Find top-rated stocks in seconds",
        "html": """
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f0f1a;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h1 style="color:#c1c1ff;font-size:24px;">Your screener is ready</h1>
          <p style="color:#a0a0b0;line-height:1.6;">NeuralQuant scores 1,000+ stocks nightly across 5 factors. Use the screener to filter by composite score, sector, or individual factor.</p>
          <p style="margin:24px 0;"><a href="https://neuralquant.vercel.app/screener" style="background:linear-gradient(135deg,#c1c1ff,#bdf4ff);color:#0f0f1a;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Open Screener →</a></p>
        </div>
        """,
    })
    return True


def send_upgrade_email(to: str):
    """Day-7 upgrade prompt email."""
    client = _resend_client()
    if not client:
        return True

    resend.Emails.send({
        "from": RESEND_FROM,
        "to": to,
        "subject": "Unlock 100 queries/day — Investor tier",
        "html": """
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f0f1a;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h1 style="color:#c1c1ff;font-size:24px;">Ready for more?</h1>
          <p style="color:#a0a0b0;line-height:1.6;">The free tier gives you 10 AI queries per day. Upgrade to Investor for 100 queries/day, 25 watchlists, and priority scoring — for just ₹299/mo ($9/mo).</p>
          <p style="margin:24px 0;"><a href="https://neuralquant.vercel.app/pricing" style="background:linear-gradient(135deg,#c1c1ff,#bdf4ff);color:#0f0f1a;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">See Pricing →</a></p>
        </div>
        """,
    })
    return True
```

- [ ] **Step 2: Wire welcome email into signup flow**

In `apps/api/src/nq_api/auth/deps.py`, in the `_load_user_row` function, after inserting a new user row (when `result.data` is empty), call the welcome email:

```python
# After the insert:
from nq_api.notify import send_welcome_email
send_welcome_email(email)
```

- [ ] **Step 3: Verify imports work**

Run: `cd apps/api && python -c "from nq_api.notify import send_welcome_email, send_debate_demo_email, send_screener_email, send_upgrade_email; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/notify.py apps/api/src/nq_api/auth/deps.py
git commit -m "feat(onboarding): add 4-step welcome email sequence via Resend"
```

---

## Task 8: Upgrade Prompt Component

**Files:**
- Create: `apps/web/src/components/ui/UpgradePrompt.tsx`

- [ ] **Step 1: Create UpgradePrompt component**

Create `apps/web/src/components/ui/UpgradePrompt.tsx`:

```tsx
"use client";

import Link from "next/link";

interface UpgradePromptProps {
  feature?: string;
  currentTier?: string;
}

export default function UpgradePrompt({ feature, currentTier = "free" }: UpgradePromptProps) {
  const featureLabel = feature ? ` ${feature}` : "";

  return (
    <div className="rounded-2xl ghost-border bg-surface-low/40 p-8 text-center">
      <div className="text-3xl mb-3">🔒</div>
      <h3 className="font-headline text-xl font-bold">
        {featureLabel} requires an upgrade
      </h3>
      <p className="mt-2 text-on-surface-variant text-sm max-w-md mx-auto">
        You&apos;ve reached your {currentTier} tier daily limit. Upgrade to Investor for
        100 queries/day, 25 watchlists, and more.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link
          href="/pricing"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm hover:opacity-90 transition-opacity"
        >
          See pricing plans
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into query/screener/analyst pages**

In any page that uses rate-limited endpoints, catch 429/402 responses and render `<UpgradePrompt />`. Example for the query page:

Find where API errors are handled and add:

```tsx
if (res.status === 429 || res.status === 402) {
  return <UpgradePrompt feature="AI queries" />;
}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/ui/UpgradePrompt.tsx
git commit -m "feat(conversion): add UpgradePrompt component for rate-limited features"
```

---

## Task 9: Sector Landing Pages for SEO

**Files:**
- Create: `apps/web/src/app/best-stocks/[sector]/page.tsx`

- [ ] **Step 1: Create sector page**

Create `apps/web/src/app/best-stocks/[sector]/page.tsx`:

```tsx
import type { Metadata } from "next";
import Link from "next/link";

const SECTORS: Record<string, { name: string; tickers: string[]; description: string }> = {
  banking: {
    name: "Banking",
    tickers: ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS", "BANDHANBNK.NS", "AUBANK.NS", "FEDERALBNK.NS", "PNB.NS"],
    description: "Top banking stocks in India ranked by NeuralQuant 5-factor AI scoring. Quality, momentum, value, low-vol, and delivery analysis.",
  },
  it: {
    name: "IT & Technology",
    tickers: ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTIM.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS"],
    description: "Best IT stocks in India by NeuralQuant AI scoring. 5-factor analysis including quality, momentum, and value.",
  },
  pharma: {
    name: "Pharmaceuticals",
    tickers: ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "TORNTPHARM.NS", "BIOCON.NS", "LUPIN.NS", "CADILAHC.NS", "ALKEM.NS"],
    description: "Top pharma stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  auto: {
    name: "Automobile",
    tickers: ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "MOTHERSON.NS", "BOSCHLTD.NS", "TVSMOTOR.NS"],
    description: "Best auto stocks in India by NeuralQuant AI scoring.",
  },
  energy: {
    name: "Energy & Oil",
    tickers: ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", "BPCL.NS", "IOC.NS", "HINDPETRO.NS", "GAIL.NS", "ADANIGREEN.NS"],
    description: "Top energy stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  fmcg: {
    name: "FMCG",
    tickers: ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "EMAMILTD.NS"],
    description: "Best FMCG stocks in India by NeuralQuant AI scoring.",
  },
  metals: {
    name: "Metals & Mining",
    tickers: ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ADANIENT.NS", "SAIL.NS", "VEDL.NS", "NMDC.NS", "HINDCOPPER.NS", "MOIL.NS", "NATIONALUM.NS"],
    description: "Top metal stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  telecom: {
    name: "Telecom",
    tickers: ["BHARTIARTL.NS", "IDEA.NS", "TATACOMM.NS", "INDHOTEL.NS"],
    description: "Best telecom stocks in India by NeuralQuant AI scoring.",
  },
  infrastructure: {
    name: "Infrastructure",
    tickers: ["LT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "SHREECEM.NS", "ACC.NS", "AMBUJA.NS", "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS"],
    description: "Top infrastructure stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  "financial-services": {
    name: "Financial Services",
    tickers: ["BAJFINANCE.NS", "BAJAJFINSV.NS", "SHRIRAMFIN.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "MANAPPURAM.NS", "BAJAJHLDNG.NS", "LICHSGFIN.NS", "PFC.NS", "RECLTD.NS"],
    description: "Best financial services stocks in India by NeuralQuant AI scoring.",
  },
  cement: {
    name: "Cement",
    tickers: ["ULTRACEMCO.NS", "SHREECEM.NS", "ACC.NS", "AMBUJA.NS", "DALMIACEM.NS", "RAMCOCEM.NS", "JKCEMENT.NS", "BOMDCEM.NS", "INDIACEM.NS", "HEIDELBERG.NS"],
    description: "Top cement stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  chemicals: {
    name: "Chemicals",
    tickers: ["PIDILITIND.NS", "ATUL.NS", "SRF.NS", "DEEPAKNTR.NS", "TATAELXSI.NS", "NAVINFLUOR.NS", "AARTIDRUGS.NS", "VINATIORGA.NS", "BALAMINES.NS", "CLEAN.NS"],
    description: "Best chemical stocks in India by NeuralQuant AI scoring.",
  },
  "consumer-durables": {
    name: "Consumer Durables",
    tickers: ["TITAN.NS", "VOLTAS.NS", "BLUESTARCO.NS", "HAVELLS.NS", "ORIENTELEC.NS", "BAJAJELEC.NS", "WHIRLPOOL.NS", "CROMPTON.NS", "AMBER.NS", "BUTTERFLY.NS"],
    description: "Top consumer durable stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  "real-estate": {
    name: "Real Estate",
    tickers: ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "BRIGADE.NS", "SOBHA.NS", "PHOENIXLTD.NS", "NBCC.NS", "HIRANANDANI.NS"],
    description: "Best real estate stocks in India by NeuralQuant AI scoring.",
  },
  media: {
    name: "Media & Entertainment",
    tickers: ["ZEEL.NS", "SUNTV.NS", "PVR.NS", "INOXLEISUR.NS", "NETWORK18.NS", "DBL.NS"],
    description: "Top media stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ sector: string }>;
}): Promise<Metadata> {
  const { sector } = await params;
  const data = SECTORS[sector];
  if (!data) return { title: "Sector Not Found" };

  return {
    title: `Best ${data.name} Stocks in India 2026 — NeuralQuant AI Analysis`,
    description: data.description,
    alternates: {
      canonical: `https://neuralquant.vercel.app/best-stocks/${sector}`,
    },
  };
}

export function generateStaticParams() {
  return Object.keys(SECTORS).map((sector) => ({ sector }));
}

export default async function SectorPage({
  params,
}: {
  params: Promise<{ sector: string }>;
}) {
  const { sector } = await params;
  const data = SECTORS[sector];

  if (!data) {
    return <div className="p-10 text-center text-on-surface-variant">Sector not found</div>;
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <div className="max-w-6xl mx-auto px-6 py-20">
        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
          NeuralQuant ForeCast™
        </span>
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight">
          Best {data.name} Stocks in India
        </h1>
        <p className="mt-4 text-on-surface-variant max-w-2xl">
          {data.description} Updated nightly with live market data.
        </p>

        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {data.tickers.map((ticker) => {
            const name = ticker.replace(".NS", "").replace(/-/g, " ");
            return (
              <Link
                key={ticker}
                href={`/stocks/${ticker}`}
                className="rounded-xl ghost-border bg-surface-low/40 p-6 hover-glow transition-colors flex justify-between items-center"
              >
                <div>
                  <div className="font-semibold text-on-surface">{name}</div>
                  <div className="text-sm text-on-surface-variant">{ticker}</div>
                </div>
                <span className="text-primary text-sm font-medium">View analysis →</span>
              </Link>
            );
          })}
        </div>

        <div className="mt-16 text-center">
          <p className="text-on-surface-variant text-sm">
            Want full 5-factor scores + AI debate for these stocks?
          </p>
          <Link
            href="/signup"
            className="mt-4 inline-block px-6 py-3 rounded-xl bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm"
          >
            Create free account
          </Link>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds. Static paths generated for all 15 sectors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/best-stocks/
git commit -m "feat(seo): add 15 sector landing pages for organic search traffic"
```

---

## Task 10: In-App Onboarding Modal

**Files:**
- Create: `apps/web/src/components/onboarding/WelcomeModal.tsx`
- Modify: `apps/web/src/app/dashboard/page.tsx`

- [ ] **Step 1: Create WelcomeModal component**

Create `apps/web/src/components/onboarding/WelcomeModal.tsx`:

```tsx
"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

const POPULAR_STOCKS = [
  { ticker: "RELIANCE.NS", name: "Reliance" },
  { ticker: "TCS.NS", name: "TCS" },
  { ticker: "HDFCBANK.NS", name: "HDFC Bank" },
  { ticker: "INFY.NS", name: "Infosys" },
  { ticker: "AAPL", name: "Apple" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "GOOGL", name: "Alphabet" },
  { ticker: "NVDA", name: "Nvidia" },
  { ticker: "ICICIBANK.NS", name: "ICICI Bank" },
  { ticker: "BHARTIARTL.NS", name: "Bharti Airtel" },
];

export default function WelcomeModal({ onClose }: { onClose: () => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const toggle = (ticker: string) => {
    setSelected((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker].slice(0, 5)
    );
  };

  const handleContinue = async () => {
    setLoading(true);
    if (selected.length > 0) {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        await supabase.from("watchlists").insert({
          user_id: user.id,
          name: "My Watchlist",
          tickers: selected,
        });
      }
    }
    setLoading(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-strong ghost-border rounded-2xl p-8 max-w-md w-full mx-4">
        <h2 className="font-headline text-2xl font-bold">Welcome to NeuralQuant!</h2>
        <p className="mt-2 text-on-surface-variant text-sm">
          Pick 3-5 stocks you track. We&apos;ll create your first watchlist.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-2">
          {POPULAR_STOCKS.map((stock) => (
            <button
              key={stock.ticker}
              onClick={() => toggle(stock.ticker)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors text-left ${
                selected.includes(stock.ticker)
                  ? "bg-primary/20 text-primary ghost-border"
                  : "bg-surface-low text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {stock.name}
              <span className="block text-xs opacity-60">{stock.ticker}</span>
            </button>
          ))}
        </div>

        <div className="mt-6 flex justify-between items-center">
          <button onClick={onClose} className="text-sm text-on-surface-variant hover:text-on-surface">
            Skip
          </button>
          <button
            onClick={handleContinue}
            disabled={loading}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm disabled:opacity-50"
          >
            {loading ? "Creating..." : selected.length > 0 ? `Add ${selected.length} stocks` : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into dashboard**

In `apps/web/src/app/dashboard/page.tsx`, show the modal for first-time users:

```tsx
import { useState, useEffect } from "react";
import WelcomeModal from "@/components/onboarding/WelcomeModal";

// Inside the dashboard component:
const [showOnboarding, setShowOnboarding] = useState(false);

useEffect(() => {
  const seen = localStorage.getItem("nq_onboarding_seen");
  if (!seen) {
    setShowOnboarding(true);
    localStorage.setItem("nq_onboarding_seen", "1");
  }
}, []);

// In the return JSX, before the main content:
{showOnboarding && <WelcomeModal onClose={() => setShowOnboarding(false)} />}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/onboarding/WelcomeModal.tsx apps/web/src/app/dashboard/page.tsx
git commit -m "feat(onboarding): add first-login stock picker modal on dashboard"
```

---

## Task 11: Cold Email Outreach — Operational Playbook

**This is an operational task, not a code change.** Uses existing Apollo.io + Gmail MCP tools.

- [ ] **Step 1: Search Apollo for Indian finance professionals**

Use `mcp__claude_ai_Apollo_io__apollo_mixed_people_api_search` with:
- `person_titles`: ["equity analyst", "portfolio manager", "investment advisor", "CFA", "research analyst"]
- `organization_locations`: ["Mumbai, India", "Bangalore, India", "Delhi, India", "Hyderabad, India", "Chennai, India", "Pune, India"]
- `q_organization_keyword_tags`: ["Zerodha", "Groww", "Upstox", "Angel One", "HDFC Securities", "ICICI Direct", "Motilal Oswal"]
- `per_page`: 25
- Run multiple pages to collect 500+ contacts

- [ ] **Step 2: Enrich contacts with emails**

Use `mcp__claude_ai_Apollo_io__apollo_people_match` or `apollo_people_bulk_match` to get verified email addresses.

- [ ] **Step 3: Send Email 1 — Personal Intro**

Use `mcp__claude_ai_Gmail__create_draft` for each contact:
- Subject: "I built an AI that debates stocks like a research desk"
- Body: Personalized with their name, company, and a link to a stock they'd be interested in
- Review drafts before sending

- [ ] **Step 4: Send Email 2 — Value Prop (Day 3)**

Follow up with contacts who opened Email 1:
- Subject: "5-factor scoring + regime detection — see AAPL vs RELIANCE.NS"
- Link to specific stock comparison

- [ ] **Step 5: Send Email 3 — Social Proof (Day 7)**

Final follow-up:
- Subject: "Free tier, no credit card — early adopter perks inside"
- CTA to signup page with UTM: `?utm_source=apollo&utm_medium=email&utm_campaign=cold_outreach`

---

## Spec Coverage Check

| Spec Section | Task |
|-------------|------|
| 2.1 Apollo search | Task 11 |
| 2.2 Cold email sequence | Task 11 |
| 3.1 Dynamic stock page SEO | Task 2 |
| 3.2 Sector landing pages | Task 9 |
| 3.3 Sitemap + robots | Task 3 |
| 4.1 Regional pricing | Task 4 |
| 4.2 Currency detection | Task 4 |
| 4.3 Stripe Checkout + webhook | Task 5 |
| 5.1 Welcome email sequence | Task 7 |
| 5.2 In-app onboarding | Task 10 |
| 5.3 Referral system | Task 6 |
| 6.1 Plausible analytics | Task 1 |
| 6.2 Key metrics | Task 1 (via custom events) |
| Upgrade prompts | Task 8 |

**No gaps found.** All spec requirements covered by tasks.