# NeuralQuant × Intepat IP — Meeting Prep (Monday)

Prepared 2026-06-13. Internal. This is our strategy brief, not for sharing with Intepat as-is.

---

## 0. Bottom line up front — the 3 things that actually matter

Intepat's documents describe a clean, standard process. Our situation is **not** standard. Three issues dominate everything else, and the meeting must force answers on them:

1. **We have already disclosed publicly.** neuralquant.co is live with no auth wall, there are LinkedIn launch posts (personal + company), public demos, and — most damaging — a **published `/methodology` page that describes PARA-DEBATE (6+1 agents), the IRS% derivation, the consensus mechanism, walk-forward validation, and the data pipeline.** In most jurisdictions, public disclosure *before* filing destroys novelty. India gives **no general grace period** for commercial/marketing disclosure. This is the single biggest threat to patentability and must be the first question we ask.

2. **Software/business-method exclusion — Section 3(k).** Indian law excludes "a mathematical or business method or a computer programme per se or algorithms." A stock-analysis SaaS is squarely in the danger zone. We can only get a patent if we frame a **technical effect / technical contribution** beyond the algorithm. We have one strong candidate (below). IRS% scoring on its own is likely unpatentable in India.

3. **Foreign-filing license — Section 39.** As India-resident inventors, we may **not** file abroad (US/PCT) for an invention made in India without either filing in India first (then waiting 6 weeks) or obtaining a written foreign-filing permit from the Controller. Violation is a criminal offence and can void the patent. If we want US protection (where software is more patentable), the sequencing is legally constrained.

Everything else (forms, fees, timelines) is secondary to nailing these three.

---

## 1. What we would actually patent (ranked candidates)

Do **not** walk in saying "patent NeuralQuant." Patents protect specific technical inventions, not products. Our candidates, ranked by how well they survive Section 3(k):

**A. (STRONGEST) PARA-DEBATE multi-agent verification / metric-correction engine.**
A system where multiple LLM agents independently analyse a security, and an orchestrator **reconciles and auto-corrects each agent's numeric claims against authoritative live data before synthesis** (our logs literally show "Agent metric corrections: current_price 4.97→205.2", "roe 76.3→0.8", "market_cap 97000000000000→4969906990000"). This is framed not as "a way to pick stocks" (business method) but as **a technical solution to a technical problem in AI systems — LLM hallucination / factual unreliability — via real-time cross-source metric reconciliation in a multi-agent pipeline.** Hallucination mitigation is a recognised *technical* problem, which is the doorway through Section 3(k). This is our lead invention.

**B. (MODERATE) Multi-source data-integrity pipeline with provenance tagging.**
The cascade that pulls from FMP → yfinance → snapshot/score caches, tags each field `[VERIFIED]` / `[ESTIMATE]` / `[UNAVAILABLE]`, and forces the LLM to use only verified values. Possible technical-effect angle (data reliability / preventing fabrication), weaker than A but could be a dependent claim or a second filing.

**C. (WEAK in India) IRS% composite scoring methodology.** Likely a mathematical/business method → 3(k) bar. Better protected as a **trade secret** than a patent.

**D. (WEAK) Voice-companion architecture** (LiveKit + persona + page-context narration). Integration/UI; low inventive height. Trade secret / copyright territory.

→ **Recommendation:** lead with **A**, possibly bundle **B** as dependent claims. Keep **C/D** as trade secrets (note: trade secret only works for things we have *not* already published — see §2).

---

## 2. Risk #1 in detail — public disclosure / "bar dates" (IDF Section 2)

India's grace provisions (Patents Act ss. 29-31) are narrow: prior publication that's anticipated only doesn't bar if it was e.g. an unauthorised disclosure, a government-notified exhibition, or a paper read before a learned society — all within 12 months. **A commercial launch, marketing posts, and a public methodology page do NOT qualify.** US is friendlier: a **12-month grace period** runs from the inventor's own first public disclosure, so US may still be reachable if we file within 12 months of first disclosure.

**Action before Monday — reconstruct the disclosure timeline (this is homework Intepat will need):**
- First date neuralquant.co was publicly reachable without login.
- Date the `/methodology` page (PARA-DEBATE, IRS%, consensus, pipeline) went live.
- Dates of each LinkedIn launch post (personal + company), Gamma/carousel posts, any demo videos.
- Any investor/customer demos, the "sale-ready" exit-package screenshots, any public GitHub.
- For each: what was disclosed (marketing-level vs. enough technical detail to enable the invention?).

The key legal question is whether any public artifact was **enabling** (disclosed enough that a skilled person could reproduce the invention). Marketing fluff usually isn't; the **methodology page might be**. We must be honest about this — hiding it weakens or later invalidates the patent (IDF §3.1 explicitly warns against omitting known art, including our own).

