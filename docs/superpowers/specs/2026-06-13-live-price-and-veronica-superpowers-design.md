# Live-Price Reliability + Veronica Superpowers — Design

Date: 2026-06-13 · Status: approved (brainstorm gate passed)

Two independent subsystems, executed together tonight.

- **A. Permanent live-price fix** — eliminate "Price unavailable" for any real ticker.
- **B. Veronica superpowers** — B1 page-context (she always knows the screen), B2 wake word ("Hey Veronica"), B3 morning briefing.

---

## A. Permanent live-price fix

### Root cause
On Render, nq-api has no reliable real-time price source for an arbitrary ticker:
- **yfinance self-blocked** — `yf_guard` deliberately skips yfinance on Render (Yahoo blocks Render IPs; direct calls return "possibly delisted").
- **FMP plan-gated** — `batch-quote` works (US), but single `/quote`, key-metrics, ratios, and IN `.NS` quotes return **402**.
- **Prefetch fetches the wrong tickers** — Phase-0 batch-quote prices the screener top-N, but the LLM's ForeCast/portfolio can name *other* tickers (observed: prefetched `NUE,BNY,LLY,NTRS,CFG`; LLM picked `VLO,BKR,NTRS,LLY` → VLO/BKR had no price).
- **stock_snapshot** only covers the ~592 refreshed universe tickers, 30 min stale.

### The unlock
**`nq-openbb` already returns live yfinance data on Render for US *and* IN** (logs: `HINDZINC.NS` 200 via openbb). nq-api already has `nq_data.openbb.get_openbb_client()`, and OpenBB exposes `/equity/price/quote` and `/equity/price/historical` (see `routes/terminal.py:59,64`). Use it as the reliable real-time price tier.

### Design
New centralized helper, single source of truth for "what does this trade at right now":

```
get_live_price(ticker, market) -> (price: float | None, source: str)
```

Location: a focused module, e.g. `apps/api/src/nq_data/price/live_price.py` (follows the existing `nq_data.price` package). Source order (first hit wins, each wrapped so one failure falls through):

1. **FMP batch/quote** — reuse the existing FMP client quote (works for US). For IN `.NS`, FMP quote is 402 → falls through.
2. **nq-openbb `/equity/price/quote?symbol={sym}&provider=yfinance`** — via `get_openbb_client()`. Works on Render for US **and** IN. Normalize the IN symbol to `.NS`. Extract last/close price from the response. **This is the new reliable tier.**
3. **stock_snapshot** — `snapshot_cache.read_snapshot(ticker, market)["price"]` (30-min fresh, already added in session 90).
4. **score_cache** — `read_one(ticker, market, max_age=7d)["current_price"]` (last resort).

Add a tiny in-process TTL cache (60 s) keyed `(ticker, market)` so a portfolio of N stocks and repeat renders don't re-hit openbb.

