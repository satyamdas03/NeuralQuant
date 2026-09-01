# NeuralQuant — Acquisition Prospectus & Valuation Brief

**Prepared:** June 2026
**Seller:** Satyam Das (satyamdas03@gmail.com)
**Asset:** NeuralQuant — AI stock-intelligence platform (live at neuralquant.co)
**Status:** Live, production-deployed, investor-demo-ready
**Document classification:** Shareable with serious prospective acquirers under NDA

---

## 1. Executive Summary

NeuralQuant is a production-grade, multi-agent AI stock-research platform covering the US and India equity markets (~949 stocks). It is **live and operational today** at neuralquant.co — not a prototype, not a slide deck. The platform combines a proprietary quantitative scoring engine, an adversarial multi-agent LLM research committee, and real-time voice-agent interfaces, backed by a filed patent application and a demonstrated backtested alpha track record.

This document explains the composition of the asset, the engineering investment it represents, and the rationale behind the asking price. Proprietary algorithm internals, source code, prompts, and credentials are **not** disclosed in this document; they are made available during due diligence under NDA and after a letter of intent.

---

## 2. Competitive Positioning

**"Why can't I just buy Bloomberg, use Danelfin, or build this myself?"** — the single most important question an acquirer asks. The honest answer is that no existing product occupies NeuralQuant's position, and rebuilding it is a 6–12 month, multi-hundred-thousand-dollar undertaking with material execution risk.

| Platform | Price / mo | Multi-agent AI | Adversarial debate | India (NSE-native) | Voice agents | Live-data quant scoring |
|---|---|---|---|---|---|---|
| **Bloomberg Terminal** | $2,000 | ✗ | ✗ | ✗ | ✗ | Data only (no AI score) |
| **Danelfin** | ~$34 | Scoring only | ✗ | ✗ (US only) | ✗ | ✓ (US only) |
| **Ticker.in** | ~$5 | ✗ | ✗ | ✓ (India only) | ✗ | Basic |
| **ChatGPT / Claude** | $20 | General-purpose | ✗ | ✗ | General voice | ✗ (no live data) |
| **NeuralQuant** | **$9.99** | **✓** | **✓** | **✓** | **✓ (2 live)** | **✓ (US + India)** |

Bloomberg has the data but no AI reasoning layer and a 200× higher price. Danelfin has scoring but is US-only, single-score, with no adversarial scrutiny and no voice. Ticker.in covers India but has no AI engine. General-purpose LLMs have no live market data and no quant engine — they hallucinate numbers. **NeuralQuant is the only product that combines all of it, at a retail price point.**

**And building it yourself?** §8 quantifies it: **24–37 senior engineer-months** plus 6–12 months of calendar, the data-source and voice-stack integration scars a live system has already absorbed, and a pending patent that raises a copier's cost and legal risk. Acquisition collapses that timeline to zero.

---

## 3. What Is Being Acquired

A complete, running software business-in-a-box: domain, brand, codebase, infrastructure, data pipeline, intellectual property, and operating services.

### 3.1 Surface area at a glance

| Dimension | Scale |
|---|---|
| Backend API routers | 33 |
| Web pages / routes | 38 |
| Running services | 7 (4 on Render, 1 Vercel, 1 GCP, 1 Supabase) |
| Scheduled jobs | 4 daily cron jobs (nightly scoring, market refresh, quantfactor sync) |
| Production tests | 186+ (passing) |
| Markets covered | US + India |
| Stock universe | ~949 stocks (502 India + 447 US) |
| AI agents | 8 distinct agents across research, debate, and voice |
| Live voice interfaces | 2 (a voice PM and an ambient voice companion) |
| Patent | Application filed (provisional stage) |
| Current version | v4.1.3 |

### 3.2 Flagship capabilities (all live)

