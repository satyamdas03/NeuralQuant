# Live-Price + Veronica Superpowers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live prices reliable for any ticker on Render via the nq-openbb yfinance proxy, and give Veronica three superpowers — she always knows the on-screen content, wakes to "Hey Veronica", and gives a morning briefing on first connect of the day.

**Architecture:** Backend = FastAPI (`apps/api`, package `nq_api`; data package `nq_data` in `packages/data`). Voice agent = LiveKit (`apps/livekit-agent`, package `quantastra`). Web = Next.js (`apps/web`). Agent↔web over LiveKit data channel topic `"veronica"`. The OpenBB client (`nq_data.openbb.get_openbb_client()`) already proxies yfinance successfully on Render.

**Tech Stack:** Python/FastAPI/pytest, TypeScript/React, LiveKit agents, Supabase REST, Web Speech API.

Branch already created: `session91-price-veronica`. Spec: `docs/superpowers/specs/2026-06-13-live-price-and-veronica-superpowers-design.md`.

---

## Task A1: Centralized `get_live_price` service

**Files:**
- Create: `apps/api/src/nq_api/services/live_price.py`
- Test: `apps/api/tests/test_live_price.py`

Reliable price chain for Render: **nq-openbb yfinance proxy → stock_snapshot → score_cache**, with a 60s in-process cache. (FMP is attempted upstream by callers; this service is the Render-reliable backstop.)

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_live_price.py`:

```python
import time
from nq_api.services import live_price


class _FakeOBB:
    def __init__(self, quote, enabled=True):
        self._quote = quote
        self.enabled = enabled
    def get_quote(self, symbol, provider="yfinance"):
        return self._quote


def test_openbb_tier_hits_first(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB({"last_price": 205.2}))
    price, source = live_price.get_live_price("NVDA", "US")
    assert price == 205.2
    assert source == "openbb"


def test_falls_through_to_snapshot(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB(None))
    monkeypatch.setattr(live_price, "read_snapshot", lambda t, m: {"price": 3500.0})
    price, source = live_price.get_live_price("TCS", "IN")
    assert price == 3500.0
    assert source == "stock_snapshot"


def test_all_miss_returns_none(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB(None))
    monkeypatch.setattr(live_price, "read_snapshot", lambda t, m: None)
    monkeypatch.setattr(live_price, "_score_cache_price", lambda t, m: None)
    price, source = live_price.get_live_price("ZZZZ", "US")
    assert price is None
    assert source is None


def test_cache_returns_same_within_ttl(monkeypatch):
    live_price._CACHE.clear()
    calls = {"n": 0}
    def _obb():
        calls["n"] += 1
        return _FakeOBB({"last_price": 100.0})
    monkeypatch.setattr(live_price, "get_openbb_client", _obb)
    live_price.get_live_price("AAA", "US")
    live_price.get_live_price("AAA", "US")
    assert calls["n"] == 1  # second call served from cache
```

- [ ] **Step 2: Run — confirm fail**

Run: `cd apps/api && python -m pytest tests/test_live_price.py -v`
Expected: FAIL — module `nq_api.services.live_price` does not exist.

- [ ] **Step 3: Implement the service**

Create `apps/api/src/nq_api/services/live_price.py`:

```python
"""Single source of truth for a ticker's current price on Render.

Source order: nq-openbb yfinance proxy (works on Render for US + IN) ->
stock_snapshot (30-min refresh) -> score_cache (7d). 60s in-process cache.
"""
from __future__ import annotations

import logging
import time

from nq_data.openbb import get_openbb_client, _obb_symbol
from nq_api.cache.snapshot_cache import read_snapshot

log = logging.getLogger(__name__)

_CACHE: dict[tuple[str, str], tuple[float, float]] = {}
_TTL_S = 60.0


