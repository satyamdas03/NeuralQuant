# NeuralQuant Verify — Master Plan

**Derived from:** `NEURALQUANT_MASTER_REPORT_AUDIT_GB`  
**Purpose:** Convert the audit's strategic recommendation into an end-to-end execution roadmap.  
**Assumption:** 15 hours/week founder/operator bandwidth.  
**Target:** B2B verification/audit layer for licensed research publishers (SEBI RAs, US newsletters, small RIAs).

---

## 0. North Star

Stop selling to retail investors under the NeuralQuant name. Pivot to **NeuralQuant Verify**, a regulated-market-compliant verification and audit layer that licensed research publishers use to check AI-drafted and human-drafted research notes before publication. Every feature must produce evidence a compliance officer, auditor, or regulator can review.

---

## Part A: Problems We Must Solve

| # | Problem | Why It Blocks Us | Consequence If Ignored |
|---|---|---|---|
| 1 | **Regulated advice claims without a licence** | Site/LinkedIn use "Strong Buy", "Avoid", "recommendations", "90% accuracy" | SEBI RA/IA enforcement, SEC RIA scrutiny, ASIC RG 255 action |
| 2 | **Verification produces no evidence** | PARA-DEBATE only regex-checks ~13 fields; corrections go to logs, not an audit log | Licensees cannot show regulators a record of checks |
| 3 | **No reproducible scoring contract** | `composite_score` is ×10 scale; consumed as 0–1 in some places, 1–10 in others | Performance and backtest numbers are not trustworthy |
| 4 | **Performance/backtest claims are not reproducible** | Hard-coded `_q1fy27_baseline()` fallback; no transaction costs/delisted handling | Marketing claims become liability; no honest public evaluation |
| 5 | **Data licensing and source opacity** | Yahoo-impersonating paths via `yf_guard`/`curl_cffi`; no provenance tags | Licensing breach; licensees cannot defend source lineage |
| 6 | **Technical bloat for wrong use case** | Voice, Hermes, mobile, `torch` in API install drive cost/complexity | Burn is too high for a pivot with no paying customers yet |
| 7 | **Building without validated demand** | Previous phases added features before confirming who would pay | Risk of another product nobody buys |
| 8 | **Unclear patent/IP ownership** | Provisional filed solo, but QuantAlpha JV and Financial Simplicity employment contract may have claims | Any sale, licence, or funding is blocked until clean |

---

## Part B: What Must Stop Immediately (Week 0 — Before Day 1)

| # | Stop Doing | Replace With | Owner | Done When |
|---|---|---|---|---|
| B.1 | B2C subscription charges under NeuralQuant name | Suspend Stripe plans; add "not for retail advice" gate | Product/Finance | Stripe products archived or hidden |
| B.2 | Public "Buy / Sell / Strong Buy / Avoid" labels | Neutral model buckets (e.g., "Top quintile on IRS") or remove | Frontend | No advice labels on public pages |
| B.3 | "90% accuracy" / "recommendations" / performance marketing on LinkedIn/site | Remove or replace with methodology-only copy | Marketing | LinkedIn + site copy scrubbed |
| B.4 | Personalized advice flows (portfolio profiler, Ask Morgan "what should I do", sell-signal panels, Veronica advice path) | Disable behind flags or remove | Frontend/API | Routes behind `ENABLE_ADVICE=false` or deleted |
| B.5 | New voice worker, Hermes, mobile features | Freeze; only keep alive for cash if needed | Engineering | No new commits in these modules |
| B.6 | Yahoo-impersonating user-facing data paths | Route user-facing data through licensed/FMP/EDGAR/FRED/bhavcopy only, with provenance | Engineering | No `yf_guard` output on public endpoints |
| B.7 | Hard-coded quarterly backtest fallback (`_q1fy27_baseline`) | Remove fallback; return unavailable if data missing | Engineering | `/testing/quarterly/public-results` has no synthetic baseline |

