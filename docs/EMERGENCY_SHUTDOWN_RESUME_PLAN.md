# NeuralQuant / QuantAlpha — EMERGENCY SHUTDOWN & RESUME PLAN

> **Created:** 2026-06-09
> **Purpose:** Stop all billable services immediately. Resume after ~10 days as if nothing happened.

---

## 💰 WEEKLY COST BREAKDOWN

| # | Service | Plan | Monthly | Weekly |
|---|---------|------|---------|--------|
| 1 | **Render nq-api** | Pro | ~$85 | **~$19.60** |
| 2 | **Render nq-openbb** | Standard | ~$25 | **~$5.77** |
| 3 | **Render nq-trader** | Starter | ~$7 | **~$1.62** |
| 4 | **Render quantastra-agent** | Standard | ~$25 | **~$5.77** |
| 5 | **Render 4× Cron Jobs** | Starter ×4 | ~$28 | **~$6.47** |
| 6 | **FMP Premium API** | $49/mo flat | $49 | **~$11.31** |
| 7 | **Porkbun Domain** | ~$12/yr | $12 | **~$0.23** |
| | **Vercel** | Hobby (FREE) | $0 | $0 |
| | **Supabase** | Free tier | $0 | $0 |
| | **Finnhub** | Free tier | $0 | $0 |
| | **FRED** | Free tier | $0 | $0 |
| | **GitHub Actions** | Free tier | $0 | $0 |
| | **Resend** | Free tier | $0 | $0 |
| | **Slack** | Free tier | $0 | $0 |
| | **TOTAL FIXED** | | **~$221/mo** | **~$51/week** |
| | **Variable (Anthropic, AWS, LiveKit, etc.)** | Usage-based | $0–$200+/mo | $0–$50+/wk |

**By following this guide you will save ~$51/week in fixed costs + whatever variable API costs you're incurring.**

---

## 🔴 PHASE 1: STOP BILLING IMMEDIATELY (Do this FIRST)

### Step 1A — Render: Scale ALL Services to 0 Instances

> ⚠️ **CRITICAL:** Render bills by running instance. Scaling to 0 stops compute billing while preserving ALL config, env vars, and deploy history.

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. For **each** of these services, click the service name → Settings → "Manual Deploy" OR scale instances to 0:

| Service | Action | Saves/Week |
|---------|--------|------------|
| `nq-api` (Web) | Scale instances → 0 | ~$19.60 |
| `nq-openbb` (Web) | Scale instances → 0 | ~$5.77 |
| `nq-trader` (Worker) | Scale instances → 0 | ~$1.62 |
| `quantastra-agent` (Worker) | Scale instances → 0 | ~$5.77 |
| `nq-anjali-refresh` (Cron) | Suspend or delete | ~$1.62 |
| `nq-market-refresh` (Cron) | Suspend or delete | ~$1.62 |
| `nq-wrap-in` (Cron) | Suspend or delete | ~$1.62 |
| `nq-wrap-us` (Cron) | Suspend or delete | ~$1.62 |

**How to scale to 0:**
- Service page → Settings → "Instance Type" → choose the smallest (Free if available) OR
- Service page → "Manual Deploy Only" toggle → ON (stops auto-restart)
- For Cron jobs: Service page → Settings → Delete service (cron configs are in `render.yaml`, you can recreate them)

> 💡 **Render keeps your environment variables, build history, and service config even when scaled to 0. You will NOT lose anything.**

---

### Step 1B — FMP Premium: Cancel Subscription

