# NeuralQuant + StockEdge — Strategic Partnership & Acquisition Prospectus

**Prepared:** June 2026  
**From:** Satyam Das (satyamdas03@gmail.com), Founder, NeuralQuant  
**To:** StockEdge Fintech Pvt Ltd — Vineet Patawari (CEO), Vivek Bajaj (MD), and the StockEdge leadership team  
**Subject:** Proposed 12-month exclusive AI-research pilot + call option to acquire NeuralQuant  
**Classification:** Strictly confidential — transmit only under signed mutual NDA  

---

## 1. Executive Summary

NeuralQuant is a production-grade, multi-agent AI stock-research platform covering the US and India equity markets (~949 stocks). It is **live and operational today** at `neuralquant.co` — not a prototype, not a slide deck.

StockEdge has built India's largest retail research distribution engine: 4M+ registered users, SEBI-registered Research Analyst and Investment Adviser licenses, and a publicly stated ambition to create a **"Bloomberg-for-Bharat"** ecosystem for Indian retail investors. NeuralQuant has built the **reasoning layer** that turns data into defended, risk-aware investment conclusions — through a multi-agent adversarial committee, a regime-adaptive quantitative scoring engine, and voice-native interfaces.

This proposal is not a request for a ₹3 Crore cash acquisition on Day 1. It is a **low-risk, gated partnership**:

- **12-month exclusive pilot:** embed NeuralQuant's PARA-DEBATE™ + IRS% engine inside StockEdge Pro / Club / Investment Cases.
- **Small upfront license fee** to cover integration and exclusivity.
- **Revenue-share kicker** tied only to the incremental subscribers the AI tier converts.
- **Call option:** StockEdge can acquire the IP, codebase, and domain once the pilot proves conversion.

This structure respects StockEdge's capital discipline, protects Vivek Bajaj's brand authority, and puts the engine under StockEdge's existing SEBI RA/IA compliance umbrella from Day 1.

---

## 2. Why NeuralQuant + StockEdge Makes Strategic Sense

### 2.1 StockEdge's stated ambition is NeuralQuant's exact output

Vivek Bajaj has repeatedly said his life goal is to build a Bloomberg-like ecosystem for Indian retail investors. Bloomberg provides data; NeuralQuant provides the **reasoning and risk discipline** on top of data — bull case, adversarial bear case, regime-aware scoring, and position-sizing guidance. The combination gives StockEdge a genuine "full stack from data to decision."

### 2.2 Four gaps in StockEdge's current product that NeuralQuant fills

| StockEdge gap today | NeuralQuant capability | Why it matters to StockEdge |
|---|---|---|
| No LLM "Ask AI" natural-language research assistant | Ask Morgan + PARA-DEBATE conversational agents | Turns static scans into interactive "why this stock?" answers |
| No adversarial / steelmanned risk section | PARA-DEBATE™ 6+1 agent committee with mandated BEAR | Produces the counter-argument section StockEdge currently lacks |
| No regime-aware position-sizing metric | IRS% (Investment-Ready Score) | Complements RS55/RSI with macro-adaptive conviction |
| No US equity coverage | US + India dual-market pipeline | Niche differentiator for HNIs and Club subscribers |

### 2.3 Revenue synergy paths inside StockEdge's existing business

| StockEdge revenue line | How NeuralQuant strengthens it |
|---|---|
| **StockEdge Pro / Premium** (~₹11,989/yr) | Bundle PARA-DEBATE reports for NSE 200 as a higher-tier "Pro AI" upsell |
| **StockEdge Investment Cases / smallcase** (₹3,000–12,000/yr) | Use IRS% + regime output to justify rebalancing in model portfolios |
| **StockEdge Club** (₹23,989/yr) | Live "Ask the AI Analyst" sessions on audience-requested stocks |
| **Kotak Neo / B2B distribution** | Resell the engine to broker partners, mirroring the 2021 Kotak partnership model |

### 2.4 Regulatory complementarity (the hidden asset)

StockEdge holds both SEBI registrations that NeuralQuant lacks:

- **Research Analyst (RA):** INH300007493
- **Investment Adviser (IA):** INA000017781

By embedding NeuralQuant as a **research-analysis tool under StockEdge's existing licenses**, the output is immediately SEBI-compliant — with StockEdge's compliance officer sign-off, disclaimers, and no guaranteed-return language. NeuralQuant does not need its own RA/IA registration.

