# NeuralQuant — US & India Compliance Research

**Date:** April 17, 2026
**Prepared for:** NeuralQuant founding team
**Product under review:** SaaS at $19–$99/mo delivering (a) composite 1–10 quant scores from a 5-factor model, (b) 7-agent LLM debate producing bull/base/bear scenarios with entry/target/stop levels, (c) screener + watchlist + backtest tools. No order routing. No custody. No brokerage. Data sourced from FRED and yfinance.
**Target jurisdictions:** United States (SEC / FINRA / state securities boards) and India (SEBI / RBI / MeitY).

> **TL;DR** — NeuralQuant can launch in the **US as a non-registered research publisher** if it sticks rigidly to the Lowe v. SEC three-prong test (impersonal, bona fide, regular) and bolts the right disclaimer everywhere. It **cannot** lawfully launch in **India** without **SEBI Research Analyst (RA) registration** — SEBI's post-2024 rule set closed almost every loophole a "publisher" could slip through, and serving Indian-resident subscribers of any specific-stock output without an RA cert is actionable. India also forces a local Pvt Ltd (for RA cert) and drags in 18% OIDAR GST from rupee one. US launch = ~6–8 weeks, ~$8–15k. India launch = ~16–24 weeks, ~$12–25k.

---

## UNITED STATES

### 1. Is NeuralQuant an "investment adviser" under the Advisers Act of 1940?

The Investment Advisers Act §202(a)(11) defines an adviser as anyone who, "for compensation, engages in the business of advising others … as to the value of securities or as to the advisability of investing in, purchasing, or selling securities." That covers NeuralQuant on its face — composite scores, bull/base/bear scenarios, and entry/target/stop levels are squarely "advisability of purchasing or selling."

NeuralQuant's escape hatch is §202(a)(11)(D), the **publisher exclusion** for any "bona fide newspaper, news magazine or business or financial publication of general and regular circulation." The Supreme Court in **Lowe v. SEC, 472 U.S. 181 (1985)** read the exclusion broadly on First Amendment grounds and laid down a three-prong test. To fit the exclusion, the content must be:

1. **Impersonal** — not tailored to the individual needs of any specific client. General publication, same content to all subscribers.
2. **Bona fide** — genuine, disinterested commentary and analysis, not a promotional vehicle for a security the publisher is positioned in.
3. **Regular / general circulation** — published on a predictable schedule, not spun up in response to a market event.

**Applied to NeuralQuant:**

- Scores, 7-agent debate, and bull/base/bear pages published identically to every subscriber at the same tier → **impersonal**.
- No proprietary trading, no affiliate-stock pushing, no pay-for-coverage → **bona fide**, provided the product never takes an issuer's money.
- Content regenerated on a fixed cadence (e.g., daily/weekly refresh) and accessible to any paying subscriber → **regular and of general circulation**.

**Where NeuralQuant would break Lowe:**

