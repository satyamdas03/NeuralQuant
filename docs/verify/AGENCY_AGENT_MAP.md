# NeuralQuant Verify — Agency Agent Orchestration Map

**Purpose:** Map every available agency agent to the Verify roadmap phases so each phase has a defined builder, reviewer, tester, and auditor.  
**Rule:** No phase is declared complete until the assigned **Universal Verification Agent** (`testing-reality-checker`) publishes a PASS memo.

---

## 0. Universal Verification Agent

| Agent | Frontmatter Name | Responsibility |
|---|---|---|
| **testing-reality-checker** | `name: testing-reality-checker` | Independent certifier for every phase. Verifies live endpoints, runs tests, audits claims, and publishes a pass/fail memo. Assisted by specialists as needed. |

---

## 1. Phase Mapping: Foundation Lock → Verify Phase 0 → Verify Phase 5

### Phase 0A — Foundation Lock (Prerequisite)
*Goal: Verify the technical baseline is trustworthy before any pivot work.*

| Role | Agency Agent | Frontmatter | Deliverable |
|---|---|---|---|
| Baseline certifier | testing-reality-checker | `name: testing-reality-checker` | `docs/verification/baseline_report.md` |
| Test analyst | testing-test-results-analyzer | `name: testing-test-results-analyzer` | Flakiness + coverage memo |
| Data freshness auditor | engineering-data-engineer | `name: engineering-data-engineer` | Data freshness report |
| API contract auditor | engineering-backend-architect | `name: engineering-backend-architect` | Contract audit memo |
| Docs auditor | engineering-technical-writer | `name: engineering-technical-writer` | Doc diff report |

**Gate:** `169/169 pytest`, Next.js build clean, 50 IN + 50 US tickers have fresh price/change_pct/name, docs match live stack.

---

### Phase 0B — Verify Phase 0: Stop the Bleed + Validate Demand (Days 1–30)
*Goal: Clean regulatory exposure and confirm licensed publishers will pay.*

#### 0B.1 Legal / IP Hygiene
| Role | Agent | Frontmatter | Task |
|---|---|---|---|
| IP/ownership reviewer | business-strategist | `name: business-strategist` | Review QuantAlpha JV for IP claims |
| Employment conflict reviewer | data-privacy-officer | `name: data-privacy-officer` | Identify employment-contract side-project clauses |
| Legal questions assembler | chief-financial-officer | `name: chief-financial-officer` | Frame lawyer-readiness checklist |

**Main agent (Claude) does:** Read contracts, create checklists, verify InPASS.

#### 0B.2 Product / Site Cleanup
| Role | Agent | Frontmatter | Task |
|---|---|---|---|
| Advice-label auditor | testing-reality-checker | `name: testing-reality-checker` | Scrape site/LinkedIn for forbidden claims |
| Frontend risk reviewer | security-appsec-engineer | `name: security-appsec-engineer` | Confirm disabled advice routes are unreachable |
| UX removal reviewer | design-ux-architect | `name: design-ux-architect` | Confirm removal does not break core UX |

**Main agent does:** Edit code to remove labels, fallbacks, advice flows.

#### 0B.3 Cost / Hosting Triage
| Role | Agent | Frontmatter | Task |
|---|---|---|---|
| Burn auditor | finance-fpa-analyst | `name: finance-fpa-analyst` | Monthly budget before/after |
| Cloud security reviewer | security-cloud-security-architect | `name: security-cloud-security-architect` | Safe scaling-down checklist |
| Infra automator | engineering-devops-automator | `name: engineering-devops-automator` | Pause voice/Hermes/mobile pipelines |

**Main agent does:** Run cost audit, pause workers, remove `torch` if unused.

#### 0B.4 Prospect Research
| Role | Agent | Frontmatter | Task |
|---|---|---|---|
| Outreach copy reviewer | marketing-content-creator | `name: marketing-content-creator` | Review free-verification-report message |
| Business strategy reviewer | business-strategist | `name: business-strategist` | Validate target-segment sizing |
| CFO reviewer | chief-financial-officer | `name: chief-financial-officer` | Sanity-check pricing anchors |

**Main agent does:** Build prospect list, send outreach, conduct interviews.

#### 0B.5 Evaluation Corpus
| Role | Agent | Frontmatter | Task |
|---|---|---|---|
| Data engineer | engineering-data-engineer | `name: engineering-data-engineer` | Corpus schema and storage |
| Test analyst | testing-test-results-analyzer | `name: testing-test-results-analyzer` | Label-quality audit |
| Reality checker | testing-reality-checker | `name: testing-reality-checker` | Verify 100-claim corpus is committed |

**Main agent does:** Label 100 claims, store `data/verify/evaluation_corpus_v1.jsonl`.

**Phase 0 Gate:** ≥15 publisher conversations, ≥5 use LLMs, ≥3 pilot yes, ≥1 names $49+/mo.

---

### Phase 1 — Verify MVP Core (Days 31–60)
*Goal: Build `apps/verify/` FastAPI service with M1–M10.*