---

## 3. What NeuralQuant Is

### 3.1 At a glance

| Dimension | Scale |
|---|---|
| Live site | `neuralquant.co` (Vercel, auto-deployed) |
| API | `neuralquant.onrender.com` (FastAPI, v4.1.3) |
| Backend routers | 33 |
| Web pages | 38 |
| Running services | 7 (4 Render, 1 Vercel, 1 GCP, 1 Supabase) |
| Markets | US + India |
| Stock universe | ~949 stocks (502 India + 447 US) |
| AI agents | 8 distinct agents |
| Live voice interfaces | 2 (voice PM + ambient companion) |
| Production tests | 186 backend tests passing, 15/15 live smoke suite |
| Patent status | Provisional application filed (India), PCT contemplated |

### 3.2 Flagship capabilities (all live today)

- **PARA-DEBATE™ adversarial research committee** — 6 specialist agents (Macro, Fundamental, Technical, Sentiment, Geopolitical, Adversarial BEAR) + Head Analyst synthesis. Every stock conclusion is stress-tested by a steelmanned bear case before release. Designed to prevent consensus herding and hallucination.
- **IRS% (Investment-Ready Score)** — a five-factor composite score combining quality (Piotroski F-Score), momentum (Jegadeesh-Titman), value, low-volatility, and HMM regime-adaptive weighting. India adds NSE Bhavcopy `delivery_pct` as a sixth liquidity-conviction signal — unique to Indian market microstructure.
- **HMM regime detection** — Hidden Markov Model classifying market state into Risk-On / Risk-Off / Bear / Late-Cycle, dynamically reweighting factor exposure.
- **Ask Morgan** — written AI research analyst with live price injection, clarification questions, and numeric reconciliation against a `[VERIFIED]` data layer.
- **Veronica + QuantAstra** — two live voice agents (portfolio manager and ambient page-aware companion) via LiveKit, Deepgram STT, LiveKit Inference TTS, and Anthropic/Bedrock LLMs.
- **Hermes live trading dashboard** — real-time paper-trading matrix with equity curve, trade tape, and strategy reflection SSE stream.

### 3.3 Validation & track record

| Metric | Result |
|---|---|
| Q1 FY27 India backtest benchmark | NIFTY50: −6.38% |
| Alpha vs NIFTY50 | **+12.69% to +14.83%** |
| Hit rate | **87–91%** |
| Live smoke suite | 15/15 passing |
| Backtest reproducibility | Baseline stored in Supabase |

---

## 4. The Proposed Deal Structure

### 4.1 Primary recommendation: 12-month exclusive licensing pilot + call option

| Component | Term |
|---|---|
| **Upfront license fee** | **₹50 lakh** for exclusive India-market integration rights to PARA-DEBATE™ + IRS% |
| **Universe covered** | NSE 200 + BSE 500 (expandable by mutual agreement) |
| **Revenue share** | **15% of incremental ARR** from any new "AI Research" / "Pro AI" / "Club AI" tier launched using the engine |
| **Revenue-share cap** | **₹2 Crore** over 24 months |
| **Pilot gates** | 10,000 MAU of the AI feature; 1,000 paid upgrades attributable to the AI tier; avg report latency < 30 seconds |
| **Call option** | StockEdge may acquire NeuralQuant IP, codebase, and `neuralquant.co` domain for a pre-agreed **₹2.5 Crore** within 24 months of pilot start |
| **License fee credit** | The ₹50 lakh upfront fee is credited against the call-option purchase price |
| **SEBI wrapper** | All AI outputs labeled "Research analysis powered by NeuralQuant, reviewed under StockEdge RA INH300007493" with required disclaimers |

### 4.2 Why this structure fits StockEdge specifically

- **Low upfront cash.** ₹50 lakh is less than the cost of two senior engineers for a year — minimal balance-sheet impact for a company with FY24 PAT of ₹23 lakh.
- **Aligned incentives.** The bulk of NeuralQuant's compensation is a revenue share on the new AI tier. We only earn meaningfully if StockEdge users actually pay for it.
- **Risk reversal.** StockEdge does not bet on unproven technology. The pilot generates conversion data; the call option is exercised only if the data justifies it.
- **Regulatory safety.** The engine sits under StockEdge's existing RA/IA licenses, avoiding a fresh SEBI registration process.
- **IP protection.** Exclusivity during the pilot prevents NeuralQuant from licensing the same engine to a competing Indian retail platform while StockEdge validates it.