def _openbb_price(ticker: str, market: str) -> float | None:
    try:
        obb = get_openbb_client()
        if not obb.enabled:
            return None
        q = obb.get_quote(_obb_symbol(ticker, market))
        if not q:
            return None
        for field in ("last_price", "price", "close", "prev_close"):
            v = q.get(field)
            if v:
                p = float(v)
                if p > 0:
                    return p
    except Exception:
        log.debug("openbb price failed for %s/%s", ticker, market, exc_info=True)
    return None


def _score_cache_price(ticker: str, market: str) -> float | None:
    try:
        from nq_api.cache.score_cache import read_one
        sc = read_one(ticker.upper(), market, max_age_seconds=604800)  # 7d
        if sc and sc.get("current_price"):
            p = float(sc["current_price"])
            return p if p > 0 else None
    except Exception:
        return None
    return None


def get_live_price(ticker: str, market: str = "US") -> tuple[float | None, str | None]:
    """Return (price, source) for the ticker, or (None, None) if all sources miss."""
    key = (ticker.upper(), market)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_S:
        return hit[1], "cache"

    p = _openbb_price(ticker, market)
    source = "openbb"
    if not p:
        snap = read_snapshot(ticker.upper(), market)
        p = float(snap["price"]) if snap and snap.get("price") and float(snap["price"]) > 0 else None
        source = "stock_snapshot"
    if not p:
        p = _score_cache_price(ticker, market)
        source = "score_cache_7d"

    if p:
        _CACHE[key] = (now, p)
        return p, source
    return None, None
```

- [ ] **Step 4: Run — confirm pass**

Run: `cd apps/api && python -m pytest tests/test_live_price.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/services/live_price.py apps/api/tests/test_live_price.py
git commit -m "feat(price): centralized get_live_price (openbb proxy -> snapshot -> score_cache)"
```

---

## Task A2: Wire `get_live_price` into the portfolio price cascade

**Files:**
- Modify: `apps/api/src/nq_api/services/portfolio.py` (the price-fill cascade in `_validate_and_fill_portfolio_prices`)

The cascade currently goes FMP batch → FMP profile → yfinance (skipped on Render) → yf.download → stock_snapshot → score_cache → _fetch_one. Insert the openbb-backed `get_live_price` as a high-priority tier right after the FMP tiers so LLM-named tickers the prefetch missed (e.g. VLO/BKR) resolve.

- [ ] **Step 1: Add the import**

In `apps/api/src/nq_api/services/portfolio.py`, near the existing `from nq_api.cache.snapshot_cache import read_snapshot` line, add:

```python
from nq_api.services.live_price import get_live_price
```

- [ ] **Step 2: Insert the openbb-backed tier after FMP profile (Tier 2)**

In `apps/api/src/nq_api/services/portfolio.py`, immediately AFTER the `# -- Tier 2: FMP profile fallback` block and BEFORE `# -- Tier 3: yfinance`, insert:

```python
        # -- Tier 2b: nq-openbb yfinance proxy (reliable on Render, US + IN) --
        if not live_price or live_price <= 0:
            lp, lp_source = get_live_price(ticker, stock_market)
            if lp:
                live_price = lp
                price_source = lp_source
                fill_notes.append(f"{ticker} price: {lp_source} ({live_price:.2f})")
```

(Leave the existing Tier 3–6 below as deeper fallbacks; `get_live_price` already includes snapshot + score_cache, so those rarely run now, which is fine.)

- [ ] **Step 3: Sanity-import**

Run: `cd apps/api && python -c "import nq_api.services.portfolio"`
Expected: no error.

- [ ] **Step 4: Verify existing snapshot tests still pass**

Run: `cd apps/api && python -m pytest tests/test_snapshot_price.py tests/test_live_price.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/services/portfolio.py
git commit -m "fix(portfolio): resolve any ticker price via openbb proxy tier (fixes VLO/BKR/IN 'Price unavailable')"
```

---

## Task A3: Use `get_live_price` for the stock-detail current price

**Files:**
- Modify: `apps/api/src/nq_api/routes/stocks.py`

- [ ] **Step 1: Find the current-price resolution in the meta path**