1. Go to [financialmodelingprep.com](https://financialmodelingprep.com) → Login → Billing → Cancel Subscription
2. Or email support@fmp.com to cancel
3. **Effect:** App will fall back to yfinance/Finnhub for data (slower, less reliable, but functional for 10 days)
4. **To resume:** Re-subscribe with same API key (retrieve from your password manager)

**Saves: ~$11.31/week**

---

### Step 1C — Vercel: Disconnect Auto-Deploy (optional — it's FREE)

Vercel Hobby tier is **free**. You can leave it running or disconnect to be safe:

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Select `neuralquant` project
3. Project Settings → Git → Disconnect Repository
4. This stops auto-deploys. Your site stays live at the last deployed version.

> 💡 **Vercel is free, so this is optional. But disconnecting prevents accidental deploys.**

---

### Step 1D — Supabase: Pause Project (optional — it's FREE)

Supabase is on the **free tier** ($0/month). You can:

**Option A: Leave it running** (costs $0, no action needed)
**Option B: Pause it** (recommended for safety)

To pause:
1. Go to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Select `neuralquant-prod` project
3. Project Settings → General → "Pause Project"
4. **Effect:** Database becomes read-only. All data is preserved.
5. **To resume:** Click "Restore Project" — takes ~2 minutes

> ⚠️ **If you pause Supabase, the live site will show errors.** Since you're shutting down Render anyway, this is fine.

---

### Step 1E — GitHub Actions: Disable Workflows

1. Go to [github.com/satyamdas03/NeuralQuant/actions](https://github.com/satyamdas03/NeuralQuant/actions)
2. For each active workflow, click it → "…" menu → "Disable workflow"
3. Disable these:
   - `ci.yml`
   - `nightly-score.yml`
   - `market-refresh.yml`
   - `quantfactor-sync.yml`
   - `anjali_github_workflow.yml`

> 💡 Disabling stops scheduled runs. Workflow files remain in the repo.

---

### Step 1F — Optional: Disable Trading

If you want to keep Render running for some reason but stop trading:

Set `TRADE_ENABLED=false` in Render Dashboard → `nq-trader` → Environment → Add/Edit variable.

But since you're scaling everything to 0, this is redundant.

---

## 📦 PHASE 2: BACKUP CRITICAL STATE (Before you walk away)

### What MUST be preserved

| # | State | Where | How to Backup |
|---|-------|-------|---------------|
| 1 | **PostgreSQL Database** (users, scores, conversations, watchlists, signals, etc.) | Supabase Cloud | `pg_dump` (script provided below) |
| 2 | **Render Environment Variables** (API keys, secrets) | Render Dashboard | Manual copy to password manager |
| 3 | **Vercel Environment Variables** | Vercel Dashboard | Manual export |
| 4 | **GitHub Repository Secrets** | GitHub Settings → Secrets | Screenshot or copy |
| 5 | **PayPal Subscription Records** | PayPal Dashboard | Export CSV |
| 6 | **Domain/DNS Records** | Porkbun + Vercel | Screenshot DNS settings |

---

### Step 2A — Database Backup (RUN THIS NOW)

Use the provided script:

```bash
# From repo root:
python scripts/backup_database.py
```

This creates `backups/nq_backup_YYYY-MM-DD_HHMMSS.sql.gz`.

**Keep this file safe.** It contains your entire database including user accounts, conversations, scores, and trading history.

---

### Step 2B — Export API Keys & Secrets

All critical secrets are stored in:
- `apps/api/.env` (local dev copy — do NOT commit this)
- Render Dashboard (production)
- Vercel Dashboard (frontend)

**Make sure you have these written down or in a password manager:**

```
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
FMP_API_KEY=<FMP_API_KEY>
SUPABASE_SERVICE_ROLE_KEY=<SUPABASE_SERVICE_ROLE_KEY>
SUPABASE_ANON_KEY=<SUPABASE_ANON_KEY>
SUPABASE_JWT_SECRET=<SUPABASE_JWT_SECRET>
PAYPAL_CLIENT_ID=<PAYPAL_CLIENT_ID>
PAYPAL_CLIENT_SECRET=<PAYPAL_CLIENT_SECRET>
PAYPAL_WEBHOOK_ID=<PAYPAL_WEBHOOK_ID>
CRON_SECRET=<CRON_SECRET>
SMOKE_TEST_SECRET=<SMOKE_TEST_SECRET>
STRIPE_SECRET_KEY=<STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<STRIPE_WEBHOOK_SECRET>
AWS_ACCESS_KEY_ID=<AWS_ACCESS_KEY_ID>
AWS_SECRET_ACCESS_KEY=<AWS_SECRET_ACCESS_KEY>
LIVEKIT_URL=<LIVEKIT_URL>
LIVEKIT_API_KEY=<LIVEKIT_API_KEY>
LIVEKIT_API_SECRET=<LIVEKIT_API_SECRET>
DEEPGRAM_API_KEY=<DEEPGRAM_API_KEY>
ELEVENLABS_API_KEY=<ELEVENLABS_API_KEY>
RESEND_API_KEY=<RESEND_API_KEY>
SLACK_BOT_TOKEN=<SLACK_BOT_TOKEN>
SLACK_APP_TOKEN=<SLACK_APP_TOKEN>
```

> ⚠️ **NEVER share these publicly. The `.env` file in your repo has production secrets in plaintext — this is a security risk. Consider rotating all keys after resume.**

---

## 🟢 PHASE 3: RESUME AFTER ~10 DAYS

### Pre-Resume Checklist

- [ ] You have the database backup file (`backups/nq_backup_*.sql.gz`)
- [ ] You have all API keys and secrets
- [ ] FMP Premium is re-subscribed (if you cancelled it)
- [ ] You remember your Render, Vercel, Supabase, and Porkbun login credentials

---

### Step 3A — Supabase: Unpause (if paused)

1. [supabase.com/dashboard](https://supabase.com/dashboard) → `neuralquant-prod` → "Restore Project"
2. Wait ~2 minutes for database to come back online
3. Verify: `curl https://ajkhyayrbqiuvnsmqrdz.supabase.co/rest/v1/score_cache?limit=1`

---

### Step 3B — Render: Scale Services Back Up

1. [dashboard.render.com](https://dashboard.render.com)
2. For each service, scale instances back to 1:
   - `nq-api` → Pro plan, 1 instance
   - `nq-openbb` → Standard plan, 1 instance
   - `nq-trader` → Starter plan, 1 instance (if you want trading)
   - `quantastra-agent` → Standard plan, 1 instance (if you want voice)
3. Re-create cron jobs (or use `render.yaml` blueprint deploy):
   - `nq-anjali-refresh` (daily 02:00 UTC)
   - `nq-market-refresh` (weekdays 20:30 UTC)
   - `nq-wrap-in` (weekdays 11:00 UTC)
   - `nq-wrap-us` (weekdays 21:30 UTC)

> 💡 **Render will auto-deploy the latest commit from GitHub when you restart.**

---

### Step 3C — FMP Premium: Re-Subscribe

1. [financialmodelingprep.com](https://financialmodelingprep.com) → Pricing → Subscribe
2. Verify your FMP key is still active (retrieve from your password manager)
3. If not, update `FMP_API_KEY` in Render Dashboard → `nq-api` → Environment

---

### Step 3D — Vercel: Reconnect GitHub

1. [vercel.com/dashboard](https://vercel.com/dashboard) → `neuralquant`
2. Project Settings → Git → Connect Repository → `satyamdas03/NeuralQuant`
3. Set root directory to `apps/web`
4. Deploy should trigger automatically

---

### Step 3E — GitHub Actions: Re-enable Workflows

1. [github.com/satyamdas03/NeuralQuant/actions](https://github.com/satyamdas03/NeuralQuant/actions)
2. For each disabled workflow, click it → "…" → "Enable workflow"

---

### Step 3F — Verify Everything Works

Run the smoke test:

```bash
python scripts/smoke_test.py \
  --api https://neuralquant.onrender.com \
  --cron-secret "<CRON_SECRET>" \
  --smoke-secret "<SMOKE_TEST_SECRET>"
```

Expected: **14/15 or 15/15 PASS**

Then verify manually:

```bash
# API version
curl https://neuralquant.onrender.com/health

# Score cache fresh
curl https://neuralquant.onrender.com/health/score-cache

# IN stocks (should show varied scores now)
curl https://neuralquant.onrender.com/stocks/GICRE?market=IN
curl https://neuralquant.onrender.com/stocks/TCS?market=IN

# Frontend live
curl https://neuralquant.co
```

---

## ⚠️ WHAT WILL BREAK DURING SHUTDOWN

| Feature | Status During Shutdown | Why |
|---------|------------------------|-----|
| Website (`neuralquant.co`) | ❌ Offline | Render `nq-api` is down |
| Ask AI | ❌ Offline | Backend down |
| Stock scores | ❌ Offline | Backend down |
| Screener | ❌ Offline | Backend down |
| Trading daemon | ❌ Offline | `nq-trader` scaled to 0 |
| Voice agent | ❌ Offline | `quantastra-agent` scaled to 0 |
| Market wraps | ❌ Offline | Cron jobs suspended |
| Anjali sync | ❌ Offline | Cron jobs suspended |
| Score cache | ⚠️ Stale | Not updated (but data preserved in Supabase) |
| User accounts | ✅ Preserved | In Supabase (paused or running) |
| Conversations | ✅ Preserved | In Supabase |
| Watchlists | ✅ Preserved | In Supabase |
| Trading history | ✅ Preserved | In Supabase + Alpaca |
| Domain | ✅ Active | Porkbun renews annually |

---

## 🛡️ SECURITY NOTE

Your `apps/api/.env` file contains **plaintext production secrets**.

**Recommended action after resume:**
1. Rotate ALL API keys (Anthropic, FMP, Supabase JWT, PayPal, etc.)
2. Move secrets to a password manager (1Password, Bitwarden)
3. Replace `.env` with `.env.example` (placeholders only)
4. Update Render/Vercel dashboards with new rotated keys
5. Never commit `.env` to git again

---

## 📞 EMERGENCY CONTACTS

| Service | Support URL |
|---------|-------------|
| Render | [render.com/help](https://render.com/help) |
| Vercel | [vercel.com/help](https://vercel.com/help) |
| Supabase | [supabase.com/support](https://supabase.com/support) |
| FMP | support@fmp.com |
| Porkbun | porkbun.com/support |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) |

---

*Plan generated 2026-06-09. Review before executing.*
