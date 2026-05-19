# NeuralQuant Go-To-Market & Business Strategy

**Date:** 2026-04-24
**Status:** Approved
**Approach:** Community-Led Growth (Approach A)

---

## 1. Target Market & Positioning

**Primary:** India retail investors (90M+ Demat accounts, $26B+ market)
**Secondary:** US retail investors (S&P 500 coverage as differentiator)
**Positioning:** "Institutional-grade AI stock research at retail scale — free forever, paid for power users"

**Why India first:**
- 90M+ Demat accounts growing 15% YoY
- Zero AI quant competitors (Danelfin, TRUE AI, SimplyWall.St are US-only)
- Price-sensitive market = free tier as massive acquisition moat
- PARA-DEBATE + 5-factor engine = unique, defensible

---

## 2. Lead Generation Pipeline

### 2.1 Apollo.io Search Strategy

**Target personas:**
- Job titles: "equity analyst", "portfolio manager", "trader", "investment advisor", "CFA", "research analyst", "wealth manager"
- Locations: Mumbai, Bangalore, Delhi, Hyderabad, Chennai, Pune
- Company keywords: Zerodha, Groww, Upstox, Angel One, Motilal Oswal, HDFC Securities, ICICI Direct, Kotak Securities, Sharekhan
- SEBI-registered RIAs and research analysts

**Workflow:**
1. Search Apollo for matching contacts → enrich emails via People Match
2. Export contact list with email, name, title, company
3. Import into cold email sequence via Gmail MCP

### 2.2 Cold Email Sequence (3 emails, 5-day cadence)

**Email 1 — Personal Intro (Day 0):**
Subject: "I built an AI that debates stocks like a research desk"
Body: Personal hook referencing their role/company → "NeuralQuant runs 6 specialist AI analysts in a structured debate on any stock — plus 5-factor quant scoring. It's free to try. Here's [SPECIFIC STOCK] analyzed: [link]"
CTA: "Try it free — neuralquant.vercel.app"

**Email 2 — Value Prop (Day 3):**
Subject: "5-factor scoring + regime detection — see AAPL vs RELIANCE.NS"
Body: "Most stock tools give you a single score. NeuralQuant gives you 5 independent factors (quality, momentum, value, low-vol, insider signals) plus a 4-state HMM regime detector. Plus 6 AI analysts debate every angle before you invest."
CTA: "Run your own analysis — [link]"

**Email 3 — Social Proof + Urgency (Day 7):**
Subject: "Free tier, no credit card — early adopter perks inside"
Body: "Join 100+ investors using NeuralQuant. Free tier gives you 10 AI queries/day, 5 watchlists, full screener access. No credit card. Early adopters get a 'Founder' badge + extra queries."
CTA: "Create free account — [link]"

### 2.3 Volume & Conversion Targets

- 5,000 contacts per batch
- Expected: 5% open rate → 1.5% click rate → 0.8% signup rate
- Per batch: ~40 signups
- 10 batches over 30 days: ~300-400 users from cold email
- Plus organic SEO (see Section 3): target 600+ signups over 90 days
- **Total target: 1,000 users in 90 days**

---

## 3. Programmatic SEO — Organic Growth Engine

### 3.1 Dynamic Stock Pages (1,200+ indexable pages)

Each `/stocks/{ticker}` page already exists. Enhance with:

**SEO meta tags:**
- `<title>`: "{TICKER} Stock Score — NeuralQuant 5-Factor AI Analysis"
- Meta description: factor breakdown, regime, market cap
- Open Graph image: auto-generated score card (server-side)
- JSON-LD structured data: `FinancialProduct` schema with rating, offers

**Target keywords (per stock page):**
- "RELIANCE stock analysis AI" (long-tail, low competition)
- "TCS stock score free" (long-tail)
- "HDFC Bank AI analysis India" (long-tail)

### 3.2 Sector Landing Pages (15 pages)