Run: `cd apps/api && grep -n "current_price\|live_price\|regularMarketPrice\|yf_guard\|_fetch_one" src/nq_api/routes/stocks.py | head -30`
Identify where `/stocks/{ticker}/meta` (or the meta builder) sets the live price (the field the StockCard shows). Read ~40 lines of context around it.

- [ ] **Step 2: Add a get_live_price backfill for a missing price**

At the point where the meta dict's price is assembled, after the existing FMP/snapshot attempts, add a backfill (use the real variable names found in Step 1 — `meta` and `market` are the conventional names in this file):

```python
        # Backfill price via the reliable openbb->snapshot->score_cache chain
        if not meta.get("price"):
            from nq_api.services.live_price import get_live_price
            _lp, _src = get_live_price(ticker, market)
            if _lp:
                meta["price"] = _lp
```

If the variable holding the response is not named `meta`, adapt to the actual name; do not introduce a new variable. If price is already reliably set on this path, note that and skip — report DONE_WITH_CONCERNS explaining why.

- [ ] **Step 3: Sanity-import**

Run: `cd apps/api && python -c "import nq_api.routes.stocks"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/routes/stocks.py
git commit -m "fix(stocks): backfill stock-detail price via get_live_price"
```

---

## Task B1a: Veronica agent — carry on-screen `keyData` into grounding

**Files:**
- Modify: `apps/livekit-agent/src/quantastra/veronica_logic.py` (`parse_page_context`)
- Modify: `apps/livekit-agent/src/quantastra/veronica_agent.py` (`_note_page`)
- Modify: `apps/livekit-agent/src/quantastra/veronica_persona.py` (prompt rule)
- Test: `apps/livekit-agent/tests/test_veronica_logic.py` (append)

- [ ] **Step 1: Write failing tests for key_data passthrough**

Append to `apps/livekit-agent/tests/test_veronica_logic.py`:

```python
from quantastra.veronica_logic import parse_page_context


def test_parse_page_context_preserves_key_data():
    msg = {
        "type": "page_context",
        "route": "/stocks/TCS",
        "pageType": "stock_detail",
        "ticker": "TCS",
        "narrate": False,
        "keyData": {"price": 3500.0, "irs_pct": 78, "score": 1},
    }
    page = parse_page_context(msg)
    assert page is not None
    assert page["key_data"] == {"price": 3500.0, "irs_pct": 78, "score": 1}


def test_parse_page_context_key_data_defaults_none():
    msg = {"type": "page_context", "route": "/dashboard", "pageType": "dashboard"}
    page = parse_page_context(msg)
    assert page is not None
    assert page["key_data"] is None


def test_parse_page_context_key_data_must_be_dict():
    msg = {"type": "page_context", "route": "/x", "keyData": "not-a-dict"}
    page = parse_page_context(msg)
    assert page["key_data"] is None
```

- [ ] **Step 2: Run — confirm fail**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -k key_data -v`
Expected: FAIL — `page` has no `key_data`.

- [ ] **Step 3: Preserve key_data in `parse_page_context`**

In `apps/livekit-agent/src/quantastra/veronica_logic.py`, in `parse_page_context`, change the returned dict to include `key_data`:

```python
    kd = msg.get("keyData")
    return {
        "route": route,
        "page_type": msg.get("pageType") or "page",
        "ticker": ticker if isinstance(ticker, str) and ticker else None,
        "narrate": bool(msg.get("narrate", False)),
        "key_data": kd if isinstance(kd, dict) else None,
    }
```

- [ ] **Step 4: Inject key_data into the `[PAGE]` note**

In `apps/livekit-agent/src/quantastra/veronica_agent.py`, in `_note_page`, build an on-screen line from `key_data` and append it to the note content:

```python
    async def _note_page(agent: VeronicaAgent, page: dict) -> None:
        try:
            on_screen = ""
            kd = page.get("key_data")
            if isinstance(kd, dict) and kd:
                pairs = ", ".join(f"{k}={v}" for k, v in kd.items() if v is not None)
                if pairs:
                    on_screen = f" On screen: {pairs}."
            chat_ctx = agent.chat_ctx.copy()
            chat_ctx.add_message(
                role="system",
                content=f"[PAGE] User is now viewing {page['page_type']} "
                        f"({page['route']})"
                        + (f", ticker {page['ticker']}" if page["ticker"] else "")
                        + "." + on_screen,
            )
            await agent.update_chat_ctx(chat_ctx)
        except Exception:
            log.debug("update_chat_ctx failed", exc_info=True)