- **Adversarial research committee** — a multi-agent LLM investment committee that produces a bull case, an adversarial steelmanned bear case, and a synthesized verdict per pick. Designed to prevent consensus herding — a trust moat absent from competing products.
- **Written research analyst** — a queryable AI analyst that returns cited, data-validated written research on demand, with clarification questions and live price injection.
- **Voice portfolio manager** — a real-time conversational voice agent (speech-to-text → reasoning LLM → neural text-to-speech) with ~20 function-calling tools, file upload, and a whiteboard.
- **Ambient voice companion** — an always-listening voice assistant with page-context awareness, a wake word, and a morning briefing.
- **Proprietary scoring engine** — a multi-factor quantitative ranking system including a unique Investment-Ready Score (IRS%) that, to the seller's knowledge, no competing product offers.
- **Live paper-trading dashboard** — a real-time trading matrix with equity curve, trade tape, and strategy reflection stream.

---

## 4. Strategic Fit by Buyer Type

NeuralQuant is not a one-size-fits-all asset — its value is highest to four distinct buyer profiles, each acquiring a different strategic advantage.

| Buyer type | What they acquire | Why it matters |
|---|---|---|
| **Indian brokers** | A ready-made AI research layer for 90M+ Demat account holders — no build required | Differentiated retention/acquisition feature deployable on day one, instead of an 18-month internal build |
| **US / global fintechs** | India market entry (NSE + BSE coverage with India-specific signals) | The dual-market pipeline would take ~18 months to build independently; here it is already live |
| **PE firms / family offices** | Proven alpha (+12.69% to +14.83% vs NIFTY50), patent-protected, ready to monetise | A defensible, IP-encumbered asset to acquire and scale with a commercial team |
| **AI companies** | Voice-native equity research — 2 live voice agents already deployed | Voice-first financial research is ahead of the market; competitors are text-only |

---

## 5. Technology Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, async |
| Frontend | Next.js 16, React 19, Tailwind v4 (PWA) |
| Database / Auth | Supabase (Postgres + cookie-session auth) |
| Voice real-time | LiveKit Cloud (WebRTC SFU) |
| Speech-to-text | Deepgram |
| Text-to-speech | LiveKit Inference (cartesia/sonic-3.5) |
| LLM providers | Anthropic (Claude) + AWS Bedrock (cross-region) |
| Market data | FMP Premium, Finnhub, yfinance, OpenBB Platform, EDGAR, FRED |
| Hosting | Render (4 services), Vercel (web), GCP Always Free (trading + India feeder), Supabase (DB) |
| CI/CD | GitHub Actions, Render auto-deploy, Vercel GitHub auto-deploy |
| Repo size | Monorepo, uv workspace |

---

## 6. Infrastructure (Operating Today)

All services are running and verified as of the date of this document.

| Service | Role | State |
|---|---|---|
| Core API | 33-router FastAPI backend | Live |
| Voice agent worker | LiveKit voice agents (2) | Live |
| Paper-trading worker | Trading daemon | Live (dry-run) |
| Market-data proxy | OpenBB platform (live-price unlock) | Live |
| Trading engine | BTC/USDT paper trading + SSE stream | Live |
| Web app | neuralquant.co, 38 pages | Live |
| Database | Postgres + auth | Live |

**Scheduled jobs:** 4 daily cron jobs handling nightly scoring, market refresh, quantfactor sync, and quantfactor enrichment. End-of-day wrap reports were previously email-based and have been removed.

**Security hardening:** The platform has undergone a multi-phase security pass including log redaction, secret-scanning in CI, row-level security policies, IDOR remediation, content-security-policy headers, rate-limiting fuses, upload guards, dependency auditing, and an audit-event log with an incident-response runbook.

---

## 7. Validation & Track Record

### 7.1 Backtest results (Q1 FY27, India)
- All three model pools beat the NIFTY50 benchmark.
- Outperformance (alpha): **+12.69% to +14.83%** vs NIFTY50 (−6.38% in the same period).
- Hit rate: **87–91%**.
- Baseline stored in Supabase for reproducibility.