| Subsystem | Builder (main agent) | Reviewer Agent(s) | Auditor Agent(s) |
|---|---|---|---|
| Service architecture (`apps/verify/`) | engineering-backend-architect, engineering-software-architect | `name: engineering-backend-architect` | `name: testing-reality-checker` |
| M1 Claim extractor | engineering-ai-engineer | `name: engineering-ai-engineer` | `name: testing-reality-checker` |
| M2 Reference store | engineering-data-engineer | `name: engineering-data-engineer` | `name: testing-reality-checker` |
| M3/M4 Decision engine + tolerances | engineering-backend-architect | `name: engineering-backend-architect` | `name: testing-api-tester` |
| M5 Audit log (hash-chained) | engineering-backend-architect, security-appsec-engineer | `name: security-appsec-engineer` | `name: testing-reality-checker` |
| M6/M7 Certificate + branding | design-ui-finish-gate-reviewer | `name: design-ui-finish-gate-reviewer` | `name: testing-reality-checker` |
| M8 API keys + metering | engineering-api-platform-engineer | `name: engineering-api-platform-engineer` | `name: security-appsec-engineer` |
| M9 Web upload/review | design-ux-architect, engineering-frontend-design | `name: design-ux-architect` | `name: testing-api-tester` |
| M10 Evaluation harness | testing-test-results-analyzer, testing-api-tester | `name: testing-test-results-analyzer` | `name: testing-reality-checker` |
| Database migrations | engineering-database-reliability-engineer | `name: engineering-database-reliability-engineer` | `name: testing-reality-checker` |
| Performance / load | testing-performance-benchmarker | `name: testing-performance-benchmarker` | `name: testing-reality-checker` |

**Phase 1 Gate:** ≥2 partners running notes weekly, false-correction ≤2%, recall ≥80%.

---

### Phase 2 — Pilots, Pricing & Patent (Days 61–90)
*Goal: Convert partners to paying pilots, publish honest evaluation report, frame patent.*

| Workstream | Agent(s) | Frontmatter |
|---|---|---|
| Partner metrics tracking | product-manager | `name: product-manager` |
| AI-use disclosure generator | data-privacy-officer, business-strategist | `name: data-privacy-officer` |
| Pricing tiers + Stripe | chief-financial-officer, finance-financial-analyst | `name: chief-financial-officer` |
| Evaluation report review | finance-investment-researcher, testing-reality-checker | `name: finance-investment-researcher` |
| Patent attorney prep | business-strategist, chief-financial-officer | `name: business-strategist` |
| Complete spec draft review | finance-investment-researcher | `name: finance-investment-researcher` |

**Phase 2 Gate:** ≥1 paying customer or signed LOI, false-correction ≤2%, ≥2 partners active.

---

### Phase 3 — Scale, Complete Spec, 5 Customers (Jan–Mar 2027)
*Goal: Harden platform, reach 5 paying customers, file patent complete specification.*

| Workstream | Agent(s) | Frontmatter |
|---|---|---|
| Reviewer workflow | product-manager, design-ux-architect | `name: product-manager` |
| Explainable scores | finance-investment-researcher, engineering-ai-engineer | `name: finance-investment-researcher` |
| Reproducible backtest (if B) | finance-financial-analyst, engineering-data-engineer | `name: finance-financial-analyst` |
| Batch/webhooks/dashboard | engineering-backend-architect, engineering-data-visualization-engineer | `name: engineering-data-visualization-engineer` |
| Security questionnaire | security-appsec-engineer, data-privacy-officer | `name: security-appsec-engineer` |
| Sales outreach content | marketing-content-creator | `name: marketing-content-creator` |
| Patent filing readiness | business-strategist, chief-financial-officer | `name: business-strategist` |

**Phase 3 Gate:** 5+ paying customers, patent spec filed or ready by mid-June 2027.

---

### Phase 4 — Platform Expansion (Apr–Sep 2027)
*Goal: Multi-tenant, SSO, data residency, SDK, middleware, AU onboarding.*

| Workstream | Agent(s) | Frontmatter |
|---|---|---|
| Multi-tenant / SSO | engineering-identity-access-engineer, engineering-backend-architect | `name: engineering-identity-access-engineer` |
| Data residency | security-cloud-security-architect, engineering-data-engineer | `name: security-cloud-security-architect` |
| SDK + middleware | engineering-api-platform-engineer, engineering-ai-engineer | `name: engineering-api-platform-engineer` |
| Suspend/kill-switch hooks | security-appsec-engineer, engineering-sre | `name: security-appsec-engineer` |
| Australian licensee onboarding | data-privacy-officer, business-strategist | `name: data-privacy-officer` |
| India fundamentals vendor | engineering-data-engineer, finance-investment-researcher | `name: engineering-data-engineer` |

**Phase 4 Gate:** 10+ paying customers or 1 enterprise anchor.

---

### Phase 5 — Strategic Outcome (Oct 2027+)
*Goal: Choose long-term path and execute.*