```

- [ ] **Step 5: Add the prompt rule**

In `apps/livekit-agent/src/quantastra/veronica_persona.py`, find the `VERONICA_SYSTEM_PROMPT` string and add this rule near its behavior rules (keep existing text; insert a new bullet/sentence):

```
When the user asks what they are looking at, answer from the most recent [PAGE] note — describe the page and read back the on-screen numbers it lists. If a stock page has no on-screen numbers, quietly use your tools to fetch the live data for that ticker. Never tell the user that their page content did not come through.
```

- [ ] **Step 6: Run tests + sanity-import**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -v`
Run: `cd apps/livekit-agent && PYTHONPATH=src python -c "import quantastra.veronica_logic, quantastra.veronica_persona" || python -m py_compile src/quantastra/veronica_logic.py src/quantastra/veronica_persona.py src/quantastra/veronica_agent.py`
Expected: tests pass; modules compile.

- [ ] **Step 7: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_logic.py apps/livekit-agent/src/quantastra/veronica_agent.py apps/livekit-agent/src/quantastra/veronica_persona.py apps/livekit-agent/tests/test_veronica_logic.py
git commit -m "feat(veronica): carry on-screen keyData into page grounding so she knows what's displayed"
```

---

## Task B1b: Frontend — publish on-screen `keyData`

**Files:**
- Modify: `apps/web/src/lib/veronica-store.ts` (add pageData)
- Modify: `apps/web/src/components/veronica/VeronicaProvider.tsx` (publish keyData)
- Modify: `apps/web/src/app/stocks/[ticker]/page.tsx` (populate pageData for the highest-traffic page)

- [ ] **Step 1: Add a pageData store**

In `apps/web/src/lib/veronica-store.ts`, extend the external store. Replace the `VeronicaExternalState` type and add a setter + change the state object:

```ts
type VeronicaExternalState = {
  /** QuantAstra call modal is open — Veronica must go quiet. */
  astraOpen: boolean;
  /** Key numbers visible on the current page, for Veronica grounding. */
  pageData: Record<string, unknown> | null;
};

let state: VeronicaExternalState = { astraOpen: false, pageData: null };
```

Update `setAstraOpen` to preserve `pageData` (spread already does). Add:

```ts
export function setVeronicaPageData(data: Record<string, unknown> | null) {
  state = { ...state, pageData: data };
  emit();
}
```

And update `serverSnapshot`:

```ts
const serverSnapshot: VeronicaExternalState = { astraOpen: false, pageData: null };
```

- [ ] **Step 2: Publish keyData from the provider**

In `apps/web/src/components/veronica/VeronicaProvider.tsx`:

(a) In `VeronicaSession`, read pageData from the store. Change the destructure:

```tsx
  const { astraOpen, pageData } = useVeronicaExternalState();
```

(b) In the page-context publish effect, include `keyData` and add `pageData` to deps:

```tsx
  useEffect(() => {
    if (!localParticipant) return;
    const { pageType, ticker } = pageInfoFor(pathname);
    const key = `${pageType}:${ticker ?? ""}`;
    const narrate = !quiet && !narratedRef.current.has(key);
    if (narrate) narratedRef.current.add(key);
    const payload = JSON.stringify({
      type: "page_context",
      route: pathname,
      pageType,
      ticker,
      narrate,
      keyData: pageData ?? undefined,
    });
    localParticipant
      .publishData(new TextEncoder().encode(payload), {
        reliable: true,
        topic: "veronica",
      })
      .catch(() => {});
  }, [pathname, quiet, localParticipant, pageData]);