---

## Part C: Phased Roadmap

### Phase 0 — Stop the Bleed + Validate Demand (Days 1–30)
**Goal:** Clean up regulatory exposure and confirm licensed publishers will pay for a verification layer before writing MVP code.

**C0.1 Risk & Legal Hygiene (Days 1–7)**
- C0.1.1 Read Financial Simplicity employment contract; identify clauses on IP, side projects, conflict, non-compete.
- C0.1.2 Read QuantAlpha JV documents; identify claims on NeuralQuant IP, code, or patent.
- C0.1.3 List open questions for a lawyer; book a 1-hour consult if any clause is ambiguous.
- C0.1.4 Verify InPASS application status for Indian provisional 202631083313.
- C0.1.5 Confirm no Australian licensees are contacted until employment conflict is cleared.

**Deliverables:**
- `docs/verify/IP_OWNERSHIP_CHECKLIST.md` — findings and open questions.
- `docs/verify/INPASS_STATUS.md` — screenshot or note of application status.
- Decision: proceed / pause / restructure ownership.

**C0.2 Product & Site Cleanup (Days 1–14)**
- C0.2.1 Scrub site copy for advice/accuracy/recommendation language.
- C0.2.2 Add "Information only. Not investment advice." notice for IN/US/AU visitors.
- C0.2.3 Disable or remove portfolio profiler, sell-signal panels, Ask Morgan personalized action path, Veronica action path.
- C0.2.4 Remove or hide public `/testing/quarterly/public-results` and methodology backtest numbers.
- C0.2.5 Remove `_q1fy27_baseline()` fallback.
- C0.2.6 Ensure any remaining score displays use the neutral bucket label map (no Buy/Sell).

**Deliverables:**
- PR: `chore(verify): remove retail advice claims and backtest fallbacks`
- Updated `docs/OPERATIONS.md` section on public claims.
- Screenshot audit of homepage, pricing, methodology, LinkedIn posts.

**C0.3 Cost & Hosting Triage (Days 3–10)**
- C0.3.1 Audit Render, Railway, GCP, Vercel, LiveKit, ElevenLabs, FMP, Stripe, Supabase monthly burn.
- C0.3.2 Pause or scale down: voice worker, Hermes Railway service, mobile builds, GPU/ML-heavy workers.
- C0.3.3 Remove `torch` from the API install path if not strictly required.
- C0.3.4 Decide whether FMP Premium is still needed for Verify MVP (likely yes for US reference data, but check terms).

**Deliverables:**
- `docs/verify/BURN_DOWNSIZE_PLAN.md` — before/after costs.
- PRs for worker pauses and dependency slimming.

**C0.4 Prospect Research (Days 5–14)**
- C0.4.1 Build a target list of 40 prospects:
  - 20 SEBI-registered research analysts from SEBI's public intermediary register, preferably those whose notes look AI-drafted.
  - 20 US newsletter publishers or small RIAs.
- C0.4.2 For each prospect, note: name, firm, registration number, public notes, suspected AI use, email/LinkedIn.
- C0.4.3 Prioritize by: likelihood of AI drafting, note volume, public errors found, size.

**Deliverable:**
- `docs/verify/PROSPECT_LIST_40.md`

**C0.5 Outreach & Interviews (Days 8–28)**
- C0.5.1 Send 40 personalized messages offering a **free verification report** on one of their published notes.
- C0.5.2 Hold 15+ short interviews with the person who signs off on research.
- C0.5.3 Demo artefact: run the existing PARA-DEBATE gate + a quick LLM extractor script over 20 public AI-style notes; save results as CSV/PDF "verification report" sample.
- C0.5.4 Send 3 free verification reports to warm prospects.

