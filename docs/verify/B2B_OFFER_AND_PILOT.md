# NeuralQuant Verify — B2B Offer and Pilot Description

**Status:** PROVISIONAL until customer-discovery interviews validate pain and willingness to pay.  
**Target segments:** SEBI-registered Research Analysts (India), US investment-newsletter publishers (publisher's exclusion), RIAs.  
**Core product:** A verification/audit layer for published research notes, not a stock-picking tool for retail investors.

---

## The problem we solve

Licensed research publishers must be able to prove that every number in their research note is grounded in sourced data. Regulators are asking:

- SEBI RA Regulations and the Feb 2026 Master Circular require RAs using AI to disclose that use and remain solely responsible for output.
- US SEC Marketing Rule restricts hypothetical or backtested performance claims and requires substantiation.
- AI-washing enforcement (Delphia, Global Predictions, March 2024) makes unsubstantiated AI claims risky.

Today, most publishers either verify numbers by hand or do not verify them at all. NeuralQuant Verify automates the drudgery and keeps an audit log.

---

## What Verify does

For any research note (text, PDF, or API):

1. **Extract** every numeric claim with ticker context (price, P/E, market cap, revenue, growth %, dates, etc.).
2. **Ground** each claim against provenance-tagged data (FMP, EDGAR, NSE, macro feeds, etc.).
3. **Classify** each claim as:
   - **VERIFIED** — sourced value matches within a stated tolerance.
   - **MISMATCH** — sourced value differs; show the sourced value.
   - **UNVERIFIABLE** — no authoritative data available; fail closed, never guess.
4. **Log** every correction, source, and timestamp in a hash-chained audit log.
5. **Output** a report the publisher can attach to their note or show to a regulator.

Verify does **not**:
- Tell readers what to buy or sell.
- Publish performance claims, alpha, hit rates, or accuracy numbers.
- Act as a SEBI-registered research analyst or investment adviser.

The licensed publisher remains responsible for the final published content. Verify is the tool they use to substantiate it.

---

## Why it fits the patent

Indian patent application 202631083313 describes a multi-agent adversarial debate framework with a numeric verification gate. Verify productizes the gate: the correction log, the `verified/estimated/unavailable` provenance states, the time-aware tolerances, and the fail-closed behaviour when no authoritative data exists.

---

## Pilot offer (PROVISIONAL)

**Who:** Up to 3 licensed publishers in distinct segments (SEBI RA, US newsletter, RIA).  
**What:**
- Submit up to 5 research notes per week.
- Receive a CSV + HTML verification report within minutes.
- Get a weekly call to refine tolerances and reduce false positives.
**Duration:** 4 weeks.  
**Price:** Free pilot; paid tier to be set after interviews (target $49–$999/month, PROVISIONAL).  
**Success metric:** Publisher can show the audit log alongside a published note and say "every number was checked against this source."

---

## One-line value propositions by segment

| Segment | Pain | Verify value |
|---|---|---|
| SEBI-registered Research Analyst (India) | SEBI requires AI disclosure and sole responsibility for AI-generated output. | An audit log that maps every number to a source, ready for SEBI examination. |
| US newsletter publisher | SEC Marketing Rule and AI-washing risk on performance and accuracy claims. | Substantiation layer that flags unsupported numbers before publication. |
| RIA | Compliance officers need to show that model outputs are data-grounded. | Source-tagged, reproducible verification reports for client-facing research. |

---

## What's needed from the founder

Satyam must run 15+ discovery interviews using `docs/verify/interviews.csv` and confirm:

1. Which segment feels the pain most acutely.
2. What file format they submit notes in (PDF, Word, email, API).
3. What their current verification process costs in time/money.
4. Whether they will pay a monthly fee for an audit log.
5. Whether a regulator or compliance officer would accept the Verify report.

Do not start Verify product engineering until at least 3 pilots are confirmed.