```

Note: `useVeronicaExternalState` currently returns only `astraOpen`. After Step 1 it returns `pageData` too (same hook). No new hook needed.

- [ ] **Step 3: Populate pageData on the stock-detail page**

In `apps/web/src/app/stocks/[ticker]/page.tsx`, after the stock meta/score data is loaded into state, add an effect that pushes the key visible numbers to the store and clears on unmount. Use the actual state variable names present in the file (commonly `meta`, `score`, `summary`); adapt accordingly:

```tsx
import { setVeronicaPageData } from "@/lib/veronica-store";

// ...inside the component, after data is available:
useEffect(() => {
  setVeronicaPageData({
    ticker,
    price: meta?.price ?? null,
    pe: meta?.pe_ttm ?? null,
    irs_pct: score?.irs_pct ?? null,
    score: score?.score_1_10 ?? null,
    change_pct: meta?.change_pct ?? null,
  });
  return () => setVeronicaPageData(null);
}, [ticker, meta, score]);
```

If the page's data variables differ, map to whatever holds price / P/E / IRS / score. Keep it to ~5 fields. If a value isn't available on this page, omit it or pass null.

- [ ] **Step 4: Typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no new errors in the three edited files.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/veronica-store.ts apps/web/src/components/veronica/VeronicaProvider.tsx apps/web/src/app/stocks/[ticker]/page.tsx
git commit -m "feat(veronica): publish on-screen keyData so Veronica can describe the current page"
```

---

## Task B2: Wake word — "Hey Veronica"

**Files:**
- Create: `apps/web/src/lib/useWakeWord.ts`
- Modify: `apps/web/src/components/veronica/VeronicaProvider.tsx` (activate while sleeping/idle)

- [ ] **Step 1: Create the wake-word hook**

Create `apps/web/src/lib/useWakeWord.ts`:

```ts
"use client";

import { useEffect, useRef } from "react";

export function matchesWakeWord(transcript: string): boolean {
  const t = transcript.toLowerCase();
  return t.includes("veronica");
}

/**
 * Browser wake-word listener (Web Speech API). Runs ONLY while `active` is true
 * (Veronica sleeping/idle) so it never competes with the live LiveKit mic.
 * On hearing "veronica" it calls `onWake()`. No-op where SpeechRecognition is
 * unsupported (Firefox/Safari) — caller keeps the orb-click fallback.
 */
export function useWakeWord(active: boolean, onWake: () => void): void {
  const onWakeRef = useRef(onWake);
  onWakeRef.current = onWake;

  useEffect(() => {
    if (!active) return;
    const SR =
      (typeof window !== "undefined" &&
        ((window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
          (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition)) ||
      null;
    if (!SR) return; // unsupported browser — graceful no-op

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rec: any = new (SR as any)();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    let stopped = false;

    rec.onresult = (e: { results: ArrayLike<{ 0: { transcript: string } }> }) => {
      for (let i = 0; i < e.results.length; i++) {
        if (matchesWakeWord(e.results[i][0].transcript)) {
          stopped = true;
          try { rec.stop(); } catch { /* ignore */ }
          onWakeRef.current();
          return;
        }
      }
    };
    rec.onend = () => {
      if (!stopped) {
        try { rec.start(); } catch { /* ignore */ }
      }
    };
    rec.onerror = () => { /* swallow no-speech / not-allowed; onend will restart */ };

    try { rec.start(); } catch { /* ignore */ }
    return () => {
      stopped = true;
      try { rec.stop(); } catch { /* ignore */ }
    };
  }, [active]);
}
```

- [ ] **Step 2: Wire into the provider**

In `apps/web/src/components/veronica/VeronicaProvider.tsx`, import the hook and activate it when the orb is sleeping/idle/unavailable (not during a live session). Add near the top of `VeronicaProvider` (the component that owns `orb` and `connect`):

```tsx
import { useWakeWord } from "@/lib/useWakeWord";
```