**Interview script (ask exactly these):**
1. How do you produce a research note today? Where does AI come in?
2. Tell me about the last time a wrong number got published. What happened?
3. How do you meet SEBI/SEC/ASIC AI-use disclosure and responsibility rules? Who checks?
4. How many minutes per note go to checking numbers?
5. What would a record of checks need to show your compliance officer or auditor?
6. Would you run 10 of your next notes through this, free, if I send you the report?
7. If it saved X minutes per note, what would you pay per month? (Then anchor $49 and $199.)
8. Would you rather have the research produced for you under your name? (Tests Direction B fallback.)

**Deliverables:**
- `docs/verify/INTERVIEW_NOTES.md` — exact quotes.
- `docs/verify/VERIFICATION_REPORT_SAMPLES/` — sample PDFs/CSVs.
- 3 warm prospects with free reports delivered.

**C0.6 Label 100 Claims for Evaluation Corpus (Days 15–30)**
- C0.6.1 Collect 100 numeric claims from real LLM drafts and known failures (₹4.97, $97T, beta 202).
- C0.6.2 For each claim, label: field (P/E, price, target price, revenue growth, market cap, etc.), claimed value, correct reference value or "unavailable", source, tolerance, and whether the current gate catches it.
- C0.6.3 Store as `data/verify/evaluation_corpus_v1.jsonl`.

**Deliverable:**
- 100-claim labelled corpus committed.

**Phase 0 Gate (Day 30):**
Proceed to Phase 1 (Direction A) **only if all** of:
- ≥15 conversations with licensed publishers held.
- ≥5 publishers use LLMs in drafting.
- ≥3 publishers agree to pilot with real notes.
- ≥1 publisher names a price of $49/month or more unprompted.

**Gate Decisions:**
- If pilots exist but ≥2 want research produced for them → switch to **Direction B** (white-label engine).
- If neither A nor B demand exists → extend 1 more week; if still no demand, move to **Phase F+I** (hygiene + asset sale + services bridge).

---

### Phase 1 — Verify MVP Core (Days 31–60)
**Goal:** Build a separate `verify` FastAPI service with 10 must-have features, co-designed with 2–3 design partners.

**P1.0 Architecture Decision (Day 31)**
- P1.0.1 Create `apps/verify/` as a separate deployable FastAPI service.
- P1.0.2 Reuse existing connectors (`packages/data`) for FMP, EDGAR, FRED, NSE bhavcopy; do NOT reuse user-facing Yahoo paths.
- P1.0.3 Decide database: new Postgres schema in existing Supabase project, separate from `score_cache`.
- P1.0.4 Define service boundaries: `verify` owns claim extraction, reference resolution, decision engine, audit log, certificates, API keys, billing.

**P1.1 M1 — Universal Numeric-Claim Extractor (Days 31–38)**
- P1.1.1 Build `verify/extractor.py` that takes text and returns structured claims: value, unit, currency, period, entity, field.
- P1.1.2 Use LLM structured output first, then deterministic normalization.
- P1.1.3 Cover at minimum: price, P/E, revenue growth, EPS growth, target price, market cap, beta, dividend yield, 52-week high/low, date references.
- P1.1.4 Add tests against the 100-claim corpus; report recall.

**Deliverable:**
- `POST /verify/extract` endpoint.
- PR: `feat(verify): universal numeric-claim extractor`
- Recall metric on evaluation corpus.

**P1.2 M2 — Provenance-Tagged Reference Store (Days 39–45)**
- P1.2.1 Build `verify/reference_store.py` that resolves each claim type to a canonical reference value.
- P1.2.2 For each reference value store: source, retrieval timestamp, as-of date, licence class (FMP, EDGAR, FRED, bhavcopy, BYO).
- P1.2.3 India first: NSE bhavcopy + filings.
- P1.2.4 US: EDGAR, FRED, FMP (confirm licence allows redistribution/redisplay in this context).
- P1.2.5 BYO reference source: CSV upload or API with schema mapping.

**Deliverable:**
- `verify/reference_store` module.
- `POST /verify/reference` endpoint for BYO source.
- Provenance schema committed.

