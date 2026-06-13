# Design — Session 90 batch: portfolio crash, branding, voice, greeting, debate animation, IN price

**Date:** 2026-06-13
**Status:** Approved (brainstorming gate passed)

Six independent tasks bundled from a single user report. Each is self-contained; build order is P0-crash first, most-uncertain last.

---

## T1 — Portfolio "Something went wrong" crash (BUG, P0)

### Root cause
Frontend/backend contract mismatch on geopolitical warnings.

- Backend `GET /astra/geopolitical-scan` (`apps/api/src/nq_api/routes/astra_portfolio.py:666`) emits **per-ticker** warnings:
  ```json
  { "ticker", "sector", "risk_level", "beta", "irs_pct", "recommendation" }
  ```
- Frontend `GeopoliticalScanPanel` (`apps/web/src/components/GeopoliticalScanPanel.tsx`) + the `GeopoliticalWarning` TS type (`apps/web/src/lib/types.ts:785`) expect **per-event**:
  ```ts
  { title, description, severity, affected_sectors: string[], affected_tickers: string[] }
  ```
- When any watchlisted stock is in a geo-sensitive sector (RELIANCE = oil&gas), the panel hits `w.affected_sectors.length` → `undefined.length` → throws during render → React error boundary shows "Something went wrong / Reload Page".
- Matches the report exactly: page renders, panels show "Scanning…", then 5-6s later the scan resolves with a non-empty warning and the render throws. US crashes identically (watchlist-driven, independent of 0 recommendations).

### Fix (approach: frontend renders the real per-ticker shape)
1. Update `GeopoliticalWarning` type in `types.ts` to the actual backend fields: `ticker, sector, risk_level ("HIGH"|"MEDIUM"), beta, irs_pct, recommendation`.
2. Rewrite `GeopoliticalScanPanel` to render per-ticker rows: map `risk_level` → severity color (HIGH=red, MEDIUM=amber), show ticker, sector, beta, recommendation. Keep the HIGH/MEDIUM count chips by deriving from `risk_level`.
3. Add defensive guards everywhere arrays/objects are read from API responses (`?? []`, `?? 0`, optional chaining) so a future contract drift degrades gracefully instead of white-screening.
4. **Contract audit** `SellSignalsPanel` against `GET /astra/sell-signals`: confirmed no crash (no `.length` on item fields), but neutral items emit `note` while the panel renders `s.reason` → blank text. Cheap fix: backend `astra_portfolio.py:538` neutral branch also sets `"reason"` (keep `note` for compat). Add the same defensive guards to the panel.

### Test
- Build passes (`apps/web` typecheck).
- Manual: load `/portfolio` with a watchlist containing a geo-sensitive IN stock — no crash, warning renders. Repeat for US tab.

---

## T2 — Ask Morgan "Price unavailable" for IN stocks (BUG, P1)

### Root cause
The 6-tier price cascade in `apps/api/src/nq_api/services/portfolio.py:159-241` exhausts for IN tickers:
- Tier 1-2 FMP: returns no IN quote (Premium-gated for `.NS`).
- Tier 3-4 yfinance: blocked on Render (`yf_guard skip` / "possibly delisted").
- Tier 5 `score_cache`: may lack the IN row.
- Tier 6 `_fetch_one`: re-hits the same blocked sources.

Gap: the cascade never queries `stock_snapshot` — the dedicated live-price table. **Verified:** `quantfactor_universe` has NO price column (scores/ratios/beta only); cannot be used. `stock_snapshot` (`apps/api/src/nq_api/cache/snapshot_cache.py`) has a `price` column and is refreshed every 30 min via GitHub Actions, which runs yfinance **unguarded** — so it holds IN prices that Render's blocked yfinance cannot fetch.

### Fix
Add a price tier in `portfolio.py` (before the "all sources failed" branch at line 234) calling `snapshot_cache.read_snapshot(ticker, stock_market)` → `.get("price")`. Insert it **before** the score_cache tier (snapshot refreshes far more often). Tag `price_source = "stock_snapshot"`. Falls through cleanly if the row or price is absent.

### Test
- Ask Morgan a portfolio query with an IN stock that previously showed "Price unavailable" (TCS, RELIANCE) → entry/target/stop populate from `stock_snapshot`.
- Unit: monkeypatch `read_snapshot` to return `{"price": 3500.0}` and assert the tier fills `live_price` with `price_source == "stock_snapshot"`.

---

## T3 — QuantAstra PARA-DEBATE loading animation (FEATURE, P1, voice panel only)

### Problem
"Deep dive on NVIDIA" triggers `run_para_debate` (`apps/livekit-agent/src/quantastra/tools/research_tools.py:17`), 60-120s with zero UI feedback. Black-box → user confusion. Goal: show the 7 agents working behind the scenes.

### Fix (frontend-timed reveal anchored by real start/complete events)
Reuse the existing data-channel pattern (`participant.publish_data`, topic `"quantastra"`, consumed by `useDataChannel("quantastra", …)` in `QuantAstraCallView.tsx`).