Create `/best-stocks/{sector}` routes:
- `/best-stocks/banking` — Top 10 banking stocks by NeuralQuant score
- `/best-stocks/it` — Top IT stocks
- `/best-stocks/pharma`, `/best-stocks/auto`, `/best-stocks/energy`, etc.
- 15 NSE sectors = 15 additional SEO pages with unique, data-driven content

**Target keywords:**
- "best stocks to buy India 2026" (12K/mo)
- "NIFTY stock screener free" (8K/mo)
- "AI stock analysis India" (emerging, zero competition)
- "best banking stocks India" (6K/mo)

### 3.3 SEO Infrastructure

- Dynamic sitemap.xml listing all 1,200+ tickers + sector pages
- robots.txt allowing full crawl
- Canonical URLs on all pages
- Next.js `generateMetadata()` for dynamic meta tags
- `generateStaticParams()` for pre-rendering top 100 stocks at build time

---

## 4. Monetization — Stripe + Regional Pricing

### 4.1 Pricing Tiers

| Tier | INR | USD | Watchlists | Queries/day | Backtests/day |
|------|-----|-----|------------|-------------|---------------|
| Free | ₹0 | $0 | 5 | 10 | 5 |
| Investor | ₹299/mo | $9/mo | 25 | 100 | 5 |
| Pro | ₹999/mo | $29/mo | 100 | 1,000 | 50 |
| API | ₹4,999/mo | $149/mo | 1,000 | 100,000 | 1,000 |

### 4.2 Currency Detection

- Check `navigator.language` for Indian locales (`hi-IN`, `en-IN`)
- Fallback: IP geolocation via free `ipapi.co` API
- Show INR for India, USD for rest
- User can toggle currency on pricing page

### 4.3 Stripe Integration