**P1.3 M3/M4 — Reliability States + Configurable Tolerances (Days 46–50)**
- P1.3.1 Define 4 states: `verified`, `corrected`, `estimated`, `unavailable`.
- P1.3.2 Define time-aware tolerances per field (e.g., price ±1% same-day, ±3% if >1 day old; P/E ±5%).
- P1.3.3 Implement fail-open vs fail-closed policy when no reference exists.
- P1.3.4 Replace hard-coded 15%/30% bands in PARA-DEBATE with configurable tolerance config.

**Deliverable:**
- `verify/decision_engine.py`.
- Config file: `config/verify_tolerances.yaml`.

**P1.4 M5 — Verification Audit Log (Days 51–55)**
- P1.4.1 Append-only table `verify_audit_log` with: note id, claim, claimed value, reference value, source, decision, tolerance, model/prompt version, user, timestamp.
- P1.4.2 Add hash chain linking each row to previous row hash.
- P1.4.3 Export to CSV and PDF.
- P1.4.4 Retention config: 5 years (SEBI draft) or 7 years (ASIC RG 255).
- P1.4.5 Use same pattern as existing `security_events` table.

**Deliverable:**
- Migration `verify_audit_log.sql`.
- `GET /verify/audit/{note_id}/csv` and `/pdf`.

**P1.5 M6/M7 — Verification Certificate + Licensee Branding (Days 54–58)**
- P1.5.1 One-page PDF certificate: claims checked, corrections, unavailable items, sources, reviewer sign-off box.
- P1.5.2 Branding slots: firm name, registration number, logo, disclosure blocks.
- P1.5.3 NeuralQuant appears only as "verified by NeuralQuant".

**Deliverable:**
- `POST /verify/{note_id}/certificate` returning PDF.
- Certificate template.

**P1.6 M8 — REST API + API Keys + Metering (Days 55–60)**
- P1.6.1 `POST /verify` takes text, returns claims + decisions.
- P1.6.2 API key generation, per-key usage counts.
- P1.6.3 Stripe metered billing.
- P1.6.4 Enable OpenAPI docs for `apps/verify` only.
- P1.6.5 Reuse existing quota scaffolding.

**Deliverable:**
- Public API docs for `/verify`.
- Stripe metered billing wired.

**P1.7 M9 — Web Upload + Review Screen (Days 56–60)**
- P1.7.1 Simple web page: paste or upload document, see highlighted claims, accept/override each correction, download certificate.
- P1.7.2 Human approves every correction before certificate generation.

**Deliverable:**
- `apps/web/src/app/verify/page.tsx` (minimal, behind auth).

**P1.8 M10 — Reproducible Evaluation Harness (Days 58–60)**
- P1.8.1 Expand corpus to ~300 claims.
- P1.8.2 Script reports precision, recall, false-correction rate pinned to data snapshot + git commit.
- P1.8.3 Runs in CI on every PR.
- P1.8.4 Script: `scripts/verify_evaluate.py`.

**Deliverable:**
- CI job `verify-eval`.
- Baseline metrics recorded.

**Phase 1 Gate (Day 60):**
- ≥2 partners running notes weekly.
- False-correction rate ≤2%.
- Recall ≥80% on core fields (price, P/E, revenue growth, target price, beta, market cap).
- If behind, cut M9 and keep API-only.

---

### Phase 2 — Pilots, Pricing & Patent (Days 61–90)
**Goal:** Convert 2–3 design partners into paying pilots, turn on honest marketing, and lock patent framing.

**P2.1 Partner Operations (Days 61–75)**
- P2.1.1 Weekly check-in with each partner.
- P2.1.2 Fix top 3 issues per partner.
- P2.1.3 Track: notes per partner per week, corrections per note, overrides where gate was wrong.

**Deliverable:**
- `docs/verify/PARTNER_METRICS_W9-W11.md`