### 7.2 Automated smoke testing
A 15-endpoint live smoke suite runs against production and currently passes 15/15, covering core pages, stock detail (US + India), screener, portfolio, trading dashboard, news, methodology, and pricing.

### 7.3 Intellectual property & patent moat
The platform benefits from a developing IP moat. A **provisional patent application** has been filed with the **Indian Patent Office**, covering three core inventive elements:

1. The **PARA-DEBATE** adversarial multi-agent debate architecture (a structured "Devil's Advocate" agent that steelmans the bear case before synthesis);
2. The **HMM-based regime-adaptive factor-weighting engine** (factor weights shift dynamically across Risk-On / Risk-Off / Bear / Late-Cycle market states); and
3. The **NSE `delivery_pct` India-specific liquidity conviction signal**, a market-microstructure factor not present in any comparable system.

This establishes **patent-pending status in India**, with a **PCT filing contemplated** to extend protection across 150+ jurisdictions. In parallel, the **PARA-DEBATE™ trademark** is being registered in India under **Class 42**, further strengthening the platform's proprietary positioning. Backend trade secrets — the per-regime factor weights, HMM transition probabilities, agent-prompt architecture, and IRS% composite formula — sit alongside the patent as a second, non-public layer of protection.

### 7.4 Regulatory posture
Methodology and backtest results are published on a public methodology page in a legally-cautious manner (no guaranteed-return claims). SEBI-compliance considerations for India have been researched.

---

## 8. Engineering Investment (Cost Breakdown)

The asking price is grounded in what it would cost an acquirer to recreate an equivalent system from scratch — in money, time, and risk. The figures below are **rebuild-cost estimates** based on senior-engineer effort for each subsystem, expressed in person-months. They describe scope, not proprietary internals.

### 8.1 Subsystem rebuild effort

| Subsystem | Scope (no IP detail) | Senior eng-months |
|---|---|---|
| Backend API | 33 async routers, auth, quota, rate limiting, session mgmt | 4–6 |
| Multi-agent research engine | Adversarial committee orchestration, synthesis, verdict logic | 3–4 |
| Written research analyst | Query routing, data validation, clarification, live-price injection | 2–3 |
| Quantitative scoring engine | Multi-factor ranking + IRS% + regime model + walk-forward validation | 2–3 |
| Data pipeline | Multi-source ingestion (6 providers), normalization, caching, US+India parity | 3–4 |
| Voice agent #1 (PM) | LiveKit agent, ~20 tools, STT/TTS, file upload, whiteboard | 2–3 |
| Voice agent #2 (companion) | Ambient listening, wake word, page context, briefing | 1–2 |
| Frontend web app | 38 pages, PWA, voice UI, charts, auth-gated flows | 3–4 |
| Live trading dashboard | Real-time matrix, SSE stream, equity curve, trade tape | 1–2 |
| DevOps & infra | 7-service deploy config, CI/CD, 4 cron jobs, secrets, monitoring | 1–2 |
| Security hardening | RLS, IDOR, CSP, audit log, fuses, dep-audit, IR runbook | 1–2 |
| Testing | 186+ tests, live smoke suite, backtest harness | 1–2 |
| **Total** | | **24–37 eng-months** |

### 8.2 Translated to cost

At senior-engineer rates:
- **India senior (₹2–3L/month):** ₹48L–1.1Cr in pure labor.
- **US senior ($12–18k/month):** $290k–$665k (₹2.4–5.6Cr).

These are **labor-only** figures. They exclude:
- Infrastructure spend to date (Render/Vercel/Supabase/LiveKit/API keys)
- Domain and brand assets
- Patent filing fees and legal
- 6–12 months of calendar time (opportunity cost)
- Build risk: a from-scratch rebuild has material probability of schedule overrun, data-source breakage, and integration failure that a live system has already absorbed.