### 4.3 Fallback structures (if StockEdge prefers a different shape)

| Structure | Mechanics | When it suits StockEdge |
|---|---|---|
| **Strategic investment + distribution** | ₹5–8 Crore for 15–20% stake; exclusive integration; board-observer seat | If StockEdge wants deeper alignment without full acquisition risk |
| **Acqui-hire / IP buyout** | ₹1.5–2 Crore cash for team + codebase; founder stays 6–12 months as technical advisor | If StockEdge wants to absorb the team and fold the IP in-house quickly |
| **Full acquisition with earnout** | ₹1 Crore upfront + ₹2 Crore tied to AI-tier conversions over 18 months | If StockEdge is confident in immediate product-market fit |
| **Stock swap** | NeuralQuant equity swapped into KIPL shares | Only if a near-term IPO path is credible (low preference) |

---

## 5. SEBI-Compliant Integration Specification

### 5.1 Regulatory premise

StockEdge is the licensed entity. NeuralQuant is the technology provider. The AI engine produces **research analysis**, not personalized investment advice. Final labeling, disclaimers, and any "buy/sell/hold" language are controlled by StockEdge under its RA/IA registrations.

### 5.2 Output labeling (every user-facing report)

```
Research analysis powered by NeuralQuant.
Reviewed under StockEdge Research Analyst registration INH300007493.
This is not investment advice. Past performance does not guarantee future results.
Consult a SEBI-registered investment adviser before acting.
```

### 5.3 Compliance controls

| Control | Implementation |
|---|---|
| No guaranteed-return claims | Hard-coded disclaimer on every AI-generated output |
| Principal-officer sign-off | StockEdge compliance officer reviews and approves the AI-tier output template before launch |
| Record-keeping | All AI reports logged with timestamp, ticker, input signals, and version hash |
| Segregation of research vs advisory | AI tier labeled "Research" only; personalized advisory remains with StockEdge IA team |
| MITC disclosures | Included in AI-tier subscription terms |

### 5.4 Why this matters to Vivek Bajaj personally

Vivek has been publicly vocal about SEBI's crackdown on unlicensed finfluencers and the importance of RA/IA registration. Positioning NeuralQuant as a **research tool under StockEdge's existing licenses** directly addresses his likely first objection: "Is this SEBI-compliant?"

---

## 6. Integration Plan (12-Month Pilot)

### 6.1 Phase 1: Embed (Months 1–2)

- StockEdge provides API/integration sandbox.
- NeuralQuant exposes a private `/partners/stockedge` endpoint returning PARA-DEBATE + IRS% output for agreed NSE/BSE tickers.
- StockEdge compliance team reviews output template and disclaimers.
- Soft launch to internal StockEdge analysts and Club mentors.

### 6.2 Phase 2: Pilot Tier Launch (Months 3–6)

- Launch "StockEdge Pro AI" or "Investment Cases AI Rationale" feature.
- Start with top 50 NSE stocks; expand to NSE 200 by Month 4.
- Track: MAU, paid upgrades, report-generation latency, user feedback.
- NeuralQuant provides monthly conversion and technical reports.

### 6.3 Phase 3: Scale Decision (Months 7–12)

- If gates met: expand to BSE 500, integrate into Club live sessions, add US-stock rationale for HNI tier.
- If gates not met: either adjust scope or terminate exclusivity; StockEdge retains learnings, NeuralQuant retains IP.
- By Month 12: StockEdge decides whether to exercise the call option.

### 6.4 Technical handover

- Knowledge-transfer period: **2–4 weeks** post-LOI / pilot start.
- Documentation provided: `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/ASSET_INVENTORY.md`, `docs/BUG_HISTORY.md`.
- Third-party API keys: StockEdge provisions its own accounts; NeuralQuant assists with migration.

---

## 7. Outbound Materials

### 7.1 LinkedIn cold message to Vineet Patawari (CEO)