### Wiring
- Refactor the price cascade in `apps/api/src/nq_api/services/portfolio.py` (`_validate_and_fill_portfolio_prices`) to call `get_live_price` as the authoritative path, **inserting the openbb tier before the existing yfinance-direct/score_cache tiers**. Keep the existing FMP-batch prefetch as tier 1 (it's already there as `fmp_prices`), but ensure any ticker the prefetch missed now resolves via openbb. This fixes the VLO/BKR class of bug (LLM-named tickers not prefetched).
- Point the **stock-detail price path** (`routes/stocks.py`) and any other "current price" lookups at the same `get_live_price` so all surfaces agree.
- Keep `yf_guard` as-is (still skip *direct* yfinance on Render); openbb is the sanctioned proxy.

### Error handling
- openbb cold start: `get_openbb_client()` already has connect/read timeouts + keep-warm (`terminal.py`). On timeout, fall through to snapshot/score_cache; never hang the request.
- If every tier fails (genuinely unknown ticker), keep the existing "Price unavailable" string — but for any real US/IN ticker this should no longer happen.

### Testing
- Unit: `get_live_price` source-order with monkeypatched tiers (openbb hit, openbb-miss→snapshot, all-miss→None). Symbol normalization for IN `.NS`.
- Unit: portfolio fill uses openbb tier when FMP prefetch missed the ticker.
- Live (post-deploy): Ask Morgan ForeCast naming VLO/BKR/TCS/RELIANCE → all show real entry/target/stop.

---

## B1. Veronica page-context — "she always knows the screen"

### Root cause (confirmed in code)
`VeronicaProvider` publishes only `{type, route, pageType, ticker, narrate}` — **no `keyData`** (the visible numbers the design called for). And `parse_page_context` (`veronica_logic.py`) extracts only `route/page_type/ticker/narrate`, so even a richer message is stripped. The agent's `[PAGE]` note therefore reads "viewing stock_detail (/stocks/X), ticker X" with **zero data** → when asked "what am I looking at," she correctly says the content "didn't come through."

### Design
Carry the on-screen numbers from each page to the agent and into her grounding note.

1. **Shared page-data store** — extend `apps/web/src/lib/veronica-store.ts` with a `pageData: Record<string, unknown> | null` field + setter `setPageData()`. Significant pages (stock detail, portfolio, dashboard, performance) call `setPageData({...})` with their key visible numbers (e.g. stock: `{ price, pe, irs_pct, score, change_pct, week52High, week52Low }`). Keep it small (a handful of fields). Pages clear it on unmount.
2. **Provider publishes `keyData`** — in `VeronicaProvider`'s page-context effect, include `keyData: pageData` in the published `page_context` payload. Re-publish when `pageData` changes (add it to the effect deps) so live updates reach her.
3. **Agent preserves + injects keyData** — `parse_page_context` returns `key_data` (validated: dict or None). `_note_page` formats it into the `[PAGE]` note: e.g. `"[PAGE] User is viewing stock_detail for TCS. On screen: price ₹X, P/E Y, IRS Z%, score N/10."`
4. **Prompt rule** (`veronica_persona.py` / system prompt) — "When asked what they're looking at, answer from the `[PAGE]` note's on-screen data. If a ticker page has no on-screen numbers, silently use your tools to fetch them. **Never** tell the user their page content didn't come through."
5. **Fallback for pages without a store entry** — `keyData` absent → she still has `route`+`ticker` and uses tools; for non-ticker pages she describes the page type and what it's for.

### Testing
- Unit (agent): `parse_page_context` preserves `key_data`; `_note_page` renders numbers into the note.
- Unit (frontend): store set/clear; provider includes `keyData` and re-publishes on change.
- Live: open a stock page with Veronica on → ask "what am I looking at" → she states the actual price/score on screen.

---

## B2. Wake word — "Hey Veronica"

### Behavior
She open-mics during an active session (no wake word needed). After 5 min idle she **sleeps** (room disconnects, billing stops). Today, waking requires an orb click. Add voice wake **while sleeping**.

### Design
- New hook `apps/web/src/lib/useWakeWord.ts` using the browser **Web Speech API** (`window.SpeechRecognition || window.webkitSpeechRecognition`), continuous + interim results. **Active only when the orb is `sleeping` or `idle`** (never during a live session — the LiveKit pipeline owns the mic then).
- On a transcript containing "veronica" (tolerant match: "hey veronica", "veronica", "hey, veronica"), call the provider's `connect()` and stop the recogniser (the session takes over the mic).
- Lifecycle: auto-restart on `onend` (Chrome stops periodically) while still sleeping; stop on unmount / when leaving sleeping state; swallow `not-allowed`/`no-speech` errors.
- **Graceful degrade:** unsupported browser (no SpeechRecognition) → hook is a no-op, orb click still works. Show a subtle one-time orb hint "Say 'Hey Veronica' or click" only where supported.
- Permission: Web Speech reuses mic permission already granted for the session; first sleep may re-prompt — handle denial by falling back to click silently.

### Constraints / honesty
- Web Speech API is **Chrome/Edge-centric**; Firefox/Safari unsupported → click fallback. This is acceptable for an MVP wake word; a Porcupine/WASM upgrade is a future option (needs a license key) and is out of scope tonight.
- Zero LiveKit/Deepgram cost while sleeping (wake word runs locally in the browser).

### Testing
- Unit: wake-word matcher (true for "hey veronica"/"veronica", false for unrelated speech).
- Manual: sleep Veronica → say "Hey Veronica" in Chrome → she reconnects and greets.

---

## B3. Morning briefing

### Behavior
On the user's **first Veronica connect of the day**, instead of the plain "Hey there" greeting, she speaks a short (~20–30 s) spoken briefing: market regime + a couple of notable market moves, then their watchlist/portfolio highlights and any flagged changes. Subsequent same-day connects use the normal short greeting.

### Design
- **First-of-day detection** — backend. When `/livekit/token` issues a `veronica` token, check `user_events` for a prior `veronica_session` `session_start` today (UTC or user-local — use UTC for simplicity, matches existing cap logic). Return `morning_briefing: true` in the token response when it's the first session today.
- **Frontend** passes the flag to the room via a `page_context`-style data message `{type:"briefing", enabled:true}` right after connect (or include it in the first page_context). Simplest: provider publishes `{type:"briefing"}` once on connect when `body.morning_briefing` is true.
- **Agent** — on receiving `{type:"briefing"}` (or via a greeting branch), build the briefing using `context.build_greeting_context` (already assembles portfolio/watchlist/market notes — `context.py:161,269`) plus her market tools, and `session.generate_reply(instructions=...)` for a concise spoken briefing. Reuse the existing greeting-context machinery rather than new data plumbing where possible.
- Falls back to the normal greeting if briefing data is unavailable (never blocks).

### Testing
- Unit (api): token route returns `morning_briefing=true` only on the first `veronica_session` of the day; false on second.
- Unit (agent): briefing instruction builder includes regime + watchlist when context present.
- Live: first connect of the day → spoken briefing; reconnect later → short greeting.

---

## Build order
1. **A — live price** (highest user pain; isolated backend).
2. **B1 — page-context** (core to Veronica's value; she's already live).
3. **B3 — morning briefing** (builds on greeting/context machinery).
4. **B2 — wake word** (frontend-only, independent).

## Cross-cutting notes
- Veronica's voice: `kdnRe2koJdOK4Ovxn2DI` returns HTTP 400 from ElevenLabs (invalid / not addable) → she's on the safe fallback voice. Tracking separately; not part of this spec. If a valid voice ID is supplied, set `VERONICA_VOICE_ID` and redeploy.
- Deploy: A → `nq-api` redeploy; B1/B3 agent → `quantastra-agent` redeploy; B1/B2/B3 frontend → Vercel auto on merge.