**Questions for Intepat:**
- Given the live product + methodology page, is Indian novelty already lost for invention A? For B/C/D?
- Is the US 12-month grace window still open (i.e., is our first disclosure < 12 months ago)? If so, what's the deadline?
- What can still be protected — improvements/unreleased internals not yet disclosed? Continuation/improvement filings?

---

## 3. Risk #2 in detail — Section 3(k) framing

To clear "computer programme per se," the specification must show a **technical effect / technical advancement** beyond running software on a general computer. Our framing for invention A:
- Problem (technical): LLM agents produce factually inconsistent / hallucinated quantitative outputs; naive multi-agent aggregation compounds the error.
- Solution (technical): an orchestration architecture that intercepts each agent's structured numeric assertions, reconciles them against an authoritative real-time data layer, applies bounded corrections, and only then performs weighted consensus synthesis — improving factual reliability of the system output.
- Effect: measurable reduction in factual error rate of generated analysis (we should **quantify** this — IDF §3.7 wants numbers like "corrected N% of agent metric assertions across M runs").

**Question for Intepat:** Does our metric-reconciliation architecture clear 3(k)? What claim structure (system claims vs. method claims) and what level of technical detail give the strongest position? Ask for examples of AI-system patents they've gotten granted in India post-2019 guidelines.

---

## 4. Risk #3 — Section 39 foreign-filing license (sequencing)

If we want US/PCT (recommended for software value), as India residents we must either:
- file the Indian application first, then wait **6 weeks** before filing abroad (no secrecy direction imposed), **or**
- obtain a **Foreign Filing License (FFL)** from the Controller first (Intepat can file this; typically fast).

**Question for Intepat:** confirm we need an FFL or India-first sequencing, and build it into the plan. This is a compliance must, not optional.

---

## 5. Recommended strategy & sequence (our proposal to test with them)

1. **Sign the mutual NDA first.** They offered it. Even though much is public, the orchestrator correction logic, prompts, weighting, and unreleased internals are still confidential — disclose those only under NDA.
2. **Patentability search + written opinion first (₹15,000).** Given the 3(k) risk *and* dense AI-fintech prior art (Danelfin, Bloomberg, Kavout, TipRanks, plus our own methodology page), pay for the search before committing to a ₹50-75k complete draft. Cheap insurance.
3. **In parallel, file a Provisional (priority date) ASAP** for invention A — *if* the search shows a path. A provisional is cheaper (₹25k draft) and buys 12 months to file complete. Speed matters because of the disclosure clock.
4. **Decide India-only vs. India + US/PCT.** If US grace window is open and software value is mostly US-relevant, strongly consider a US provisional too (with FFL/India-first sequencing).
5. **Get DPIIT Startup / Small-Entity recognition** if we don't have it — it collapses statutory fees (Form 28) and unlocks **fast-track examination** (Form 18A, ~1-year grant vs. years).
6. Treat IRS% and voice architecture as **trade secrets** (only the parts not already published).

---

## 6. Cost budget (Individual / Startup / Small-Entity rates; +18% GST on professional fees; 50% advance per step)

Path to a **filed Indian provisional with a priority date** (invention A):

| Step | Professional ₹ | Statutory ₹ (startup) | Notes |
|---|---|---|---|
| Patentability search | 15,000 | nil | 7–10 days |
| Provisional draft | 25,000 | nil | 10–12 days |
| Filing application | 8,000 | 1,600 | up to 30 pp / 10 claims |
| **Subtotal** | **48,000** | **1,600** | |
| GST @18% on prof | 8,640 | — | |
| **≈ Total to priority date** | | **≈ ₹58,240** | rough; statutory subject to change |

Then within 12 months, **complete specification** (₹50,000 prof after provisional + filing) and later **RFE** (₹5,000 prof + ₹4,000 statutory, or fast-track ₹5,000 + ₹8,000). Renewals from year 3 (startup: ₹800–₹8,000/yr statutory + ₹5,000–8,000 prof). Office-action responses billed ₹2,000/hr.

**Ballpark to a *granted* India patent over ~3–4 yrs (startup rates): roughly ₹2–3.5 lakh** all-in incl. drafting, prosecution, one FER response, GST — heavily dependent on objections and whether we add US/PCT (US adds materially more). Confirm a fixed-fee or capped estimate with them.

---

## 7. Questions to ask Intepat (in priority order)