**P2.2 S1 — AI-Use Disclosure Generator (Days 62–70)**
- P2.2.1 Generate AI-use disclosure paragraph from actual log data.
- P2.2.2 Compliant with SEBI 2025 circular on AI disclosure.
- P2.2.3 Show on certificate optionally.

**Deliverable:**
- `POST /verify/disclosure` endpoint.

**P2.3 Pricing & Stripe (Days 68–75)**
- P2.3.1 Define tiers: **Solo** ($49/mo, 1 user, 50 notes/mo), **Firm** ($199/mo, 5 users, 500 notes/mo), **Enterprise** (custom).
- P2.3.2 Configure Stripe products and metered billing for overage.
- P2.3.3 Send conversion proposal to each partner: pilot ends 31 January 2027; paid from February 2027.

**Deliverable:**
- Stripe products live.
- `docs/verify/PRICING.md`.
- Conversion proposals sent.

**P2.4 Public Evaluation Report (Days 76–82)**
- P2.4.1 Write honest "NeuralQuant Verify Evaluation Report" from M10.
- P2.4.2 Include precision, recall, method, limits, data snapshot date, git commit.
- P2.4.3 Post on LinkedIn and publish at `docs/verify/EVALUATION_REPORT_2026-12.md`.

**Deliverable:**
- First honest public performance claim.
- Inbound lead tracking sheet.

**P2.5 Patent Attorney Engagement (Days 76–82)**
- P2.5.1 Email Intepat or chosen attorney for complete-specification quote and timeline.
- P2.5.2 Ask three questions:
  1. Can claims be reframed so verification gate leads and debate is dependent?
  2. Which new features (time-aware tolerances, fail-open/closed, hash-chained log, BYO source) are supported by provisional vs new matter?
  3. s39 foreign-filing position given Sydney residence.
- P2.5.3 Brief attorney on verification gate framing.

**Deliverable:**
- Attorney quote received.
- Ownership confirmed or plan to resolve.

**P2.6 Patent Specification Reframing (Days 83–90)**
- P2.6.1 Draft complete specification around deterministic interception/correction of LLM numeric outputs with provenance-tagged data and audit log.
- P2.6.2 Include worked examples from real Verify runs.
- P2.6.3 Make debate framework a dependent claim.

**Deliverable:**
- Draft complete spec in `docs/patent/COMPLETE_SPEC_DRAFT_2027.md`.

**Phase 2 Gate (Day 90):**
- **Continue A** if: ≥1 paying customer or signed LOI, false-correction ≤2%, ≥2 partners still using it. Next goal: 5 paying customers by end of March 2027.
- **Switch to B** if publishers like evidence but won't pay for checker, and one will discuss licensing the engine.
- **Go to F+I** if neither: sale hygiene, asset listing, one build-service project for cash.

---

### Phase 3 — Scale, Complete Spec, and 5 Customers (Months 4–6: Jan–Mar 2027)
**Goal:** Reach 5 paying customers, file complete patent specification, and harden the platform.

**P3.1 S2 — Reviewer Workflow (Jan)**
- P3.1.1 Two-step approval: drafter → compliance reviewer.
- P3.1.2 Record sign-offs in audit log: "AI recommends, assurance verifies, human approves".

**P3.2 S3 — Explainable Scores (Jan–Feb)**
- P3.2.1 One unified score label map.
- P3.2.2 Labels are neutral model buckets, not Buy/Sell.
- P3.2.3 Show factor breakdown and formula on every score.
- P3.2.4 Missing factors shown as missing, not silently 0.5.

**P3.3 S4 — Reproducible Strategy Backtest (Only if Direction B is active; Feb)**
- P3.3.1 Rebuild from `score_cache_history` using existing walk-forward calculator.
- P3.3.2 Pinned data snapshot, transaction costs, delisted names, published config + commit hash, multi-year windows.
- P3.3.3 Delete `_q1fy27_baseline()`.

