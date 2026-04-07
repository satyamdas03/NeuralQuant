# NeuralQuant — QA, Authenticity Testing & Public Deployment Design
**Date:** 2026-04-07
**Status:** Approved by user

---

## Overview

Three-part plan: (1) deep QA & authenticity testing of all platform outputs, (2) competitive comparison against top AI finance tools, (3) public deployment on Vercel + Render free tier.

---

## Part 1 — QA & Authenticity Testing

### Endpoints to test
| Endpoint | Test |
|---|---|
| `GET /health` | Status OK, version correct |
| `GET /market/data-quality` | All FRED fields present, non-null, plausible values |
| `GET /screener?market=US` | 20 stocks, scores 1–10 spread, `_is_real=true` for all |
| `GET /screener?market=IN` | 20 NSE stocks, same checks |
| `GET /stocks/{ticker}?market=US` | Valid AAPL/NVDA/MSFT scores, factor percentiles present |
| `POST /query` | Self-aware: detects screener keywords, injects live data |
| `POST /analyst/{ticker}` | PARA-DEBATE 7 agents, HEAD ANALYST verdict present |

### Authenticity cross-checks
- **Macro data**: Compare NeuralQuant `/market/data-quality` VIX, 10Y yield, HY spread against FRED website and Yahoo Finance directly
- **Stock scores**: Pull raw yfinance data for AAPL, NVDA, MSFT and manually verify gross margin, P/E, P/B, beta match NeuralQuant's fundamentals
- **Query engine**: Test 5 real-world questions (Fed policy, tariffs, India market, top picks, specific stock) — compare depth/accuracy against Perplexity Finance

### Pass criteria
- All macro values within 5% of FRED/Yahoo reference
- Stock fundamental data fresher than 4 hours (cache TTL)
- Query engine cites NeuralQuant screener data when asked about top picks
- PARA-DEBATE returns structured verdict with bull/bear/risk for any valid ticker

---

## Part 2 — Competitive Comparison

### Test questions (identical to both platforms)
1. "What is the current macroeconomic environment for US equities?"
2. "What are your top 3 stock picks right now and why?"
3. "Should I be worried about US tariffs impacting tech stocks?"
4. "What is the outlook for NVIDIA?"
5. "How is the Indian stock market performing?"

### Evaluation dimensions
- Data freshness (live vs. delayed)
- Source citation (does it say where data comes from?)
- Quantitative grounding (does it cite actual numbers/scores?)
- India coverage (can it answer Q5 at all?)
- Explainability (does it show reasoning or just conclusions?)

---

## Part 3 — Deployment Architecture

### Stack
```
Users → Vercel (neuralquant.vercel.app)
           ↓ NEXT_PUBLIC_API_URL
        Render (nq-api.onrender.com)
           ↓
        Anthropic API + FRED API + yfinance
```

### Frontend — Vercel
- Connect `github.com/satyamdas03/NeuralQuant` to Vercel
- Root directory: `apps/web`
- Framework preset: Next.js
- Build command: `cd ../.. && npm run build --workspace=apps/web` (or Vercel auto-detects)
- Environment variable: `NEXT_PUBLIC_API_URL=https://<render-url>.onrender.com`
- Branch: `master`

### Backend — Render
- Service type: Web Service (Python)
- Root directory: `apps/api`
- Build command: `pip install uv && uv pip install -e ../../packages/data -e ../../packages/signals -e . --system`
- Start command: `uvicorn nq_api.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `ANTHROPIC_API_KEY`, `FRED_API_KEY`, `ENVIRONMENT=production`
- Free tier: 512MB RAM, spins down after 15 min idle

### CORS fix required
- Add Vercel domain to `allow_origins` in FastAPI CORS middleware before deploying

### Pre-deployment checklist
- [ ] `npm run build` passes locally
- [ ] CORS updated to allow Vercel domain
- [ ] No hardcoded `localhost` URLs in frontend code
- [ ] `NEXT_PUBLIC_API_URL` in `.env.local` is the only place the API URL is set
- [ ] Render build command handles monorepo workspace correctly

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Render free tier cold start (50s) | Warm up before demos; document for users |
| yfinance rate limits under load | Existing 4-hour cache reduces requests significantly |
| Monorepo build complexity on Render | Use `pip install --system` with explicit workspace paths |
| CORS blocking frontend→backend | Explicitly whitelist Vercel domain before deploy |