1. Given our live product + public methodology page, **is Indian novelty already barred** for the multi-agent verification engine? For the other candidates?
2. Is the **US 12-month grace window** still open from our first disclosure — what's the exact deadline?
3. Does the **metric-reconciliation / hallucination-mitigation architecture clear Section 3(k)**? Best claim framing? Show us granted AI-system examples.
4. **Section 39** — do we need a foreign-filing license or India-first sequencing for US/PCT?
5. **Provisional-first vs. search-first** — what order do you recommend given the disclosure clock?
6. Do we qualify for **DPIIT startup / small-entity** status and **fast-track (Form 18A)**? Help us get it.
7. Is this **one patent or a family** (verification engine; data-integrity pipeline)? What's the filing strategy?
8. **Section 8** ongoing foreign-application disclosure obligations (Form 3) — what do we commit to?
9. Fixed/capped fee for the full path to grant (India; and India+US option)?
10. Send the **mutual NDA** today so we can disclose internals.

---

## 8. To prepare / bring before Monday

- [ ] **Disclosure timeline** (the dated list in §2) — most important homework.
- [ ] **Draft IDF** (their `Intepat Invention Disclosure Form (IDF).docx`) focused on invention A: §3.1 old way (existing AI-research tools and why their outputs are unreliable), §3.2 new way (one paragraph), §3.3 how (orchestrator architecture, agent roster, reconciliation step-by-step), §3.4 secret sauce (the metric-correction + bounded reconciliation + consensus), §3.7 advantages (quantify the correction rate). Use the AI/ML checklist (IDF §100-106): model(s) used, data sources + licensing, pipeline, eval metrics.
- [ ] **Prior-art list** we know: Danelfin, Bloomberg/Bloomberg GPT, Kavout, TipRanks, Seeking Alpha, BloombergGPT paper, any "multi-agent LLM finance" arXiv papers, and **our own `/methodology` page URL** (disclose it).
- [ ] **Third-party dependencies** (IDF §5.2): we use Anthropic Claude, AWS Bedrock, FMP, yfinance, LiveKit, ElevenLabs, Deepgram, Sarvam — list licenses; note none are in the *inventive step* itself (the reconciliation logic is ours), but be ready to discuss.
- [ ] **Inventor list** (IDF §5.3): every person who contributed to *conception* of the verification engine, with contribution %. **Applicant** (IDF §5.4) = the NeuralQuant legal entity if incorporated; else the inventor(s). Decide entity name + incorporation status.
- [ ] **Development stage** (IDF §4.3): "Tested & verified — deployed in production."
- [ ] Note the product is **being positioned for sale (v4.1.0 sale-ready)** — a filed/pending patent materially strengthens buyer diligence and valuation. This is a reason to move fast even if grant is uncertain; "patent pending" has standalone commercial value.

---

## 9. Reference cheat-sheet (from their docs)

**Firm:** Intepat IP Services Pvt Ltd, Bengaluru (JP Nagar). Founded 2009 by **Senthil Kumar** (Registered Patent Agent; PGDIPRL NLSIU; MS Instrumentation; ~2 decades, electronics/comms/AI/blockchain). Co-founder **Kalaivani** (BD/portfolio ops). 16+ yrs, 30+ jurisdictions, thousands of filings. Strengths incl. **software, AI, blockchain** — good fit. Rep experience: deep-tech drone portfolio, growth-stage AI FTO + portfolio restructuring, university tech-transfer. Contact: contact@intepat.com, +91-80-42173649. Patent intake: patent@intepat.com.

**Key statutory deadlines (post 15-Mar-2024 rules):**
- Provisional → Complete: **12 months** (Section 9, no extension).
- Publication: 18 months (or ~1 month via Form 9 early-publication).
- **RFE: 31 months** from priority/filing (Form 18; Form 18A expedited).
- Response to FER: **6 months** from FER, +3 (Form 4).
- Pre-grant opposition reply: 2 months. Post-grant opposition: within 1 yr of grant.
- Renewals from year 3 (Section 53). Form 27 working statement every 3 FYs.
- Appeal to High Court: 3 months (IPAB abolished 2021).

**Forms:** 1 (application), 2 (spec), 3 (foreign-app statement/Section 8), 5 (inventorship), 9 (early pub), 18/18A (RFE/expedited), 26 (PoA), 27 (working), 28 (startup/small-entity).

**Their payment terms:** 50% advance per step, 50% on completion. GST 18% on professional fees only (statutory exempt). Search 7–10 days; drafting 10–12 days; provisional gives 12 months.

---

## 10. One-line framing for the meeting

"We have a production AI system with a specific technical mechanism — multi-agent LLM output reconciliation against live authoritative data to suppress hallucination — that we believe is our patentable core. We've already launched publicly, so our first questions are about novelty/grace windows and Section 3(k) viability before we spend on drafting. We want a search + opinion first, an NDA up front, and a fast provisional if there's a path."