**P3.4 S5/S6/S7 — Batch Mode, Webhooks, Text-Claim Checks, Monitoring Dashboard (Feb–Mar)**
- P3.4.1 Batch verify a day's notes in one call.
- P3.4.2 Webhooks on `corrected` or `unavailable` events.
- P3.4.3 Text-claim checks: dates, ticker-to-company matching, "beat/missed estimates" statements.
- P3.4.4 Dashboard: correction rate per model/field over time (drift evidence per REP 798).

**P3.5 Patent Filing (By Mid-June 2027)**
- P3.5.1 Finalize complete specification by mid-May 2027.
- P3.5.2 File Indian complete specification by mid-June 2027 (3-week buffer before 7 July 2027 deadline).
- P3.5.3 Decide PCT by 31 March 2027: only if ≥5 paying customers, buyer asks, or funder pays.

**P3.6 Sales & Marketing (Jan–Mar)**
- P3.6.1 10 new outreach messages per week using evaluation report as proof.
- P3.6.2 Target: 5 paying customers by 31 March 2027.
- P3.6.3 Build security questionnaire pack for enterprise prospects.

**Phase 3 Gate (31 Mar 2027):**
- 5+ paying customers → continue scale.
- <5 customers but strong pilot pipeline → extend.
- No pipeline → activate Direction F (asset sale) or I (services).

---

### Phase 4 — Platform Expansion (Months 7–12: Apr–Sep 2027)
**Goal:** Expand product surface for multi-tenant enterprise use and deepen moat.

**P4.1 Multi-Tenant & SSO**
- P4.1.1 Organization-scoped audit logs.
- P4.1.2 SAML/OIDC SSO for enterprise licensees.

**P4.2 Data Residency**
- P4.2.1 EU/IN data-residency options for enterprise.
- P4.2.2 Regional reference-source routing.

**P4.3 SDK & Middleware**
- P4.3.1 Python SDK: `pip install neuralquant-verify`.
- P4.3.2 LangChain / LangGraph / TradingAgents middleware so publishers can call Verify inside their own pipelines.

**P4.4 Suspend/Advise Hooks (Direction D Bridge)**
- P4.4.1 API hooks for platforms to suspend advice if correction rate exceeds threshold.
- P4.4.2 Kill-switch integration per RG 255.

**P4.5 Australian Licensee Onboarding**
- P4.5.1 Only after employment/IP check is fully cleared.
- P4.5.2 AFSL/ASIC disclosure templates.

**P4.6 India Fundamentals Vendor Integration**
- P4.6.1 Evaluate licensed India fundamentals vendor.
- P4.6.2 Integrate as primary reference source if cost-effective.

**Phase 4 Gate (Sep 2027):**
- 10+ paying customers or 1 enterprise anchor.
- Decision: raise seed / continue bootstrapping / pursue strategic partnership.

---

### Phase 5 — Strategic Outcome (Oct 2027 onwards)
**Goal:** Choose and execute the long-term path.

| Outcome | Condition | Action |
|---|---|---|
| **A — Independent B2B SaaS** | Verify has 10+ paying customers, low churn, healthy unit economics | Keep scaling; raise seed or stay bootstrapped |
| **B — Licensed Engine** | One publisher wants exclusive/non-exclusive research engine | License scoring + verification stack under their brand |
| **D — RegTech Platform Middleware** | Large platform wants audit hooks | Pivot to middleware/SDK model |
| **F — Asset Sale** | A or B not working; buyer interested | Package code, patent, evaluation harness, customer LOIs; sell |
| **G — Open Source** | Patent filed, no competitive moat from secrecy | Open-source debate/verification framework; monetize support/enterprise |
| **I — Services Bridge** | Cash needed while product scales | Take 1–2 build-service projects for licensed publishers |