Inside `VeronicaProvider`, after `connect`/`onOrbClick` are defined:

```tsx
  const wakeActive = orb === "sleeping" || orb === "idle";
  useWakeWord(wakeActive, () => {
    if (orb === "sleeping" || orb === "idle" || orb === "unavailable") {
      retriedRef.current = false;
      connect();
    }
  });
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/useWakeWord.ts apps/web/src/components/veronica/VeronicaProvider.tsx
git commit -m "feat(veronica): 'Hey Veronica' wake word wakes her from sleep (Web Speech API, click fallback)"
```

---

## Task B3a: Backend — `morning_briefing` flag on the token

**Files:**
- Modify: `apps/api/src/nq_api/routes/livekit_token.py`
- Test: `apps/api/tests/test_livekit_token_briefing.py` (new)

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_livekit_token_briefing.py`:

```python
from nq_api.routes import livekit_token as lt


def test_first_session_of_day_true(monkeypatch):
    monkeypatch.setattr(lt, "_fetch_today_veronica_events", lambda uid: [])
    assert lt._is_first_veronica_today("u1") is True


def test_second_session_of_day_false(monkeypatch):
    monkeypatch.setattr(
        lt, "_fetch_today_veronica_events",
        lambda uid: [{"label": "session_start", "payload": {}}],
    )
    assert lt._is_first_veronica_today("u1") is False


def test_first_check_fails_open_false(monkeypatch):
    def _boom(uid):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(lt, "_fetch_today_veronica_events", _boom)
    assert lt._is_first_veronica_today("u1") is False  # fail closed: no briefing on error
```

- [ ] **Step 2: Run — confirm fail**

Run: `cd apps/api && python -m pytest tests/test_livekit_token_briefing.py -v`
Expected: FAIL — `_is_first_veronica_today` does not exist.

- [ ] **Step 3: Add the helper**

In `apps/api/src/nq_api/routes/livekit_token.py`, after `_veronica_seconds_today`, add:

```python
def _is_first_veronica_today(user_id: str) -> bool:
    """True if the user has no prior veronica session today (drives the morning
    briefing). Must be called BEFORE _log_session_start. Fails closed (False)."""
    try:
        rows = _fetch_today_veronica_events(user_id)
    except Exception:
        return False
    return not any(r.get("label") == "session_start" for r in rows)
```

- [ ] **Step 4: Compute the flag before logging the start, return it**

In `generate_token`, in the `if agent == "veronica":` block, compute the flag BEFORE `_log_session_start` is called (which is at line ~173). Right after `room = f"veronica-{user_id}"` set:

```python
        morning_briefing = _is_first_veronica_today(user_id)
```

For the non-veronica branch, set `morning_briefing = False`. Then in the final `return {...}` dict (the success path with the token), add the key:

```python
    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room,
        "morning_briefing": morning_briefing,
    }
```

Ensure `morning_briefing` is defined on both branches (set `morning_briefing = False` in the `else:` branch so it's always bound).

- [ ] **Step 5: Run tests + sanity-import**

Run: `cd apps/api && python -m pytest tests/test_livekit_token_briefing.py -v`
Run: `cd apps/api && python -c "import nq_api.routes.livekit_token"`
Expected: 3 passed; import clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/routes/livekit_token.py apps/api/tests/test_livekit_token_briefing.py
git commit -m "feat(veronica): token returns morning_briefing flag on first session of the day"
```

---

## Task B3b: Briefing — provider trigger + agent handler

**Files:**
- Modify: `apps/web/src/components/veronica/VeronicaProvider.tsx` (publish briefing trigger on connect)
- Modify: `apps/livekit-agent/src/quantastra/veronica_agent.py` (handle briefing message)

- [ ] **Step 1: Provider — remember the flag and publish once on connect**

In `apps/web/src/components/veronica/VeronicaProvider.tsx`:

(a) Add a ref in `VeronicaProvider` to carry the flag from the token response into the session:

```tsx
  const briefingRef = useRef(false);
```