### 8.3 The "live and de-risked" premium
An acquirer purchasing a running system avoids:
- 6–12 months of build calendar
- Data-source integration risk (the platform already solved multiple provider failures, rate limits, and India/US market divergences)
- Voice-stack integration risk (LiveKit + STT + LLM + TTS pipelines are notoriously flaky to stabilize)
- Security debt accumulation (the platform ships already-hardened)

Conservatively, the de-risked + live + calendar-saved premium is **1.5–3× raw rebuild cost**.

### 8.4 Strategic / IP premium
- IRS% is unique in the market — no competing product offers an equivalent readiness score.
- The adversarial committee design is a defensible trust moat.
- A pending patent encumbers competitors.
- Voice-native equity research is ahead of the market (competitors are text-only).

---

## 9. Valuation Rationale

| Approach | Result |
|---|---|
| Raw rebuild cost (India senior) | ₹48L–1.1Cr |
| Raw rebuild cost (US senior) | ₹2.4–5.6Cr |
| Rebuild + live/de-risked premium (1.5–3×) | ₹1.5–3.4Cr |
| Strategic/IP value (unique IRS% + patent + voice moat) | ₹3–5Cr |
| Revenue multiple | Not applicable (pre-revenue; see §9.1) |

### 9.1 Pre-revenue by design — a clean greenfield, not a gap
The platform has been **deliberately kept pre-revenue**, with the seller prioritising technical robustness, IP defensibility, and backtest validation over early-stage commercialisation. Payments infrastructure, including **Stripe integration, is already in place and activation-ready**, enabling an acquirer to capture **100% of monetisation upside from closing**. With **no legacy pricing obligations, no embedded churn, and no inherited customer-support burden**, the asset offers a clean, greenfield revenue build on top of a production-ready, patent-pending platform.

Accordingly, valuation is anchored on **asset/rebuild + IP premium**, not on a revenue multiple. A revenue multiple would apply only after the acquirer monetizes — see the illustrative ROI model in §10.

---

## 10. Revenue Model Projection (Illustrative)

The platform is pre-revenue today, but the monetisation engine is built and activation-ready. The scenarios below are **illustrative, not guaranteed** — they exist to give an acquirer a mental model for return on investment.

| Scenario | Assumption | Indicative ARR |
|---|---|---|
| **Conservative** | 2,000 paying subscribers @ $9.99/mo | ~$240K ARR |
| **Base** | 5,000 subscribers + B2B API tier | ~$800K ARR |
| **Upside** | 50,000 subscribers via broker partnership | ~$6M ARR |

**Payback math:** at an acquisition price of **~₹1.5 Cr (≈$180K)** against the **base-case ~$800K ARR**, the purchase price is recovered in well under one year of revenue (illustrative, gross of operating costs). For a strategic buyer with an existing distribution channel — a broker or wealth platform — the upside scenario makes the payback effectively immediate.

*These projections are illustrative scenarios provided for buyer modelling only. They are not forecasts, guarantees, or representations of future performance.*

---

## 11. Asking Price

| | Amount (INR) | When it applies |
|---|---|---|
| **Opening ask** | ₹3 Cr | Strategic acquirer (brokerage, fund, fintech) valuing IP + voice moat + patent |
| **Expected settle** | ₹1.5–2 Cr | Working-product buyer, normal negotiation |
| **Walk-away floor** | ₹1 Cr | Asset-only buyer; below this the seller retains the asset |

**Rationale for the floor:** ₹1 Cr is below the conservative India-senior rebuild cost plus infrastructure, domain, patent, and opportunity cost already invested. Selling below it transfers more value than the seller would recover by continuing to operate.

---

## 12. Sale Process & Urgency

The seller is conducting a **structured sale process**:

- **Letters of intent are invited by [LOI deadline: __________].**
- Multiple parties have been approached.
- The seller reserves the right to accept an offer at any time, including before the stated deadline.

**Category-timing risk for the buyer.** A US competitor operating under the **neuralquant.dev** name is actively building in this space. The India + US dual-market position — the single hardest element to replicate — is currently uncontested. Early acquisition **locks in the dual-market moat before it becomes a contested category**; waiting risks a competitor closing the India gap and eroding the differentiation an acquirer is paying for.