**Patent maintenance decision (2028–2029):**
- Request examination by ~7 February 2029.
- Decide whether to pursue grant or abandon based on business value.

---

## Part D: Technical Specs for Verify MVP

### D.1 Service Layout

```
apps/verify/
  src/
    verify/
      __init__.py
      main.py              # FastAPI app
      config.py            # tolerances, sources, retention
      extractor.py         # M1
      reference_store.py   # M2
      decision_engine.py   # M3/M4
      audit.py             # M5
      certificate.py       # M6/M7
      api_keys.py          # M8
      billing.py           # M8
      webhooks.py          # later
      models.py            # Pydantic schemas
    tests/
      test_extractor.py
      test_decision.py
      test_audit.py
      test_certificate.py
  Dockerfile
  requirements.txt         # no torch
  README.md
```

### D.2 Database Schema

```sql
-- verify_notes: input text and metadata
CREATE TABLE verify_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    licensee_id UUID NOT NULL,
    raw_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    model_version TEXT,
    prompt_version TEXT
);

-- verify_claims: extracted claims
CREATE TABLE verify_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES verify_notes(id),
    field TEXT NOT NULL,          -- price, pe, revenue_growth, etc.
    entity TEXT,                  -- ticker or company
    period TEXT,
    claimed_value NUMERIC,
    claimed_unit TEXT,
    claimed_currency TEXT,
    extracted_at TIMESTAMPTZ DEFAULT NOW()
);

-- verify_references: resolved reference values
CREATE TABLE verify_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID REFERENCES verify_claims(id),
    source TEXT NOT NULL,         -- FMP, EDGAR, FRED, BHAVCOPY, BYO
    source_licence_class TEXT,    -- commercial, public, byo
    reference_value NUMERIC,
    reference_unit TEXT,
    reference_currency TEXT,
    as_of_date DATE,
    retrieved_at TIMESTAMPTZ DEFAULT NOW(),
    raw_payload JSONB
);

-- verify_decisions: final state
CREATE TABLE verify_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID REFERENCES verify_claims(id),
    state TEXT CHECK (state IN ('verified','corrected','estimated','unavailable')),
    tolerance_used NUMERIC,
    policy TEXT CHECK (policy IN ('fail_open','fail_closed')),
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    model_version TEXT,
    prompt_version TEXT
);

-- verify_audit_log: hash-chained evidence
CREATE TABLE verify_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES verify_notes(id),
    event_type TEXT NOT NULL,     -- claim_extracted, reference_found, decision_made, override, certificate_generated
    payload JSONB NOT NULL,
    previous_hash TEXT,
    row_hash TEXT NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- verify_certificates: generated artefacts
CREATE TABLE verify_certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES verify_notes(id),
    pdf_url TEXT,
    claims_total INT,
    claims_verified INT,
    claims_corrected INT,
    claims_unavailable INT,
    reviewer_signed BOOLEAN DEFAULT FALSE,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- verify_api_keys + usage (reuse existing pattern)
CREATE TABLE verify_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    licensee_id UUID NOT NULL,
    key_hash TEXT NOT NULL,
    label TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### D.3 API Contract

```yaml
POST /verify
  headers:
    X-API-Key: string
  body:
    text: string
    licensee_config:
      tolerances: object        # optional override
      branding: object          # logo url, reg numbers
      fail_policy: string        # "fail_open" | "fail_closed"
  response:
    note_id: uuid
    claims:
      - field: string
        entity: string
        period: string
        claimed_value: number
        reference_value: number
        state: verified | corrected | estimated | unavailable
        tolerance_used: number
        source: string
    certificate_url: string
    audit_url: string

GET /verify/audit/{note_id}/csv
GET /verify/audit/{note_id}/pdf
POST /verify/{note_id}/certificate
POST /verify/disclosure
```

### D.4 Evaluation Harness

```bash
# Run against pinned snapshot
python scripts/verify_evaluate.py \
  --corpus data/verify/evaluation_corpus_v1.jsonl \
  --snapshot data/snapshots/verify_snapshot_YYYYMMDD.json \
  --commit $(git rev-parse HEAD) \
  --output reports/verify_eval_YYYYMMDD.json