**Backend:**
- `POST /checkout/session` — Create Stripe Checkout Session with regional price
- `POST /webhooks/stripe` — Handle `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
- Update `users.tier` in Supabase on webhook events
- Store `stripe_customer_id` + `stripe_subscription_id` in `users` table (schema ready)

**Frontend:**
- New `/pricing` page with tier comparison table
- INR/USD toggle
- "Most popular" badge on Investor tier
- Stripe Checkout redirect on paid tier click
- Upgrade prompt when free user hits daily cap: "Upgrade to Investor — ₹299/mo"

---

## 5. Onboarding + Retention

### 5.1 Email Welcome Sequence (via Resend)

**Day 0 — Welcome:**
Subject: "Welcome to NeuralQuant — here's your first analysis"
Body: Quickstart guide + link to pre-analyzed stock (RELIANCE.NS or AAPL)

**Day 1 — PARA-DEBATE Demo:**
Subject: "Watch 6 AI analysts debate RELIANCE"
Body: Screenshot of debate + CTA to run own analysis

**Day 3 — Screener:**
Subject: "Find top-rated stocks in seconds"
Body: Pre-built screener configs + CTA to run screener

**Day 7 — Upgrade:**
Subject: "Unlock 100 queries/day — Investor tier"
Body: Usage stats + social proof + pricing link

### 5.2 In-App Onboarding

- First-login modal: "Pick 3 stocks you track" → auto-create watchlist
- Tooltip tour on dashboard (3-step: screener, watchlist, ask AI)
- "New" badges on recently added features

### 5.3 Referral Loop

**Supabase schema:**
```sql
CREATE TABLE public.referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_id UUID REFERENCES auth.users NOT NULL,
  referred_email TEXT NOT NULL,
  code TEXT UNIQUE NOT NULL,
  status TEXT DEFAULT 'pending', -- pending, signed_up, converted
  created_at TIMESTAMPTZ DEFAULT now()
);
```

**Mechanics:**
- Each user gets unique code: `NQ-{username_hash}`
- Referrer gets +5 daily queries per successful referral
- Referee gets +5 daily queries on signup
- Referral stats visible on `/dashboard`
- Shareable link: `neuralquant.vercel.app/signup?ref=NQ-abc123`

---

## 6. Analytics + Measurement

### 6.1 Plausible Analytics

Self-hosted or cloud (GDPR-friendly, no cookie banner needed, $0 free tier).

**Page views:** All routes tracked automatically
**Custom events:**
- `signup` — New account created
- `query_sent` — AI query submitted
- `debate_viewed` — PARA-DEBATE analysis viewed
- `watchlist_created` — New watchlist
- `screener_run` — Screener query executed
- `upgrade_shown` — Upgrade prompt displayed
- `upgrade_clicked` — User clicked upgrade CTA
- `checkout_started` — Stripe Checkout initiated
- `payment_success` — Payment completed

### 6.2 Key Metrics

| Metric | Target (90 days) | How to measure |
|--------|-------------------|----------------|
| Total users | 1,000 | Supabase `auth.users` count |
| DAU (daily active) | 150+ | Plausible |
| Free→Paid conversion | 3-5% | Stripe + Supabase |
| MRR | ₹22K+ (75 paid users × ₹299 avg) | Stripe Dashboard |
| Queries/user/day | 3+ | `usage_log` aggregation |
| Churn rate | <5%/month | Stripe subscription status |
| Cold email signup rate | 0.5-1% | Plausible UTM tracking |

---

## 7. Investor Readiness

### 7.1 Traction Milestones for Seed Pitch

Update existing `docs/NeuralQuant_Investor_Pitch.pdf` with:

**Traction data:**
- User count + growth rate
- MRR + conversion rate
- DAU/MAU ratio (engagement)
- Queries per user (product-market fit signal)

**Market sizing:**
- TAM: 90M Indian Demat accounts × ₹300/mo ARPU = ₹32,400 Cr/year
- SAM: 10M active traders × ₹300/mo = ₹3,600 Cr/year
- SOM: 50K users in 18 months × ₹400/mo blended ARPU = ₹240 Cr/year

### 7.2 Financial Projections (12-month model)

| Period | Users | Paid Users | MRR |
|--------|-------|-------------|------|
| Month 1-3 | 1,000 | 0 (free only) | ₹0 |
| Month 4-6 | 2,500 | 75 (3%) | ₹22K-75K |
| Month 7-9 | 5,000 | 200 (4%) | ₹60K-200K |
| Month 10-12 | 10,000 | 500 (5%) | ₹1.5L-5L |

### 7.3 Key Investor Data Points

- 90M Demat accounts growing 15% YoY
- Zero AI quant competitors in India
- $26B+ Indian stock market
- 5-factor engine + 7-agent debate = defensible moat (not replicable by ChatGPT wrapper)
- Free tier = zero-friction acquisition (vs TRUE AI $20/mo min)
- PARA-DEBATE = branded, marketed feature ("6 Analysts Debate Your Stock")
- Academic rigor: Jegadeesh-Titman, Piotroski, Hamilton citations on landing page
- LightGBM LambdaRanker = ML-based ranking competitors lack

---

## 8. Implementation Order (Priority)

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Stripe Checkout + webhook | Medium | Revenue enabler |
| P0 | Pricing page (INR/USD) | Low | Conversion enabler |
| P0 | Plausible analytics setup | Low | Measurement enabler |
| P0 | SEO meta tags on stock pages | Low | Organic growth |
| P1 | Dynamic sitemap + robots.txt | Low | SEO infrastructure |
| P1 | Cold email sequence via Apollo + Gmail MCP | Low | User acquisition |
| P1 | Welcome email sequence (Resend) | Low | Retention |
| P1 | Referral system (Supabase + code gen) | Medium | Viral growth |
| P2 | Sector landing pages | Medium | SEO depth |
| P2 | In-app onboarding (first-login modal) | Medium | Activation |
| P2 | Upgrade prompts on rate limit hits | Low | Conversion |
| P3 | Pitch deck update with traction | Low | Fundraising |
| P3 | Financial projections model | Low | Fundraising |