(b) In `connect`, after `const body = await res.json();`, set it:

```tsx
      briefingRef.current = Boolean(body.morning_briefing);
```

(c) Pass it to the session component:

```tsx
          <VeronicaSession
            setOrb={setOrb}
            onIdleTimeout={() => disconnect("sleeping")}
            briefing={briefingRef.current}
          />
```

(d) Extend `VeronicaSession`'s props and publish a one-time briefing message once the agent participant is present. Update the signature and add an effect:

```tsx
function VeronicaSession({
  setOrb,
  onIdleTimeout,
  briefing,
}: {
  setOrb: (s: OrbState) => void;
  onIdleTimeout: () => void;
  briefing: boolean;
}) {
```

Add (after `agentParticipant` is defined), publish once when the agent has joined:

```tsx
  const briefingSentRef = useRef(false);
  useEffect(() => {
    if (!briefing || briefingSentRef.current || !localParticipant || !agentParticipant) return;
    briefingSentRef.current = true;
    localParticipant
      .publishData(new TextEncoder().encode(JSON.stringify({ type: "briefing" })), {
        reliable: true,
        topic: "veronica",
      })
      .catch(() => {});
  }, [briefing, localParticipant, agentParticipant]);
```

- [ ] **Step 2: Agent — handle the briefing message**

In `apps/livekit-agent/src/quantastra/veronica_agent.py`, in the `_on_data_received` handler, after the existing `page = parse_page_context(msg)` handling, add a branch for the briefing message. Insert before `page = parse_page_context(msg)`:

```python
        if isinstance(msg, dict) and msg.get("type") == "briefing":
            asyncio.ensure_future(_morning_briefing(agent, session))
            return
```

Then define `_morning_briefing` alongside the other inner helpers (near `_narrate`):

```python
    async def _morning_briefing(agent: VeronicaAgent, session: AgentSession) -> None:
        try:
            from quantastra.context import build_greeting_context
            ctx = await build_greeting_context(agent._user_id)
        except Exception:
            ctx = ""
        instructions = (
            "Give a brief spoken morning briefing, 20 to 30 seconds when read aloud. "
            "Cover the market mood and one or two notable moves, then anything relevant "
            "in the user's watchlist or portfolio. Conversational, no lists. "
            + (f"Context to use: {ctx}" if ctx else "If you lack data, keep it short and warm.")
        )
        try:
            session.generate_reply(instructions=instructions)
        except Exception:
            log.exception("Morning briefing failed")
```

Confirm `build_greeting_context` exists in `quantastra/context.py` (it does — `context.py:161`).

- [ ] **Step 3: Typecheck web + compile agent**

Run: `cd apps/web && npx tsc --noEmit`
Run: `cd apps/livekit-agent && python -m py_compile src/quantastra/veronica_agent.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/veronica/VeronicaProvider.tsx apps/livekit-agent/src/quantastra/veronica_agent.py
git commit -m "feat(veronica): spoken morning briefing on first connect of the day"
```

---

## Final verification

- [ ] `cd apps/api && python -m pytest tests/test_live_price.py tests/test_snapshot_price.py tests/test_livekit_token_briefing.py -v` — green
- [ ] `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -v` — green
- [ ] `cd apps/web && npx tsc --noEmit` — clean
- [ ] Manual (post-deploy): Ask Morgan "top picks for 2026" → VLO/BKR/IN names show real entry/target/stop (no "Price unavailable"). Veronica on a stock page → "what am I looking at" → states the on-screen price/score. Sleep Veronica, say "Hey Veronica" (Chrome) → reconnects. First connect of the day → spoken briefing.

## Deploy-time steps
- `nq-api` redeploy (A1/A2/A3, B3a). Requires `OPENBB_ENABLED=true` + `OPENBB_API_URL=https://nq-openbb.onrender.com` already set (they are — openbb calls succeed in prod).
- `quantastra-agent` redeploy (B1a, B3b agent).
- Vercel auto-deploys web on merge (B1b, B2, B3b frontend).