```

Reports:
- precision, recall, false-correction rate
- per-field breakdown
- git commit hash
- data snapshot date

---

## Part E: What We Stop, Freeze, or Deprecate

| Area | Action | Timeline |
|---|---|---|
| B2C subscriptions | Suspend/hide | Day 1 |
| Buy/Sell labels | Remove | Day 7 |
| 90% accuracy claims | Remove from site + LinkedIn | Day 7 |
| Personalized advice flows | Disable behind flags | Day 14 |
| Portfolio profiler | Disable or remove | Day 14 |
| Veronica advice path | Disable | Day 14 |
| Sell-signal panels | Disable | Day 14 |
| Voice worker | Pause new work; scale down hosting | Day 7 |
| Hermes trading | Freeze submodule; scale down Railway | Day 7 |
| Mobile app | Freeze features; remove from build pipeline | Day 14 |
| `torch` in API | Remove from install if unused | Day 14 |
| Yahoo user-facing paths | Replace with licensed sources + BYO | Day 30 |
| `_q1fy27_baseline()` | Delete | Day 14 |
| `/testing/quarterly/public-results` | Remove fallback or make internal | Day 14 |

---

## Part F: Weekly Hour Budget

| Phase | Weeks | Hours/Week | Total Hours |
|---|---|---|---|
| Phase 0 | 4 | 15 | 60 |
| Phase 1 | 4 | 15 | 60 |
| Phase 2 | 4 | 11 avg (holiday weeks 8h) | 46 |
| Phase 3 | 12 | 15 | 180 |
| Phase 4 | 24 | 15 | 360 |
| Phase 5 | ongoing | variable | variable |

**First 90 days total:** ~166 hours.

---

## Part G: Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Regulatory exposure from live site | Week 1 cleanup; no B2C charging |
| Conflict with employer / QuantAlpha JV | Contract check week 1; pause AU until cleared |
| Unclear IP ownership | Resolve by end of October 2026 |
| Building without demand | No MVP code before day-30 gate |
| Gate errors damage trust | M10 harness + human approval of every correction |
| Data licensing (Yahoo/FMP) | No Yahoo impersonation; BYO source option; confirm FMP terms |
| Burnout | Freeze bloat, fixed 15h/week, clear gates |
| Patent deadline missed | Mid-June 2027 filing target with 3-week buffer |
| False-correction rate too high | Tolerance tuning, fail-open policy, human override loop |

---

## Part H: Immediate Next Actions (This Week)

1. **Read employment contract and QuantAlpha JV** → `docs/verify/IP_OWNERSHIP_CHECKLIST.md`.
2. **Scrub site + LinkedIn** for advice/accuracy/recommendation language.
3. **Audit hosting costs** → `docs/verify/BURN_DOWNSIZE_PLAN.md`.
4. **Pause voice worker and Hermes** to reduce burn.
5. **Build 40-prospect list** of licensed publishers.
6. **Draft the free verification report offer message**.
7. **Verify InPASS status** for the provisional patent.
8. **Remove `_q1fy27_baseline()` fallback** and hard-coded backtest claims.

---

## Part I: How to Use This Plan

- Every phase has a numeric gate. Do not proceed past a gate until criteria are met.
- This file is the anchor. As work progresses, update `docs/verify/STATUS.md` with current phase, gate status, blockers, and metrics.
- Commit plan updates the same way code is committed: small, clear PRs.
- The only performance claims allowed in public are those produced by `scripts/verify_evaluate.py`.

---

**Plan version:** 1.0  
**Based on report:** `NEURALQUANT_MASTER_REPORT_AUDIT_GB`  
**Next review date:** Day 7 of Phase 0.