```
Hi Vineet — long-time admirer of what you and Vivek have built at StockEdge.

We have built an adversarial AI research committee (PARA-DEBATE) that forces a
bull-vs-bear debate before any stock conclusion — exactly the "noise removal"
StockEdge stands for. It is live with dual-market US+IN coverage, an India-specific
IRS% score, and a Q1FY27 backtest showing +12.69% to +14.83% alpha vs NIFTY50.

I am not looking for a cash-heavy acquisition day one. I would love to explore a
12-month pilot inside StockEdge Pro that converts your 4M users into AI-tier
subscribers, with an option to buy the IP later.

Worth a 15-minute call?
```

### 7.2 LinkedIn cold message to Vivek Bajaj (MD)

```
Hi Vivek — your Bloomberg-for-Bharat vision is why I started NeuralQuant.

We built the reasoning layer that turns market data into defended conclusions:
a quantified adversarial committee, regime-adaptive scoring, and an India-specific
IRS% metric. Live at neuralquant.co, 949 tickers, 15/15 smoke tests passing.

I would welcome the chance to show you how it could sit inside StockEdge's
existing SEBI RA/IA framework as a 12-month pilot — low risk, aligned incentives,
and only an acquisition if your users actually pay for it.

May I send a one-page memo?
```

### 7.3 Email subject line options

1. "12-month AI research pilot for StockEdge Pro — low upfront, aligned upside"
2. "NeuralQuant + StockEdge: a Bloomberg-for-Bharat reasoning layer"
3. "Adversarial AI research engine — 12.69–14.83% alpha vs NIFTY50 — pilot proposal"

---

## 8. 10-Minute Demo Agenda

| Time | What to show |
|---|---|
| 0:00–0:30 | Live site, 949 tickers, 15/15 smoke tests, version v4.1.3 |
| 0:30–2:30 | Ask Morgan: natural-language question on RELIANCE / TCS / HDFCBANK |
| 2:30–5:30 | PARA-DEBATE on the same stock — 6 agents, mandated bear, consensus, risk section |
| 5:30–7:00 | IRS% / screener — rank NSE 200, show regime detection shifting factor weights |
| 7:00–8:30 | Backtest evidence: Q1FY27 alpha +12.69–14.83%, hit rate 87–91% |
| 8:30–10:00 | Proposed pilot: integration, SEBI umbrella, ₹50L upfront + 15% revenue share + call option |

---

## 9. Negotiation Talking Points for Vivek Bajaj

### 9.1 Five sentences that will resonate

1. "You have built the largest retail research distribution engine in India; we have built the reasoning layer that turns your scans into 'why' — together you own the full stack from data to decision."
2. "PARA-DEBATE is not a chatbot; it is a quantified adversarial committee that forces the bear case before any buy idea reaches your user — that protects your brand from bad calls."
3. "Your RS55 and RSI already teach discipline; IRS% adds regime-adaptive position sizing so your users know when the macro wind is against them."
4. "You do not need to spend 24–37 senior engineer-months and ₹1.1 Cr+ in labor to recreate this; it is live today and can be embedded under your existing SEBI licenses."
5. "We are not asking you to bet the company on a ₹3 Cr acquisition — we are asking for a 12-month pilot, and you only buy the IP if your users actually pay for it."

### 9.2 Objections Vivek / Vineet will raise — and answers

| Objection | Answer |
|---|---|
| "Why can't we build this ourselves?" | "You can build screens, but a reliable adversarial multi-agent system with hallucination guards, numeric reconciliation, and a live dual-market data pipeline has taken 80+ iterations and 126 documented bug cycles. The rebuild cost is 24–37 senior engineer-months plus integration scars. License it first, validate conversion, then decide." |
| "Is this SEBI-compliant?" | "NeuralQuant does not hold RA/IA licenses; StockEdge does. We embed the engine as a research-analysis tool under your existing registrations, with your compliance officer's sign-off, disclaimers, and no guaranteed-return language." |
| "You have no revenue. Why pay anything?" | "You are not paying for revenue — you are paying for time-to-market and IP protection. The pilot is ₹50 lakh, less than two senior engineers for a year, and most of our compensation is a 15% revenue share on the new AI tier." |
| "Will this dilute my brand as the expert?" | "The AI is positioned as augmenting your momentum/RS framework, not replacing it. PARA-DEBATE produces the counter-argument and risk sections your analysts already believe in — faster and at scale." |
| "What if the pilot doesn't convert?" | "Your downside is capped at ₹50 lakh plus integration cost. You keep the learnings. If gates are not met, exclusivity terminates and you walk away — no acquisition obligation." |

---