---

## 13. What Transfers on Acquisition

- Domain (neuralquant.co) and brand assets
- Full source code (monorepo) under NDA / LOI
- All infrastructure accounts (Render, Vercel, Supabase, GCP, LiveKit) — credentials transferred securely
- Data pipeline configurations and cached market data
- Patent application (assignment to acquirer)
- Methodology and backtest baselines
- Operations runbooks and security documentation
- A knowledge-transfer period (suggested 2–4 weeks) to hand over operations

---

## 14. Exclusions / Not Included

- Third-party API keys are **not** transferred; the acquirer provisions its own accounts (FMP, Finnhub, Deepgram, Anthropic, AWS, LiveKit, OpenBB). This is standard and avoids key-abuse liability.
- No customer/user data is represented as included (the platform is pre-revenue with minimal user base).
- No revenue or traffic representations are made.
- Proprietary algorithm internals, agent prompts, and scoring formulas are disclosed only during due diligence under NDA.

---

## 15. Buyer's Due-Diligence Checklist (what you can verify)

- [ ] Live site walk-through (neuralquant.co) — all flagship flows demonstrated live
- [ ] Smoke test suite execution (15/15 passing)
- [ ] Backtest reproduction (baseline stored in Supabase)
- [ ] Patent filing receipt and invention disclosure (under NDA)
- [ ] Service-by-service infra review (under NDA)
- [ ] Security audit documentation (RLS, IDOR, CSP, audit log)
- [ ] Code structure review (under NDA)
- [ ] Methodology page (public, no NDA needed)

---

## 16. Seller Q&A

**"If it's this good, why are you selling it?"**
The founder is mid-way through a Master of Artificial Intelligence programme at UTS Sydney, and bandwidth is genuinely constrained. NeuralQuant has been built to production and IP-protected, but scaling it commercially — sales, partnerships, support, growth — deserves a full-time commercial team. The platform has outgrown what a solo founder in a full-time degree can give it. Selling now, while it is live, validated, and patent-pending, puts it in the hands of an owner who can take it to its full market potential.

**"What happens on Day 1 for the buyer?"**
Nothing has to. The platform is **live and running on Day 1**: 4 cron jobs execute automatically (nightly scoring, market refresh, quantfactor sync, enrichment), the live smoke suite passes **15/15**, and the services self-restart. Running API/infra cost is approximately **$60–80/month** at current usage (Render Pro + Standard, Supabase free tier, GCP free tier, Vercel hobby). The buyer can **literally do nothing on Day 1 and the platform keeps running, scoring, and serving users.** Ownership begins from a position of stability — the work is scaling it, not rescuing it.

---

## 17. Why The Price Is Fair

1. **You are buying time.** 6–12 months of build calendar and the data/voice integration scars that go with it.
2. **You are buying working IP.** A unique scoring methodology and an adversarial multi-agent design that no competitor currently ships, plus a pending patent.
3. **You are buying a de-risked live system**, not a bet on whether it can be built.
4. **The floor is below rebuild cost.** Even at the walk-away price, the acquirer pays less than recreating it would cost in senior labor alone.
5. **Strategic upside is large.** For a brokerage, fund, or fintech, the voice + IRS% + adversarial-trust combination is a differentiated product feature that would take a competitor a full cycle to copy — and the patent raises that cost further.

---

## 18. Next Steps

1. Sign a mutual NDA.
2. Live product demonstration (remote, ~45 minutes).
3. Letter of intent → full source and infra access for due diligence.
4. Knowledge-transfer period post-close.

**Contact:** Satyam Das — satyamdas03@gmail.com

---

*This document is a sales prospectus, not a binding offer. Final terms, including price, are set in a definitive acquisition agreement. Valuations are the seller's estimate and have not been independently appraised; acquirers are encouraged to form their own view during due diligence.*