**Agent side** (`research_tools.py`):
- Before `orch.analyse(...)`: publish `{type:"debate_progress", phase:"started", ticker, market}`.
- After it returns (success or handled error): publish `{type:"debate_progress", phase:"complete", ticker, verdict, consensus_score}` (or `phase:"error"`).
- Mirror the participant-access pattern used by `whiteboard_tools.py` (`self` → room local participant). Wrap publishes in try/except so a publish failure never breaks the debate.

**Frontend** (`QuantAstraCallView.tsx` + new `DebateProgressPanel`):
- Handle `debate_progress` in the `useDataChannel` switch.
- On `started`: render `DebateProgressPanel` listing the 7 stages — Macro, Fundamental, Technical, Sentiment, Geopolitical, Adversarial (parallel analysts) → Head Analyst (synthesis). Reveal/advance them on a timed sequence (the 6 analysts animate "thinking" over the first ~20-30s, then hold on "Head Analyst synthesizing…").
- On `complete`: mark all done, show the verdict + consensus, auto-dismiss after a few seconds (or when the agent starts speaking).
- On `error`: collapse the panel gracefully.
- Panel coexists with whiteboard/transcript layout; does not replace audio.

Rationale for timed (not real per-agent) reveal: the orchestrator runs the 6 analysts in parallel (logs show simultaneous start), so honest per-agent events add little; threading a progress callback through the shared `nq_api` orchestrator (also used by the web path) is out of scope. Real `started`/`complete` boundaries keep it anchored to reality.

### Test
- `apps/livekit-agent` unit: publishing helper emits well-formed `debate_progress` JSON.
- Manual voice: ask QuantAstra for a deep dive → stage panel appears, animates, snaps to verdict on completion.

---

## T4 — Veronica voice → `kdnRe2koJdOK4Ovxn2DI`

- Change default in `apps/livekit-agent/src/quantastra/veronica_agent.py:34`:
  `VERONICA_VOICE_ID = os.getenv("VERONICA_VOICE_ID", "kdnRe2koJdOK4Ovxn2DI")`.
- Set `VERONICA_VOICE_ID=kdnRe2koJdOK4Ovxn2DI` on the Render livekit-agent worker (env), so it holds even if defaults change.

### Test
- Enable Veronica → spoken greeting uses the new voice.

---

## T5 — "QuantAlpha" → "NeuralQuant" everywhere (product code, incl. identifiers)

Brand string: **`NeuralQuant`** (one word). Replace all variants ("QuantAlpha AI", "QuantAlpha") → "NeuralQuant".

### Scope — product code only
- `apps/web/**`, `apps/api/**`, `apps/livekit-agent/**` source (UI strings, personas, greetings, SEBI disclaimers, meta tags, `globals.css`).
- Service-worker cache key bump (e.g. `quantalpha-v2` → `neuralquant-v1`). Already network-first → forces one clean cache bust, no stale-UI risk.
- Active config / env-referenced strings.

### Out of scope (historical records — leave as-is)
`docs/**`, `memory/**` (auto-memory), `offTopic/**`, design specs/plans, `linkedin_company_post.txt`.

### Method
- Enumerate the 41 files from grep, filter to product dirs.
- Replace per-file (case-aware; check each `globals.css` / persona hit is text not a deliberate identifier collision).
- Typecheck `apps/web`; sanity-import `apps/api` + `apps/livekit-agent`.

---

## T6 — Greeting "Hey there" + keep session recall, no name/email

- `apps/livekit-agent/src/quantastra/context.py` `build_personalized_greeting`: open with **"Hey there"** instead of "Hey {name}, welcome back." **Keep** the "In our last session we talked about X" recall. Drop the name fetch usage in the greeting line (name no longer interpolated).
- `apps/livekit-agent/src/quantastra/veronica_logic.py` `build_veronica_greeting`: open with **"Hey there, Veronica here…"**, ignore the `name` argument entirely (signature kept for caller compatibility, value unused).
- No name, no email anywhere in either greeting.

### Test
- `apps/livekit-agent/tests/test_veronica_logic.py`: assert greeting starts with "Hey there" and contains no interpolated name.
- QuantAstra greeting unit/manual: "Hey there" + recall present, no name.

---

## Build order
1. **T1** portfolio crash (P0 — users hitting it now)
2. **T5** branding (large mechanical sweep)
3. **T6** greeting (small, in agent code touched by T4)
4. **T4** Veronica voice
5. **T3** debate animation
6. **T2** IN price tier (most uncertain — needs column verification)

## Risks / notes
- T5 SW cache-key bump intentionally invalidates cached clients once — acceptable, network-first SW already in place (`sw_cache_first_stale_ui` memory).
- T2 hinges on `quantfactor_universe` exposing a usable price column; verify before coding, fall through cleanly if absent.
- T3 must never let a `publish_data` failure interrupt the debate result.
- Render env changes (T4) + worker redeploy are deploy-time steps, tracked separately from code.