- Allowing users to feed in their portfolio, risk tolerance, age, or holdings and getting back output that reacts to that input. That is personalized advice, and the publisher exclusion evaporates (see the [Wilson Sonsini analysis of SEC interest in interactive "information providers"](https://www.wsgr.com/en/insights/informationor-advice-sec-regulation-of-information-providers-may-expand-to-include-providers-of-innovative-investment-analytics.html)).
- Chatbots that tell a specific user "you should sell MSFT" based on facts that user shared. Same problem.
- "Concierge" tiers, phone calls, Slack channels where individual Q&A happens.
- Event-driven "alert" emails that only go out when a particular ticker moves — arguably not "regular."
- Taking issuer payments for coverage (blows bona fide).

**Decision rule for the product:** the watchlist and screener can be personal UI state (what the user chose to save), but the *analysis output itself* must be identical for all subscribers at that tier. If a user types "I'm 62 and retired, tell me if AAPL is right for me," the LLM must refuse and direct them to a licensed professional. Bake this into the system prompt.

Sources: [Lowe v. SEC 472 U.S. 181 (1985)](https://supreme.justia.com/cases/federal/us/472/181/); [Katten on Seeking Alpha dismissal](https://katten.com/judge-dismisses-case-against-seeking-alpha-implications-for-publishers-of-financial-information); [IBKR Spotlight on Publisher Exclusion](https://www.interactivebrokers.com/webinars/spotlight-publisher-exclusion.pdf); [Winstead — Navigating the Publisher's Exclusion](https://natlawreview.com/article/navigating-publishers-exclusion-under-advisers-act).

### 2. State RIA registration thresholds

If NeuralQuant successfully sits inside the Lowe publisher exclusion, no state RIA registration is required either — the state statutes mirror the federal definition of "investment adviser." But a handful of states have quirks that hit even publishers who hold themselves out in-state:

| State | Quirk relevant to NeuralQuant |
|---|---|
| **Texas** | National de minimis standard (no registration if ≤5 Texas clients in 12 months and no office in TX), **but** still requires a notice filing + fee before the first Texas client. |
| **Louisiana** | Zero-de-minimis in theory, but exempts advisers with <15 LA clients in 12 months who don't hold themselves out to the public. A paid subscription product effectively "holds out." |
| **Nebraska** | Won't respect the federal de minimis for SEC-registered advisers — notice filing required before first NE resident. For non-registered publishers, exclusion applies if Lowe is met. |
| **New Hampshire** | Same posture as Nebraska. |

At sub-$100M AUM a firm is a **state-level** adviser (SEC takes over at $110M+). Since NeuralQuant has $0 AUM, **if the publisher exclusion fails for any reason, it would be a state-registered adviser in every state where it has a subscriber**, which is economically impossible. This is why staying inside Lowe is existential.

Sources: [Kitces — SEC vs State Registration](https://www.kitces.com/blog/registered-investment-advisor-ria-sec-federal-state-registration-rules-iras-notice-filing/); [SmartAsset — De Minimis by State](https://smartasset.com/advisor-resources/de-minimis-exemption-by-state); [Beach Street Legal — State De Minimis](https://beachstreetlegal.com/state-de-minimis-registration-considerations-for-advisors/).

### 3. Disclaimer language the SEC has accepted for research publishers

The SEC has not "blessed" specific boilerplate, but enforcement history (and Seeking Alpha, Motley Fool, Zacks, Morningstar Research case patterns) converge on the following components. Paste-ready boilerplate is in the Deliverables section below.

- A clear "**not investment advice**" label at point of consumption.
- Statement that the publisher is **not a registered investment adviser or broker-dealer**.
- Statement that content is **general and impersonal** and not tailored to any user.
- **Past performance does not guarantee future results** — specifically required any time a backtest or scenario is shown.
- Disclosure of any holdings / conflicts by the authors (relevant for any human-written commentary layered on top).

### 4. Anti-fraud rules on paid stock recommendations

Publisher status does **not** immunize against anti-fraud liability. Section 17(a) of the Securities Act, §10(b) and Rule 10b-5 under the Exchange Act, and §206 of the Advisers Act (which applies to *anyone* giving advice, registered or not) remain live. Practical rules:

- Never publish a score or scenario you know to be false or that you have not actually computed.
- Disclose any paid promotion — if anyone ever pays NeuralQuant to cover their stock, it's a securities-law disaster and blows the Lowe "bona fide" prong. Ban this contractually in the founder agreement.
- Don't trade your own book in the direction of freshly published scores. Put a written **personal-trading policy** in place on day 1 restricting staff from trading tickers that appear in the output window. (This is the single most common trip-wire for research publishers.)

### 5. FINRA BD registration — confirm NOT needed

Broker-dealer registration under §15 of the Exchange Act is triggered by being "engaged in the business of effecting transactions in securities for the account of others." NeuralQuant does not route orders, does not hold customer funds, does not receive transaction-based compensation, and does not match buyers with sellers. **No BD registration required. No FINRA membership required.** This is the clearest regulatory answer in the entire stack.

### 6. Robinhood / Public / Titan vs. NeuralQuant

| Capability | Robinhood | Public | Titan | NeuralQuant |
|---|---|---|---|---|
| Route equity orders | Yes (BD + exchange member) | Yes (BD) | Via partner BD (Apex) | **No** |
| Hold customer cash/securities | Yes (carrying BD, SIPC) | Yes | No (Apex custody) | **No** |
| Discretionary management | No (exec only) | No | Yes (SEC-registered RIA) | **No** |
| Personalized recommendations | No | No | Yes (RIA) | **No** |
| Publish scores/analysis | Some | Yes | Yes | **Yes** |
| Licenses held | BD, SIPC, state money-transmitter where applicable | BD | SEC RIA + BD partner | **None (publisher exclusion)** |

The operational lesson: NeuralQuant's product surface is intentionally narrower than any of these firms' — we are a media/SaaS business, not a financial intermediary. Do not drift the roadmap into "paper trading with real linked accounts," "robo-portfolios," or "copy trading" without re-reading this document.

### 7. Payment compliance — Stripe USD subscriptions

Stripe is itself a licensed payment processor. Subscription billing for a SaaS product does not make NeuralQuant a money services business (MSB). FinCEN's MSB definition covers currency dealers/exchangers, check cashers, prepaid access issuers, money transmitters, and the like — none of which describes charging $29/mo for a research product. State money-transmitter licensing is not triggered either. **No MSB registration.** Standard sales-tax nexus rules apply (most states do not tax SaaS, but NY, TX, WA, MA and a growing list do — work with Stripe Tax or Avalara).

### 8. Data privacy — CCPA/CPRA, GLBA

**CCPA/CPRA applies** if NeuralQuant meets any one of: (i) $25M+ annual revenue, (ii) buys/sells/shares personal info of 100k+ California consumers/households, or (iii) derives ≥50% of revenue from selling/sharing personal information. At launch, none of those apply. As NeuralQuant scales it will almost certainly cross threshold (i) or (ii) — plan to have a privacy notice, DSR intake, and "Do Not Sell or Share" link ready **by the time revenue crosses $10M or the 50k-CA-user mark**.

**GLBA** (Gramm-Leach-Bliley) covers "financial institutions" offering financial products to consumers. SEC-registered advisers and broker-dealers are in scope. A non-registered research publisher is **generally outside GLBA's entity coverage**. Even if a court stretched it, CCPA's GLBA carve-out is a narrow **data-level** exemption, not an entity one — so NeuralQuant cannot hide behind GLBA anyway. Treat all user data as CCPA-regulated.

Sources: [Orrick — Fintech GLBA exemptions](https://www.orrick.com/en/Insights/2022/08/What-Fintech-Companies-Need-to-Know-About-GLBA-and-FCRA-Exemptions-Under-State-Data-Protection-Laws); [Orrick 2025 — GLBA entity exemption status](https://www.orrick.com/en/Insights/2025/07/Where-is-the-GLBA-Entity-Level-Exemption-Two-More-State-Privacy-Laws).

### 9. SEC Marketing Rule 206(4)-1 — hypothetical / backtest disclosures

Rule 206(4)-1 **only binds registered advisers**. A publisher operating under Lowe is not technically subject to it. However, SEC staff have signaled increasing interest in publishers whose marketing mirrors advertising by advisers, and backtested performance is the most heavily scrutinized category in the 2026 Marketing Rule FAQ updates ([Mayer Brown, Jan 2026](https://www.mayerbrown.com/en/insights/publications/2026/01/sec-staff-publishes-new-marketing-rule-faqs); [Mintz, Feb 2026](https://www.mintz.com/insights-center/viewpoints/2026-02-25-sec-marketing-rule-enforcement-2026-why-buyers-breakaways-and)). The safe posture is to **voluntarily comply** as if it bound NeuralQuant:

- Never display a backtest without a **prominent "hypothetical, backtested" label in the same visual block**.
- State criteria, assumptions, limitations (e.g., "assumes instant fill at close, zero slippage, zero taxes, universe = S&P 500 members continuously from 2005, survivorship bias not corrected" — whatever is actually true).
- Include "past performance does not guarantee future results" every time.
- Never show gross-of-fee backtest without a net-of-fee number side-by-side if fees exist.
- Match period choice honestly — don't show 5-yr when 10-yr would look worse.

---

## INDIA

### 10. SEBI Research Analyst Regulations 2014 (as amended through 2024/2025)

Under Regulation 2(1)(u), a "**research analyst**" is any person who prepares and/or publishes research reports, makes buy/sell/hold recommendations, gives price targets, or opines on public offers. **NeuralQuant outputs scores, bull/base/bear scenarios, and explicit entry/target/stop levels on listed Indian stocks** — this is the textbook definition of research analysis. Serving any Indian resident subscriber without RA registration is a regulatory violation and, since 2024, SEBI has been actively enforcing against unregistered "finfluencers" and algo-research platforms.

**Registration requirements post the Third Amendment Regulations 2024 (effective Dec 16, 2024) and the Jan/Jul 2025 Guidelines/FAQs:**

| Item | Requirement |
|---|---|
| Certification | **NISM Series-XV** (Research Analyst) mandatory for every principal analyst; must be renewed every 3 years. |
| Qualification | Graduate/postgraduate in finance, economics, commerce, accountancy, capital markets, banking, actuarial, or professional qualification (CA/CMA/CFA). **Experience requirement removed in 2024.** |
| Net worth | **Replaced** by a graded deposit with RAASB (BSE) — ₹1L (≤150 clients) scaling up to ₹10L at larger client counts. Deposit can now be held in overnight/liquid MFs (not just bank FDs). |
| Application fee | ₹5,000 (individual/partnership) / ₹50,000 (company/LLP). |
| Registration fee | ₹10,000 (individual/partnership) / ₹5,00,000 (company/LLP). |
| Admin body | **RAASB = BSE Ltd** (recognised Jul 2024) handles enlistment, deposit, ongoing supervision. |
| Compliance officer | Required for non-individual RAs. |
| Fee cap on clients | ₹1,51,000/year/family for individual & HUF clients. No cap for non-individuals or accredited investors. |

Sources: [SEBI Jan 2025 Guidelines circular](https://www.sebi.gov.in/legal/circulars/jan-2025/guidelines-for-research-analysts_90634.html); [SEBI Jul 2025 FAQs PDF](https://www.sebi.gov.in/sebi_data/faqfiles/jul-2025/1753269723942.pdf); [TaxGuru — SEBI Updates 2025](https://taxguru.in/sebi/sebi-updates-regulations-research-analysts-2025.html); [CompianceCalendar — Fees](https://www.compliancecalendar.in/learn/fee-applicability-for-ra-ria-registration-with-sebi-and-bse).

### 11. RA vs IA — can we be RA only?

Yes. This is the standard path for a research-publishing SaaS.

- **Research Analyst (RA)** = issues research reports, ratings, price targets. **Impersonal.**
- **Investment Adviser (IA)** = gives personalized advice to a client after understanding their financial situation, goals, risk profile. Requires risk-profiling, suitability, fiduciary-style conduct, and a fee cap.

NeuralQuant should **register as RA only** and explicitly NOT provide personalized advice. An RA cannot (a) guarantee returns, (b) recommend based on a client's individual circumstances, or (c) execute trades on behalf of the client. As long as the product surface remains the "publisher shape" described under Lowe, RA-only is both compliant and ~10× cheaper than dual RA+IA.

Sources: [AZB — Overhaul of RA/IA framework](https://www.azbpartners.com/bank/overhaul-of-the-regulatory-framework-for-investment-advisers-and-research-analysts/); [ELP Law](https://elplaw.in/leadership/sebi-amends-and-modernises-the-investment-adviser-regulations/).

### 12. Mandatory disclosures on every RA output

Every NeuralQuant research artefact served to an Indian user must contain:

- RA registration number (format: INH000XXXXXX) and BSE enlistment ID.
- Name of research analyst and principal officer.
- Date of publication and validity period (price-target horizon).
- Disclosure of any holdings by the RA or its associates in the subject security (past 30 days / at publication / planned).
- Disclosure of any financial relationship with the issuer in the past 12 months.
- Disclaimer that research is for informational purposes only and is not an offer or solicitation.
- Disclosure of **use of AI tools** and the extent of such use (2024 amendment).
- Complaint redressal contact (SCORES portal, SEBI toll-free, ODR link).
- Risk warnings including "investments are subject to market risks."
- For **model portfolios**: additional model-portfolio disclosure pack (universe, rebalancing rules, assumptions).
- For **part-time RAs**: font-size-≥10 disclaimer explaining which of the RA's activities fall outside SEBI's purview.

### 13. 2024–2025 AI/algo amendments

The Third Amendment Regulations 2024 (Dec 16, 2024) and the Jul 2025 FAQ circular are the first SEBI rule-set to explicitly regulate AI in research. Key points:

- **Disclosure of AI use**: every RA must disclose, at point of onboarding and in each report, the extent and manner of AI tool use. "We use an ensemble of LLMs and a 5-factor quantitative model to generate scores and scenarios; final output is not reviewed by a human analyst before publication" would be an acceptable first draft.
- **Responsibility is non-delegable**: the RA remains legally responsible for every AI-generated output as if a human produced it. "The LLM said it" is not a defence.
- **Data protection**: AI pipelines that process client data trigger additional DPDP obligations (see §15).
- **No separate AI licence**: SEBI has not created a new category. AI-only research platforms register as RA.

Sources: [Cyril Amarchand on SEBI AI amendments](https://corporate.cyrilamarchandblogs.com/2024/12/sebis-proposed-new-amendments-on-usage-of-ai-tools-by-regulated-entities/); [Taxmann — AI disclosure mandate](https://www.taxmann.com/post/blog/sebi-mandates-investment-advisers-to-disclose-use-of-ai-tools-to-clients-in-providing-investment-advice).

### 14. RBI — foreign entity payments, Payment Aggregator licence

NeuralQuant does **not** need a Payment Aggregator (PA) licence — PAs are the entities that collect money on behalf of merchants (Razorpay, Stripe India, Cashfree). NeuralQuant is the merchant. However:

- A foreign entity **cannot** directly collect INR subscription payments without going through an RBI-approved PA or PA-CB (cross-border).
- **Stripe India** has held a final RBI PA licence since Jan 2024 — if you use Stripe's India entity, they handle the regulatory burden.
- For an Indian Pvt Ltd subsidiary, a standard merchant account with Razorpay/Cashfree/Stripe India works. Expect KYC including RA registration certificate, GST cert, incorporation docs, board resolution.
- Non-bank PAs themselves need ₹15 Cr net worth at application and ₹25 Cr by end of year 3 — irrelevant to NeuralQuant as merchant.

Sources: [Stripe guide to RBI PA guidelines](https://stripe.com/guides/rbi-guidelines-kyc-direction); [KDP — RBI PA guide 2025](https://kdpaccountants.com/blogs/rbi-payment-aggregator-license-india-2025-guide); [Inc42 — Stripe final RBI nod](https://inc42.com/buzz/stripe-gets-final-rbi-nod-for-payment-aggregator-business/).

### 15. DPDP Act 2023

The Digital Personal Data Protection Act came into force with the DPDP Rules, 2025 rolling out through 2025–2026. NeuralQuant's obligations as a **Data Fiduciary**:

- Plain-language notice at collection in English and the 22 scheduled languages.
- Verifiable consent (can use Consent Manager once live).
- Purpose limitation, storage limitation, reasonable security.
- Data Principal rights: access, correction, erasure, grievance redressal with defined SLAs.
- Breach notification to the Data Protection Board without undue delay.
- Children: consent of parent/guardian required for users <18; no behavioural monitoring of minors.

**Significant Data Fiduciary (SDF)** status triggers at numerical thresholds that the Central Government is still finalising (the 2026 notification is expected to set processing volume, class of data, and risk criteria). Industry guidance points at **~50 lakh (5M) Indian data principals** or **~₹250 Cr revenue** as the likely floor. NeuralQuant will not be an SDF at launch. If it triggers, it adds: DPO appointment (resident in India), DPIA, independent audits.

**Data residency:** DPDP takes a targeted localisation approach — only "specified" categories (to be notified) are residency-locked. At launch, global cloud (AWS ap-south-1 / us-east-1) is acceptable. Plan for ap-south-1 primary, and avoid storing payment or KYC docs outside India even if DPDP doesn't strictly require it — RBI's payment data localisation rule does for payment credentials.

Sources: [EY — DPDP Act 2023 & Rules 2025](https://www.ey.com/en_in/insights/cybersecurity/decoding-the-digital-personal-data-protection-act-2023); [DPDPA.com — SDF guide](https://www.dpdpa.com/blogs/significant_data_fiduciary_sdf_dpdpa_guide.html); [FPF — DPDP explained](https://fpf.org/blog/the-digital-personal-data-protection-act-of-india-explained/).

### 16. GST, OIDAR, Equalisation Levy

- **If NeuralQuant is an Indian Pvt Ltd selling to Indian subscribers:** standard GST at 18% on SaaS. Register for GST above ₹20L annual turnover (₹10L for special-category states). Below that, no GST.
- **If NeuralQuant is a foreign entity (e.g., Delaware Inc) selling to Indian B2C subscribers:** treated as **OIDAR** (Online Information Database Access and Retrieval). **No threshold exemption** — 18% GST from rupee one. Must register under the simplified OIDAR scheme and appoint an authorised representative in India.
- **Equalisation Levy**: fully abolished. The 2% e-commerce EL ended Aug 1, 2024; the 6% online-advertising EL ended Apr 1, 2025. NeuralQuant has no EL exposure going forward.

If NeuralQuant operates through an Indian Pvt Ltd that also holds the SEBI RA registration (the recommended structure), all of the above collapses into one GST registration at incorporation.

Sources: [Business Standard — EL abolition](https://www.business-standard.com/economy/news/india-us-trade-deal-digital-services-tax-equilisation-levy-126021000635_1.html); [VATCalc — EL history](https://www.vatcalc.com/india/india-2-equalisation-levy-extension-to-e-commerce-sellers-and-facilitating-marketplaces-apr-2020/); [Dodo Payments — OIDAR guide](https://dodopayments.com/blogs/navigating-indian-gst-saas/).

### 17. ASCI + SEBI advertising rules

SEBI's 2023–2024 advertising guidelines for RIAs and RAs, reinforced in 2024/2025 circulars, are the strictest in the world:

- No guaranteed or assured returns.
- No claims of "most accurate," "best," "guaranteed profit," or "risk-free."
- Any performance claim requires the full disclosure pack: time period, methodology, net-of-fees, past-performance warning.
- Testimonials are **banned** from regulated entities' ads in India (explicit SEBI ban on "celebrity or client testimonials" for performance).
- Every ad must carry the RA registration number and standard risk disclaimer.
- ASCI guidelines on financial influencers require clear disclosure of "promotional content" and SEBI registration status.

Cleared-for-launch Twitter/LinkedIn copy template: "NeuralQuant — 7-agent AI research on listed Indian equities. SEBI RA reg no. INH000XXXXXX. Research is for informational purposes only. Investments are subject to market risks. Past performance does not guarantee future results."

### 18. Company formation — cheapest 2-person bootstrap path

| Structure | For RA registration | Cost/complexity | Verdict |
|---|---|---|---|
| Individual RA | Yes, allowed | Cheapest (~₹15k total fees) | Works only if a single founder is the principal analyst and owns the business personally. Unlimited liability. Hard to raise. |
| LLP | Yes, allowed | Moderate (~₹55k SEBI fees + ₹10–15k formation) | Better than individual; pass-through tax. Foreign investment in LLPs is restrictive. |
| **Private Limited** | Yes | **Highest upfront (~₹5.5L SEBI fees + ~₹15–25k MCA formation)** but unlocks FDI, equity grants, board structure | **Recommended** if there's any intent to raise outside capital or bring a US parent on as shareholder. |

**Two-person bootstrap recommendation:**
- Incorporate NeuralQuant Technologies Pvt Ltd in India (Bangalore/Delhi) with the two founders as directors. MCA SPICe+ form, ~₹15–25k including DSCs, DIN, stamp duty.
- Open current account + apply for GST immediately.
- One founder clears NISM-XV (~₹1,500 + 2–4 weeks) to be principal analyst.
- File SEBI RA application via BSE RAASB portal. Pay ₹50k application + ₹5L registration fee + ₹1L RAASB deposit (liquid MF units, lien-marked).
- If the long-term plan is a US parent, set up the flip **before** the RA registration (adding a foreign parent post-hoc requires RBI FDI reporting and SEBI re-scrutiny).

---

## CROSS-CUTTING

### 19. How Indian platforms structure research + disclaimers

**Zerodha / Smallcase / Tickertape:** the three operate as separate legal entities precisely to segregate regulated activities. Windmill Capital Pvt Ltd (INH200007645) is the SEBI RA that actually produces research. smallcase Technologies is the tech platform; Zerodha Broking is the BD/exchange member. Every piece of content on Smallcase and Tickertape explicitly says: "Content is not investment advice or research analysis as defined under SEBI (IA) Regulations 2013 and (RA) Regulations 2014 *except* where provided by Windmill Capital under INH200007645." Author-level opinion pieces carry a "personal opinion, for educational purposes only" tag.

**Lesson for NeuralQuant India:** the entity that publishes AI scores and scenarios should be the RA-registered entity, full stop. Don't split it across the tech entity and the RA entity — SEBI treats whoever authored the output as the RA, so better to centralise.

Sources: [Smallcase disclosures](https://www.smallcase.com/meta/disclosures/); [Tickertape disclosures](https://www.tickertape.in/meta/disclosures).

### 20. US patterns — Danelfin, AlphaSense, Trade Ideas

- **Danelfin**: "Stock ratings, alpha signals and rankings are meant for informational purposes only and are not intended to be investment advice or a recommendation to buy or sell any security. … Ratings are based on AI analysis, which calculates probabilities, not certainties." Posted on homepage footer, every ratings page, and in TOS. [Danelfin disclaimer page](https://danelfin.com/disclaimer).
- **AlphaSense**: leans "information provider / research platform," explicitly not an RIA, disclaims personalized advice.
- **Trade Ideas**: algorithmic scanner; same posture — "data and analytics tool, not investment advice," with an additional hypothetical-performance block.

Common pattern: a **single paragraph disclaimer rendered on every page** plus a longer section in the TOS and a link in the email footer.

### 21. Legal weight of "NOT INVESTMENT ADVICE"

- **US**: The label alone does not defeat adviser status or anti-fraud liability. Courts look at **what the business actually does**, not what it calls itself. That said, a consistent, prominent disclaimer is necessary (not sufficient) evidence that the provider is operating as a publisher. Without it, the SEC will assume advisory intent.
- **India**: Almost worthless as a defence. SEBI has repeatedly acted against unregistered entities that used "educational purposes only" tags while giving specific buy/sell calls. The Indian defence is **RA registration**, not a disclaimer. The disclaimer is required *on top of* registration, not as a substitute.

### 22. Does bull/base/bear + entry/target/stop cross into advisory?

In the US: **no, if impersonal** — these are standard research-report artefacts. Every sell-side analyst report has target, base case, bear case.

In India: **yes, this is exactly what SEBI calls a "research report" with "price target" and "stop loss,"** and it places the publisher squarely in the RA regulatory perimeter. You cannot escape by calling them "scenarios" instead of "recommendations." The act of stating an entry-target-stop level for a named security is the regulated activity.

**Safe phrasing (both jurisdictions):**

- Frame as **scenarios**, not directives: "In our bull scenario, our model projects AAPL at $260 within 6 months" rather than "Buy AAPL at $220, target $260, stop $210."
- Or, frame as **levels from the quant model's output**: "Our 5-factor model's 60th-percentile forward-price estimate is $260" — describes the model, not a directive.
- Include time horizon and probability explicitly.
- Never say "buy," "sell," "hold" without surrounding context making clear it's the model's output, not a recommendation to this user.
- Always the disclaimer block.

### 23. Content labelling — every output vs homepage only

**Every output.** Not just the homepage. The SEC and SEBI both expect disclosures at the point of consumption. A user who deep-links to a score page without first visiting the homepage must still see the disclaimer. Practical implementation:

- Global footer on every page in the product.
- A compact 1-sentence disclaimer in every email.
- A compact disclaimer inside each JSON API response (for any future API product).
- A screen-reader-accessible disclaimer block above the fold on every individual score/scenario page.
- A longer TOS + Disclosures page linked from footer.

---

## DELIVERABLES

### Must-do before launch — top 10 ranked by blocker severity

| # | Item | Jurisdiction | Severity | Rationale |
|---|---|---|---|---|
| 1 | **SEBI RA registration for Indian operations** (or block Indian IPs until done) | IN | Existential | Indian law is explicit; no Lowe-equivalent exists. |
| 2 | System-prompt hard constraint: **LLMs must refuse personalized advice** | US+IN | Existential | Personalization destroys the publisher exclusion. |
| 3 | **Per-output disclaimer block** on every score, scenario, email, and API response | US+IN | High | Required to demonstrate publisher posture and satisfy SEBI content rules. |
| 4 | **Personal-trading policy** banning staff trading of covered tickers | US+IN | High | Most common enforcement trip-wire; bona fide prong of Lowe. |
| 5 | **TOS + Privacy Policy** covering CCPA + DPDP; per-user consent for AI processing | US+IN | High | CCPA/DPDP baseline + SEBI AI disclosure mandate. |
| 6 | **Backtest / hypothetical-performance disclosure block** co-located with any performance chart | US+IN | High | Rule 206(4)-1 pattern + SEBI advertising rules. |
| 7 | Entity structure: **India Pvt Ltd for RA + US Delaware C-Corp parent (or separate) for US ops** | US+IN | High | Can't hold SEBI RA as a foreign entity; US fundraising prefers Delaware. |
| 8 | **State notice filings** (TX, NE, NH if users there; LA analysis) | US | Medium | State-specific quirks; not blockers if zero users in those states pre-launch. |
| 9 | **NISM-XV certification** for one founder | IN | Medium | Required for RA registration; exam scheduling is the bottleneck. |
| 10 | **Merchant of record / payment routing**: Stripe (US) + Stripe India or Razorpay (IN) with invoicing to Pvt Ltd | US+IN | Medium | Enables GST compliance and cross-border clean collections. |

### Nice-to-have

- SOC 2 Type I in year 1, Type II in year 2.
- Cyber insurance ($1–2M limit) + professional liability / E&O ($1M).
- Formal written AI model governance doc (bias testing, drift monitoring, override logs).
- Customer complaint log tied to SCORES / ODR for India.
- Proactive Dark-Pattern audit against CCPA and DPDP provisions.
- Independent legal opinion letter on the publisher exclusion (~$5–10k one-time, invaluable if SEC ever asks).

### Total launch cost estimates (ballpark)

**United States launch — $8,000–$15,000 one-time, ~$3,000/yr ongoing**
- Delaware C-Corp formation + registered agent: $500 + $125/yr.
- TOS/Privacy/Disclaimer drafting by a securities lawyer: $5,000–$9,000 flat.
- Publisher-exclusion opinion letter (optional but recommended): $5,000–$10,000.
- State notice filings (TX etc., if applicable): ~$300 per state.
- Cyber + E&O insurance: $2,000–$4,000/yr.
- No SEC / FINRA / state RIA fees (because not registering).

**India launch — $12,000–$25,000 one-time, ~$4,000/yr ongoing**
- Pvt Ltd formation (MCA SPICe+, DSC, DIN): ₹15,000–₹25,000 (~$180–$300).
- SEBI RA fees: ₹50k application + ₹5L registration = ₹5.5L (~$6,600).
- RAASB deposit: ₹1L (~$1,200) — returnable, parks in liquid MF, lien-marked.
- NISM-XV exam + prep: ₹1,500 + optional course ₹5–10k (~$70–$140).
- SEBI-specialist lawyer for RA application and compliance manual: ₹2–4L (~$2,400–$4,800).
- GST registration: free; CA retainer ~₹20–30k/yr (~$240–$360).
- Compliance officer (where required): internal hire or part-time retainer ₹1.5–3L/yr (~$1,800–$3,600).
- Annual RA fee renewal, audit, DPDP compliance: ~₹2–3L/yr (~$2,400–$3,600).

### Timeline estimates

**US launch: 6–8 weeks from decision to live**
- Week 1: entity formation, bank, Stripe.
- Weeks 2–4: TOS/Privacy/Disclaimer drafting + legal review.
- Weeks 3–5: build the per-output disclaimer block into the product; personal-trading policy executed.
- Week 5–6: publisher-exclusion opinion letter (parallel).
- Weeks 6–8: state notice filings (if applicable), soft launch with waitlist, then public.

**India launch: 16–24 weeks from decision to live**
- Weeks 1–2: Pvt Ltd incorporation, PAN, TAN, GST.
- Weeks 1–6: founder sits NISM-XV (allow one resit buffer).
- Weeks 4–10: SEBI RA application via BSE RAASB (SEBI/BSE review typically 8–16 weeks in 2026; they've sped up under the RAASB model).
- Weeks 8–12: Razorpay/Stripe India merchant account + DPDP notice + compliance manual.
- Weeks 12–20: RA certificate issued; product de-geo-blocks India; marketing/advertising submission per SEBI rules.
- Weeks 20–24: first audit cycle + launch.

The correct sequencing is **US first, India second**. Launch the US publisher product within 8 weeks and run it while the SEBI application is pending; India's registration takes ~5× longer than the US path.

---

### Paste-ready disclaimer boilerplate

#### A. Every analysis output (compact, ~60 words — render above-the-fold on every score/scenario page and embed in API responses)

> **Not investment advice.** NeuralQuant publishes general, impersonal research produced by quantitative models and AI. Outputs are identical for all subscribers and are not tailored to any individual's financial situation. NeuralQuant is not a registered investment adviser or broker-dealer in the US. [India only: SEBI Research Analyst Reg. No. INH000XXXXXX.] Investments carry risk. Past performance does not guarantee future results.

#### B. Homepage footer (every page)

> © 2026 NeuralQuant. NeuralQuant provides general investment research and analytics. Nothing on this site is investment advice, a recommendation, or an offer to buy or sell any security. NeuralQuant is not a registered investment adviser or broker-dealer in the United States and operates under the publisher exclusion of Section 202(a)(11)(D) of the Investment Advisers Act of 1940 (Lowe v. SEC, 472 U.S. 181 (1985)). In India, research is published by [NeuralQuant Technologies Pvt Ltd, SEBI Research Analyst Registration No. INH000XXXXXX]. Investments are subject to market risks. Read all related documents carefully before investing. Past performance does not guarantee future results. [Terms of Service](/tos) · [Privacy Policy](/privacy) · [Disclosures](/disclosures) · Grievances: grievance@neuralquant.com · SEBI SCORES: scores.sebi.gov.in.

#### C. Terms of Service — "Nature of Service" clause

> 3. **Nature of Service.** NeuralQuant delivers a research and analytics publication ("the Publication"). The Publication consists of composite scores, scenario narratives, entry/target/stop ranges, and related commentary on publicly listed securities, produced by quantitative models and large-language-model systems. The Publication is published on a regular cadence, is made available to all subscribers at a given tier in identical form, and is not customised to any individual subscriber's holdings, risk tolerance, tax situation, income, or investment objectives. The Publication is not investment advice, is not a recommendation to buy, sell, or hold any security, and is not a solicitation or offer. No fiduciary relationship is created. NeuralQuant is not registered as an investment adviser or broker-dealer in the United States and relies on the publisher exclusion of Section 202(a)(11)(D) of the Investment Advisers Act of 1940. In India, the Publication is produced by NeuralQuant Technologies Pvt Ltd, a SEBI-registered Research Analyst (Reg. No. INH000XXXXXX, valid from [date]).
>
> 4. **AI-Generated Content.** Portions of the Publication are generated by large-language-model systems and quantitative models with limited human review before publication. NeuralQuant discloses this in compliance with SEBI (Research Analysts) Regulations 2014 and the Third Amendment Regulations 2024. Model outputs describe probabilities, not certainties, and may contain errors, omissions, or out-of-date information.
>
> 5. **No Personalisation.** The subscriber acknowledges that NeuralQuant does not assess individual suitability. Any decision to act on the Publication is solely the subscriber's own. Subscribers are encouraged to consult a licensed financial adviser before making investment decisions.
>
> 6. **Performance and Backtests.** Any hypothetical or backtested performance shown in the Publication is for illustrative purposes only, reflects the retroactive application of a model to historical data, and does not represent actual trading. Hypothetical performance is inherently limited and may not reflect real market conditions, transaction costs, taxes, or behavioural factors. Past performance does not guarantee future results.

#### D. Email confirmation / every outbound email footer

> NeuralQuant · general investment research · not investment advice · past performance does not guarantee future results · [India subscribers: SEBI RA Reg. No. INH000XXXXXX] · manage preferences · unsubscribe

---

## Sources

- [Lowe v. SEC, 472 U.S. 181 (1985)](https://supreme.justia.com/cases/federal/us/472/181/)
- [Katten — Seeking Alpha dismissal implications for publishers](https://katten.com/judge-dismisses-case-against-seeking-alpha-implications-for-publishers-of-financial-information)
- [Interactive Brokers — Publisher Exclusion webinar](https://www.interactivebrokers.com/webinars/spotlight-publisher-exclusion.pdf)
- [Wilson Sonsini — Information or Advice? SEC regulation of information providers](https://www.wsgr.com/en/insights/informationor-advice-sec-regulation-of-information-providers-may-expand-to-include-providers-of-innovative-investment-analytics.html)
- [Jacko Law Group — Newsletter Filing Guide](https://jackolg.com/insights/extra-extra-read-all-about-it-guidance-on-registration-requirement-for-publishers-of-newsletters/)
- [SEC — Regulation of Investment Advisers](https://www.sec.gov/about/offices/oia/oia_investman/rplaze-042012.pdf)
- [Winstead — Navigating the Publisher's Exclusion](https://natlawreview.com/article/navigating-publishers-exclusion-under-advisers-act)
- [Kitces — SEC vs State RIA Registration](https://www.kitces.com/blog/registered-investment-advisor-ria-sec-federal-state-registration-rules-iras-notice-filing/)
- [SmartAsset — De Minimis Exemption by State](https://smartasset.com/advisor-resources/de-minimis-exemption-by-state)
- [Beach Street Legal — State De Minimis Considerations](https://beachstreetlegal.com/state-de-minimis-registration-considerations-for-advisors/)
- [BlackHill Law — State Investment Adviser Exemptions](https://blackhill.law/blog/state-investment-adviser-exemptions/)
- [SEC — Marketing Compliance FAQs](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/marketing-compliance-frequently-asked-questions)
- [Mayer Brown — 2026 SEC Marketing Rule FAQs](https://www.mayerbrown.com/en/insights/publications/2026/01/sec-staff-publishes-new-marketing-rule-faqs)
- [Mintz — SEC Marketing Rule Enforcement 2026](https://www.mintz.com/insights-center/viewpoints/2026-02-25-sec-marketing-rule-enforcement-2026-why-buyers-breakaways-and)
- [Troutman Pepper Locke — Marketing Rule Hypothetical Performance](https://www.troutman.com/insights/the-secs-new-marketing-rule-practically-speaking-hypothetical-performance/)
- [Orrick — Fintech GLBA and FCRA Exemptions](https://www.orrick.com/en/Insights/2022/08/What-Fintech-Companies-Need-to-Know-About-GLBA-and-FCRA-Exemptions-Under-State-Data-Protection-Laws)
- [Orrick 2025 — State privacy laws and GLBA](https://www.orrick.com/en/Insights/2025/07/Where-is-the-GLBA-Entity-Level-Exemption-Two-More-State-Privacy-Laws)
- [SEBI — Guidelines for Research Analysts (Jan 2025)](https://www.sebi.gov.in/legal/circulars/jan-2025/guidelines-for-research-analysts_90634.html)
- [SEBI — Research Analyst FAQs (Jul 2025)](https://www.sebi.gov.in/sebi_data/faqfiles/jul-2025/1753269723942.pdf)
- [SEBI — BSE as RAASB/IAASB recognition (Jul 2024)](https://www.sebi.gov.in/legal/circulars/jul-2024/recognition-of-bse-limited-as-research-analyst-administration-and-supervisory-body-raasb-and-investment-adviser-administration-and-supervisory-body-iaasb-_84748.html)
- [TaxGuru — SEBI Research Analyst Regulations 2025](https://taxguru.in/sebi/sebi-updates-regulations-research-analysts-2025.html)
- [Cyril Amarchand — SEBI AI tool amendments](https://corporate.cyrilamarchandblogs.com/2024/12/sebis-proposed-new-amendments-on-usage-of-ai-tools-by-regulated-entities/)
- [Taxmann — SEBI AI disclosure mandate](https://www.taxmann.com/post/blog/sebi-mandates-investment-advisers-to-disclose-use-of-ai-tools-to-clients-in-providing-investment-advice)
- [AZB — Overhaul of RA/IA framework](https://www.azbpartners.com/bank/overhaul-of-the-regulatory-framework-for-investment-advisers-and-research-analysts/)
- [ELP Law — SEBI IA Regulations modernisation](https://elplaw.in/leadership/sebi-amends-and-modernises-the-investment-adviser-regulations/)
- [ComplianceCalendar — RA/RIA fees with SEBI and BSE](https://www.compliancecalendar.in/learn/fee-applicability-for-ra-ria-registration-with-sebi-and-bse)
- [EY — DPDP Act 2023 and Rules 2025](https://www.ey.com/en_in/insights/cybersecurity/decoding-the-digital-personal-data-protection-act-2023)
- [DPDPA.com — SDF guide](https://www.dpdpa.com/blogs/significant_data_fiduciary_sdf_dpdpa_guide.html)
- [FPF — DPDP Act explained](https://fpf.org/blog/the-digital-personal-data-protection-act-of-india-explained/)
- [Stripe — RBI PA guidelines](https://stripe.com/guides/rbi-guidelines-kyc-direction)
- [KDP — RBI PA License guide 2025](https://kdpaccountants.com/blogs/rbi-payment-aggregator-license-india-2025-guide)
- [Inc42 — Stripe final RBI PA nod](https://inc42.com/buzz/stripe-gets-final-rbi-nod-for-payment-aggregator-business/)
- [Business Standard — Equalisation levy abolition](https://www.business-standard.com/economy/news/india-us-trade-deal-digital-services-tax-equilisation-levy-126021000635_1.html)
- [VATCalc — Equalisation Levy history](https://www.vatcalc.com/india/india-2-equalisation-levy-extension-to-e-commerce-sellers-and-facilitating-marketplaces-apr-2020/)
- [Dodo Payments — Indian GST for international SaaS](https://dodopayments.com/blogs/navigating-indian-gst-saas/)
- [Smallcase — Disclosures page](https://www.smallcase.com/meta/disclosures/)
- [Tickertape — Disclosures page](https://www.tickertape.in/meta/disclosures)
- [Danelfin — Disclaimer page](https://danelfin.com/disclaimer)