## 10. Engineering Investment (Rebuild Cost Reference)

Even under a licensing/acqui-hire structure, the rebuild cost is the anchor for why the upfront fee is modest.

| Subsystem | Senior eng-months |
|---|---|
| Backend API (33 routers, auth, quotas, sessions) | 4–6 |
| PARA-DEBATE multi-agent engine | 3–4 |
| Ask Morgan written analyst | 2–3 |
| Quant scoring + IRS% + HMM regime | 2–3 |
| Data pipeline (6 sources, US+IN parity) | 3–4 |
| Voice PM + ambient companion | 3–5 |
| Next.js web app (38 pages, PWA) | 3–4 |
| Live trading dashboard | 1–2 |
| DevOps, security, testing | 3–5 |
| **Total** | **24–37 senior eng-months** |

At India senior rates (₹2–3L/mo): **₹48L–1.1Cr** in pure labor.  
At US senior rates ($12–18k/mo): **$290k–$665k (₹2.4–5.6Cr)**.  
That excludes calendar time, integration scars, data-source failures, voice-stack stabilization, and security hardening.

The **₹50 lakh pilot fee** is a fraction of the cost to recreate even one subsystem.

---

## 11. What Transfers / Exclusions

### Transfers (on exercise of call option or IP buyout)

- Domain (`neuralquant.co`) and brand assets
- Full source code (monorepo) under NDA / LOI
- Infrastructure accounts (Render, Vercel, Supabase, GCP, LiveKit) — credentials transferred securely
- Data pipeline configurations and cached market data
- Patent application — assignment to StockEdge
- Methodology and backtest baselines
- Operations and security documentation
- Knowledge-transfer period (2–4 weeks)

### Exclusions

- Third-party API keys (StockEdge provisions its own accounts)
- Customer/user data (platform is pre-revenue)
- Revenue or traffic representations
- Proprietary algorithm internals disclosed only under NDA during due diligence

---

## 12. Due-Diligence Readiness Checklist

Before the first serious conversation, the following items will be completed and available:

- [x] Live product demonstration ready (neuralquant.co)
- [x] 15/15 smoke suite passing
- [x] Backtest baseline stored in Supabase (Q1FY27)
- [ ] Signed mutual NDA template
- [ ] Patent filing receipt + Form 31 grace-period filing status
- [ ] PARA-DEBATE™ trademark status confirmation
- [ ] One-page "StockEdge + NeuralQuant" strategic memo
- [ ] 12-month pilot term sheet draft
- [ ] SEBI-compliant output-labeling spec
- [ ] Clean repo + CI lint fixed + pending migrations applied
- [ ] FMP key rotated + Render env vars documented

---

## 13. Seller Q&A

**"Why are you selling now?"**  
I am mid-way through a Master of Artificial Intelligence at UTS Sydney. NeuralQuant has been built to production and IP-protected, but scaling it commercially — enterprise sales, partnerships, support — deserves a full-time commercial team. A partnership with StockEdge puts the technology in the hands of the team best positioned to take it to 4M+ users.

**"Why StockEdge?"**  
StockEdge is the only Indian retail platform with both the distribution (4M users), the SEBI licenses (RA + IA), and the founder vision (Bloomberg-for-Bharat) that aligns with what NeuralQuant does. No other target offers all three.

**"What happens on Day 1 of the pilot?"**  
NeuralQuant exposes a private partner API, StockEdge's compliance team reviews output templates, and integration begins against a fixed universe. The live platform keeps running autonomously regardless — 4 cron jobs execute, 15/15 smoke tests pass, and all 7 services remain live.

---

## 14. Next Steps

1. **Sign a mutual NDA** — no source code, architecture detail, or patent specifics shared before this.
2. **15-minute product call** — demo the live platform on a top NSE stock.
3. **Strategic memo + pilot term sheet** — shared for internal StockEdge review.
4. **Letter of Intent** — kicks off the 12-month exclusive pilot and integration planning.
5. **Pilot launch** — Months 1–2 embed; Months 3–6 pilot tier; Months 7–12 scale decision.

**Contact:** Satyam Das — satyamdas03@gmail.com

---

*This document is a strategic partnership proposal and acquisition prospectus, not a binding offer. Final terms are set in a definitive agreement. Valuations and projections are the seller's estimates and have not been independently appraised; StockEdge is encouraged to form its own view during due diligence.*