| Outcome | Primary Agent(s) | Frontmatter |
|---|---|---|
| Independent SaaS scale | chief-financial-officer, product-manager | `name: chief-financial-officer` |
| Licensed engine (B) | business-strategist, finance-financial-analyst | `name: business-strategist` |
| RegTech middleware (D) | engineering-api-platform-engineer, business-strategist | `name: engineering-api-platform-engineer` |
| Asset sale (F) | business-strategist, chief-financial-officer | `name: business-strategist` |
| Open source (G) | engineering-technical-writer, product-manager | `name: engineering-technical-writer` |
| Services bridge (I) | business-strategist, finance-fpa-analyst | `name: business-strategist` |

---

## 2. Cross-Phase Agent Combos

| Decision / PR | Agents to invoke together | Frontmatter block |
|---|---|---|
| New `apps/verify/` endpoint or schema change | Backend Architect + DB Reliability Engineer + API Tester | `name: engineering-backend-architect`, `name: engineering-database-reliability-engineer`, `name: testing-api-tester` |
| Claim extractor prompt/model change | AI Engineer + Test Results Analyzer + Reality Checker | `name: engineering-ai-engineer`, `name: testing-test-results-analyzer`, `name: testing-reality-checker` |
| Audit log / security change | AppSec Engineer + Cloud Security Architect + Reality Checker | `name: security-appsec-engineer`, `name: security-cloud-security-architect`, `name: testing-reality-checker` |
| Pricing / licensing decision | CFO + Financial Analyst + Business Strategist | `name: chief-financial-officer`, `name: finance-financial-analyst`, `name: business-strategist` |
| Site copy / advice-label cleanup | Marketing Content Creator + Data Privacy Officer + Reality Checker | `name: marketing-content-creator`, `name: data-privacy-officer`, `name: testing-reality-checker` |
| Patent claim reframing | Business Strategist + Financial Analyst + Investment Researcher | `name: business-strategist`, `name: finance-financial-analyst`, `name: finance-investment-researcher` |
| Cost/hosting change | FPA Analyst + Cloud Security Architect + SRE | `name: finance-fpa-analyst`, `name: security-cloud-security-architect`, `name: engineering-sre` |
| Demo / investor readiness | Business Strategist + Marketing Content Creator + Reality Checker | `name: business-strategist`, `name: marketing-content-creator`, `name: testing-reality-checker` |

---

## 3. When Main Agent (Claude) Does the Work vs. Agency Agents

### Main agent does directly
- File reads, edits, code writes, migrations, PRs.
- Running shell commands, tests, builds, deploys.
- Direct API calls and live endpoint checks.
- Drafting documents, outreach messages, interview notes.
- Committing and pushing code.
- Updating memory files and `STATUS.md`.

### Agency agents are invoked as review lenses
- Before finalizing a design or PR.
- After a phase's code is written, to audit/test/verify.
- When a specialized risk (security, finance, compliance, performance) needs review.
- To produce a signed-off memo that gates phase completion.

### Agency agents are NOT used for
- Writing production code directly (they review/audit).
- Making final go/no-go decisions (the main agent implements, user can override).
- Operating vendor dashboards or rotating secrets (they produce runbooks; main agent or user executes where MFA is required).

---

## 4. Tracking Artifacts

| Artifact | Path | Updated By |
|---|---|---|
| Master plan | `docs/verify/NEURALQUANT_VERIFY_MASTER_PLAN.md` | Main agent |
| Agency map | `docs/verify/AGENCY_AGENT_MAP.md` | Main agent |
| Status tracker | `docs/verify/STATUS.md` | Main agent after each phase/gate |
| Phase memos | `docs/verify/phase_memos/` | testing-reality-checker + specialists |
| Evaluation corpus | `data/verify/evaluation_corpus_v1.jsonl` | Main agent |
| Live verification reports | `docs/verification/baseline_report.md` | testing-reality-checker |
| Memory index | `C:\Users\point\.claude\projects\C--Users-point-projects-stockpredictor\memory\MEMORY.md` | Main agent |

---

## 5. Autonomous Execution Rules

1. **Gate before progress.** Every phase ends with a `testing-reality-checker` PASS memo. No exceptions.
2. **Pause on user command.** If the user says pause, stop immediately, commit/push all work, update `STATUS.md`, and report current state.
3. **Commit frequently.** Each meaningful chunk of work gets a commit: `robocad: verify-phase0 — <what changed>`.
4. **Push to master.** Keep master clean and in sync per project instructions.
5. **Update memory.** After each phase, write a memory file and update `MEMORY.md` index.
6. **No production secrets in code.** Secrets stay in `.env`; runbooks reference env var names only.
7. **No performance claims without eval harness.** Public claims only from `scripts/verify_evaluate.py`.
8. **Stop if baseline fails.** If Foundation Lock fails, diagnose and fix before any Verify phase work.

---

## 6. Current Phase Assignment

**Now entering:** Phase 0A — Foundation Lock  
**Universal verification agent:** testing-reality-checker  
**Specialists for this phase:** testing-test-results-analyzer, engineering-data-engineer, engineering-backend-architect, engineering-technical-writer  
**Next phase if gate passes:** Phase 0B — Stop the Bleed + Validate Demand
