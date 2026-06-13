# Session 90 Batch Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the portfolio crash, restore IN prices in Ask Morgan, add a PARA-DEBATE progress animation to the QuantAstra voice panel, set Veronica's voice, rebrand QuantAlpha→NeuralQuant across product code, and simplify both agents' greetings.

**Architecture:** Six independent tasks. Frontend = Next.js (App Router) in `apps/web`. Backend = FastAPI in `apps/api`. Voice agent = LiveKit agents in `apps/livekit-agent`. Agent↔frontend talk over a LiveKit data channel (topic `"quantastra"`, JSON `{type: ...}`).

**Tech Stack:** TypeScript/React/Tailwind, Python/FastAPI, LiveKit agents, Supabase (PostgREST), pytest.

Branch already created: `session90-batch-fixes`. Spec: `docs/superpowers/specs/2026-06-13-batch-fixes-branding-voice-design.md`.

---

## Task 1: Fix portfolio geopolitical-scan crash (P0)

**Root cause:** backend `/astra/geopolitical-scan` returns per-ticker warnings `{ticker, sector, risk_level, beta, irs_pct, recommendation}`; frontend type/panel expect `{title, description, severity, affected_sectors[], affected_tickers[]}` and call `w.affected_sectors.length` → `undefined.length` → throws → error boundary.

**Files:**
- Modify: `apps/web/src/lib/types.ts:785-799` (GeopoliticalWarning + response type)
- Modify: `apps/web/src/components/GeopoliticalScanPanel.tsx` (full rewrite of render)
- Modify: `apps/api/src/nq_api/routes/astra_portfolio.py:538-545` (neutral signal: emit `reason`)

- [ ] **Step 1: Update the TS types to the real backend shape**

In `apps/web/src/lib/types.ts`, replace the `GeopoliticalWarning` and `AstraGeopoliticalScanResponse` interfaces (lines 785-800) with:

```ts
export interface GeopoliticalWarning {
  ticker: string;
  sector?: string | null;
  risk_level: "HIGH" | "MEDIUM";
  beta?: number | null;
  irs_pct?: number | null;
  recommendation?: string | null;
}

export interface AstraGeopoliticalScanResponse {
  warnings: GeopoliticalWarning[];
  total_scanned: number;
  warning_count?: number;
  sebi_disclaimer?: string;
}
```

- [ ] **Step 2: Rewrite `GeopoliticalScanPanel` to render per-ticker warnings with guards**

Replace the whole body of `apps/web/src/components/GeopoliticalScanPanel.tsx` with:

```tsx
"use client";

import { useEffect, useState } from "react";
import { authedApi } from "@/lib/api";
import type { GeopoliticalWarning } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { Globe, Loader2 } from "lucide-react";
import Link from "next/link";

function riskStyles(level: "HIGH" | "MEDIUM") {
  return level === "HIGH"
    ? "bg-red-500/5 border-red-500/20"
    : "bg-amber-500/5 border-amber-500/20";
}

function riskBadge(level: "HIGH" | "MEDIUM") {
  const cls =
    level === "HIGH"
      ? "bg-red-500/15 text-red-400 border-red-500/30"
      : "bg-amber-500/15 text-amber-400 border-amber-500/30";
  return (
    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${cls}`}>
      {level}
    </span>
  );
}

export default function GeopoliticalScanPanel({ market = "IN" }: { market?: "US" | "IN" | "GLOBAL" }) {
  const [warnings, setWarnings] = useState<GeopoliticalWarning[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalScanned, setTotalScanned] = useState(0);

  useEffect(() => {
    authedApi.getAstraGeopoliticalScan(market)
      .then((data) => {
        setWarnings(Array.isArray(data?.warnings) ? data.warnings : []);
        setTotalScanned(data?.total_scanned ?? 0);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Scan failed"))
      .finally(() => setLoading(false));
  }, [market]);

  if (loading) {
    return (
      <GhostBorderCard>
        <div className="flex items-center justify-center py-6 gap-2">
          <Loader2 size={16} className="animate-spin text-primary" />
          <span className="text-sm text-on-surface-variant">Scanning geopolitical risks…</span>
        </div>
      </GhostBorderCard>
    );
  }

  if (error) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <p className="text-sm text-error">{error}</p>
        </div>
      </GhostBorderCard>
    );
  }

  if (warnings.length === 0) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <Globe size={24} className="mx-auto text-primary-fixed mb-2" />
          <p className="text-sm text-on-surface-variant">No geopolitical risk warnings detected for your portfolio.</p>
          {totalScanned > 0 && (
            <p className="text-[10px] text-on-surface-variant mt-1">{totalScanned} holdings scanned</p>
          )}
        </div>
      </GhostBorderCard>
    );
  }

  const highCount = warnings.filter((w) => w.risk_level === "HIGH").length;
  const medCount = warnings.filter((w) => w.risk_level === "MEDIUM").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe size={16} className="text-primary-fixed" />
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-on-surface">
            Geopolitical Risk Scan
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {highCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
              {highCount} HIGH
            </span>
          )}
          {medCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
              {medCount} MEDIUM
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {warnings.map((w, i) => (
          <Link
            key={`${w.ticker}-${i}`}
            href={`/stocks/${w.ticker}?market=${market}`}
            className={`block rounded-lg ghost-border p-3 space-y-1.5 ${riskStyles(w.risk_level)}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-headline text-sm font-bold text-on-surface">{w.ticker}</span>
              {riskBadge(w.risk_level)}
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-on-surface-variant">
              {w.sector && <span>{w.sector}</span>}
              {w.beta != null && <span>β {w.beta.toFixed(2)}</span>}
              {w.irs_pct != null && <span>IRS {w.irs_pct.toFixed(0)}%</span>}
            </div>
            {w.recommendation && (
              <p className="text-[11px] text-on-surface">{w.recommendation}</p>
            )}
          </Link>
        ))}
      </div>

      <p className="text-[9px] text-on-surface-variant text-center">
        {totalScanned} holdings scanned · Geopolitically sensitive sectors flagged from your watchlist
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Add defensive guards to `SellSignalsPanel`**

In `apps/web/src/components/SellSignalsPanel.tsx`, change the `.then` body (lines 18-21) to:

```tsx
      .then((data) => {
        setSellSignals(Array.isArray(data?.sell_signals) ? data.sell_signals : []);
        setNeutralSignals(Array.isArray(data?.neutral_signals) ? data.neutral_signals : []);
      })
```

- [ ] **Step 4: Backend — neutral sell-signal emits `reason` (so the panel text isn't blank)**

In `apps/api/src/nq_api/routes/astra_portfolio.py`, the neutral branch (around line 538) currently sets `"note"`. Add a `"reason"` key alongside it:

```python
            neutral_signals.append({
                "ticker": ticker,
                "market": market,
                "g_score": g,
                "irs_pct": row.get("irs_pct"),
                "reason": "May take significant time to show returns",
                "note": "May take significant time to show returns",
                "sector": row.get("sector"),
            })
```

- [ ] **Step 5: Typecheck the web app**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no errors in `GeopoliticalScanPanel.tsx`, `SellSignalsPanel.tsx`, `types.ts`.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/types.ts apps/web/src/components/GeopoliticalScanPanel.tsx apps/web/src/components/SellSignalsPanel.tsx apps/api/src/nq_api/routes/astra_portfolio.py
git commit -m "fix(portfolio): geopolitical-scan contract mismatch crashed the page

Backend returns per-ticker warnings; frontend expected per-event shape and
called undefined.length on a missing array. Render the real shape, add
defensive array guards, and emit reason on neutral sell-signals."
```

---

## Task 2: Restore IN prices in Ask Morgan via stock_snapshot (P1)

**Root cause:** the 6-tier price cascade in `portfolio.py` exhausts for IN tickers (FMP no IN quote, yfinance blocked on Render, score_cache may lack the row). `stock_snapshot` (dedicated `price` column, refreshed every 30 min by GitHub Actions running yfinance unguarded) is never queried.

**Files:**
- Modify: `apps/api/src/nq_api/services/portfolio.py` (new helper + new tier)
- Test: `apps/api/tests/test_snapshot_price.py` (new)

- [ ] **Step 1: Write the failing test for a `_snapshot_price` helper**

Create `apps/api/tests/test_snapshot_price.py`:

```python
from nq_api.services import portfolio


def test_snapshot_price_returns_price(monkeypatch):
    monkeypatch.setattr(
        portfolio, "read_snapshot",
        lambda ticker, market: {"ticker": ticker, "market": market, "price": 3500.0},
    )
    assert portfolio._snapshot_price("TCS", "IN") == 3500.0


def test_snapshot_price_none_when_missing(monkeypatch):
    monkeypatch.setattr(portfolio, "read_snapshot", lambda ticker, market: None)
    assert portfolio._snapshot_price("TCS", "IN") is None


def test_snapshot_price_none_when_price_zero(monkeypatch):
    monkeypatch.setattr(
        portfolio, "read_snapshot",
        lambda ticker, market: {"price": 0},
    )
    assert portfolio._snapshot_price("TCS", "IN") is None
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd apps/api && python -m pytest tests/test_snapshot_price.py -v`
Expected: FAIL — `AttributeError: module 'nq_api.services.portfolio' has no attribute 'read_snapshot'` / `_snapshot_price`.

- [ ] **Step 3: Add the import and helper to `portfolio.py`**

Near the top of `apps/api/src/nq_api/services/portfolio.py` (with the other imports), add:

```python
from nq_api.cache.snapshot_cache import read_snapshot
```

Then add this module-level helper (above the price-fill function):

```python
def _snapshot_price(ticker: str, market: str) -> float | None:
    """Live price from public.stock_snapshot (refreshed every 30 min, has IN prices
    that Render's blocked yfinance cannot fetch). Returns None when absent or <= 0."""
    try:
        row = read_snapshot(ticker.upper(), market)
        if row and row.get("price"):
            p = float(row["price"])
            return p if p > 0 else None
    except Exception:
        return None
    return None
```

- [ ] **Step 4: Run the helper tests — they pass**

Run: `cd apps/api && python -m pytest tests/test_snapshot_price.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire the tier into the cascade (before the score_cache tier)**

In `apps/api/src/nq_api/services/portfolio.py`, immediately before the `# -- Tier 5: score_cache` block (currently line 211), insert:

```python
        # -- Tier 4b: stock_snapshot (30-min refresh, reliable for IN on Render) --
        if not live_price or live_price <= 0:
            snap_price = _snapshot_price(ticker, stock_market)
            if snap_price:
                live_price = snap_price
                price_source = "stock_snapshot"
                fill_notes.append(f"{ticker} price: stock_snapshot ({live_price:.2f})")
```

- [ ] **Step 6: Sanity-import the module**

Run: `cd apps/api && python -c "import nq_api.services.portfolio"`
Expected: no error.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/nq_api/services/portfolio.py apps/api/tests/test_snapshot_price.py
git commit -m "fix(portfolio): add stock_snapshot price tier so IN stocks stop showing 'Price unavailable'

FMP has no IN quote and yfinance is blocked on Render; stock_snapshot is
refreshed every 30 min by GitHub Actions and carries IN prices. Query it
before falling through to stale score_cache."
```

---

## Task 3: PARA-DEBATE progress animation in QuantAstra voice panel (P1)

**Approach:** the `run_para_debate` tool publishes `started`/`complete` events over the existing `"quantastra"` data channel; the frontend reveals the 7 agent stages on a timed sequence anchored by those events.

**Files:**
- Modify: `apps/livekit-agent/src/quantastra/tools/research_tools.py` (publish events)
- Create: `apps/web/src/components/quantastra/DebateProgressPanel.tsx`
- Modify: `apps/web/src/components/quantastra/QuantAstraCallView.tsx` (handle event + render panel)

- [ ] **Step 1: Publish a `debate_progress` "started" event before the analysis**

In `apps/livekit-agent/src/quantastra/tools/research_tools.py`, add a small publish helper to `ResearchToolsMixin` and call it. Replace the body of `run_para_debate` between the docstring and the `try:` with the publish, and emit at start/complete/error. The full edited method:

```python
    async def _publish_debate(self, payload: dict) -> None:
        participant = getattr(self, "_participant", None)
        if not participant:
            return
        try:
            await participant.publish_data(
                json.dumps(payload), reliable=True, topic="quantastra"
            )
        except Exception:
            log.debug("Failed to publish debate_progress", exc_info=True)

    @function_tool
    async def run_para_debate(
        self,
        ticker: str,
        market: str = "US",
    ) -> str:
        """Run a full 7-agent PARA-DEBATE analysis on a stock. This invokes 7 AI agents
        (Fundamental, Technical, Macro, Sentiment, Geopolitical, Adversarial, and
        Head Analyst) that debate the stock from all angles and produce an investment
        verdict with bull/bear cases and risk factors. Takes 30-60 seconds.

        Use ONLY when the client specifically requests deep analysis, a full research
        report, or wants to understand all sides of an investment thesis. For simple
        price checks or quick opinions, use get_stock_price instead.

        Parameters:
            ticker: Stock ticker symbol, e.g. 'AAPL' or 'RELIANCE'
            market: Market — 'US' or 'IN'
        """
        await self._publish_debate({"type": "debate_progress", "phase": "started", "ticker": ticker, "market": market})
        try:
            from nq_api.agents.orchestrator import ParaDebateOrchestrator
            from nq_api.data_builder import _fetch_one, fetch_real_macro

            fund = _fetch_one(ticker, market, fast_pe=True)
            if fund is None:
                await self._publish_debate({"type": "debate_progress", "phase": "error", "ticker": ticker})
                return json.dumps({"status": "unavailable", "ticker": ticker, "reason": "Could not fetch fundamental data — FMP/yfinance may be unavailable"})

            macro = fetch_real_macro()
            context = {**fund, **vars(macro)}

            orch = ParaDebateOrchestrator()
            result = await orch.analyse(ticker, market, context)

            agent_breakdown = []
            if result.agent_outputs:
                for o in result.agent_outputs:
                    agent_breakdown.append({
                        "agent": o.agent,
                        "stance": o.stance,
                        "conviction": o.conviction,
                    })

            await self._publish_debate({
                "type": "debate_progress", "phase": "complete", "ticker": ticker,
                "verdict": result.head_analyst_verdict, "consensus_score": result.consensus_score,
            })
            return json.dumps({
                "status": "ok",
                "ticker": ticker,
                "market": market,
                "verdict": result.head_analyst_verdict,
                "investment_thesis": result.investment_thesis,
                "bull_case": result.bull_case,
                "bear_case": result.bear_case,
                "risk_factors": result.risk_factors[:5],
                "consensus_score": result.consensus_score,
                "agent_breakdown": agent_breakdown,
            }, default=str)
        except Exception as exc:
            log.error("run_para_debate failed for %s/%s: %s", ticker, market, exc)
            await self._publish_debate({"type": "debate_progress", "phase": "error", "ticker": ticker})
            return json.dumps({
                "status": "error",
                "ticker": ticker,
                "reason": "The deep analysis engine is temporarily unavailable — try again in a moment, or use get_stock_price for a quick overview.",
            })
```

- [ ] **Step 2: Sanity-import the agent module**

Run: `cd apps/livekit-agent && python -c "import quantastra.tools.research_tools"`
Expected: no error.

- [ ] **Step 3: Create the `DebateProgressPanel` component**

Create `apps/web/src/components/quantastra/DebateProgressPanel.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, BrainCircuit } from "lucide-react";

const ANALYSTS = [
  "Macro",
  "Fundamental",
  "Technical",
  "Sentiment",
  "Geopolitical",
  "Adversarial",
] as const;

export interface DebateState {
  ticker: string;
  phase: "started" | "complete" | "error";
  verdict?: string | null;
  consensusScore?: number | null;
}

// Reveal the 6 parallel analysts over ~24s, then hold on Head Analyst until `complete`.
export default function DebateProgressPanel({ state }: { state: DebateState }) {
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    if (state.phase !== "started") {
      setRevealed(ANALYSTS.length);
      return;
    }
    setRevealed(0);
    const timers = ANALYSTS.map((_, i) =>
      setTimeout(() => setRevealed((r) => Math.max(r, i + 1)), (i + 1) * 4000)
    );
    return () => timers.forEach(clearTimeout);
  }, [state.phase, state.ticker]);

  const done = state.phase === "complete";
  const failed = state.phase === "error";

  return (
    <div className="mx-auto my-4 w-full max-w-sm rounded-lg border border-ghost-border bg-surface-container/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <BrainCircuit size={16} className="text-primary-fixed" />
        <span className="text-xs font-mono uppercase tracking-wider text-on-surface">
          PARA-DEBATE · {state.ticker}
        </span>
      </div>

      <ul className="space-y-1.5">
        {ANALYSTS.map((name, i) => {
          const active = !done && !failed && i === revealed;
          const finished = done || i < revealed;
          return (
            <li key={name} className="flex items-center gap-2 text-xs">
              {finished ? (
                <Check size={13} className="text-primary-fixed" />
              ) : active ? (
                <Loader2 size={13} className="animate-spin text-primary" />
              ) : (
                <span className="inline-block h-[13px] w-[13px] rounded-full border border-ghost-border" />
              )}
              <span className={finished ? "text-on-surface" : "text-on-surface-variant"}>
                {name} analyst
              </span>
            </li>
          );
        })}
        <li className="mt-1 flex items-center gap-2 border-t border-ghost-border pt-2 text-xs">
          {done ? (
            <Check size={13} className="text-primary-fixed" />
          ) : failed ? (
            <span className="inline-block h-[13px] w-[13px] rounded-full border border-error" />
          ) : (
            <Loader2 size={13} className="animate-spin text-primary" />
          )}
          <span className="font-medium text-on-surface">
            {done ? "Head Analyst — verdict ready" : failed ? "Analysis unavailable" : "Head Analyst synthesizing…"}
          </span>
        </li>
      </ul>

      {done && state.verdict && (
        <p className="mt-3 text-center text-sm font-bold text-primary-fixed">
          {state.verdict}
          {state.consensusScore != null && (
            <span className="ml-2 font-mono text-xs text-on-surface-variant">
              consensus {state.consensusScore}
            </span>
          )}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire the event + render into `QuantAstraCallView`**

In `apps/web/src/components/quantastra/QuantAstraCallView.tsx`:

(a) Add the import near the other component imports:

```tsx
import DebateProgressPanel, { type DebateState } from "./DebateProgressPanel";
```

(b) Add state near the other `useState` hooks (after `whiteboardContent`):

```tsx
  const [debate, setDebate] = useState<DebateState | null>(null);
```

(c) Add a `case` to the `useDataChannel` switch (after the `whiteboard_update` case, before the closing `}`):

```tsx
          case "debate_progress":
            setDebate({
              ticker: data.ticker ?? "",
              phase: data.phase ?? "started",
              verdict: data.verdict ?? null,
              consensusScore: data.consensus_score ?? null,
            });
            if (data.phase === "complete" || data.phase === "error") {
              setTimeout(() => setDebate(null), 8000);
            }
            break;
```

(d) Render the panel above the transcript. Inside the `else` branch (the transcript-only layout), add the panel just inside the wrapping `<div className="flex flex-1 flex-col overflow-hidden border-t border-ghost-border">`, before the inner scroll div:

```tsx
          {debate && <DebateProgressPanel state={debate} />}
```

- [ ] **Step 5: Typecheck the web app**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no errors in `DebateProgressPanel.tsx` / `QuantAstraCallView.tsx`.

- [ ] **Step 6: Commit**

```bash
git add apps/livekit-agent/src/quantastra/tools/research_tools.py apps/web/src/components/quantastra/DebateProgressPanel.tsx apps/web/src/components/quantastra/QuantAstraCallView.tsx
git commit -m "feat(quantastra): show PARA-DEBATE stage progress in the voice panel

run_para_debate publishes started/complete events over the data channel;
the panel reveals the 6 analysts then holds on Head Analyst until the
verdict arrives, mitigating the black-box wait."
```

---

## Task 4: Set Veronica's voice to `kdnRe2koJdOK4Ovxn2DI`

**Files:**
- Modify: `apps/livekit-agent/src/quantastra/veronica_agent.py:34`

- [ ] **Step 1: Change the default voice id**

In `apps/livekit-agent/src/quantastra/veronica_agent.py`, line 34, change:

```python
VERONICA_VOICE_ID = os.getenv("VERONICA_VOICE_ID", "XB0fDUnXU5powFXDhCwa")
```
to:
```python
VERONICA_VOICE_ID = os.getenv("VERONICA_VOICE_ID", "kdnRe2koJdOK4Ovxn2DI")
```

Also update the comment on line 33 to drop the "Charlotte" reference:

```python
# Veronica's ElevenLabs voice. Override per-env with VERONICA_VOICE_ID.
```

- [ ] **Step 2: Sanity-import**

Run: `cd apps/livekit-agent && python -c "import quantastra.veronica_agent"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_agent.py
git commit -m "feat(veronica): set default ElevenLabs voice to kdnRe2koJdOK4Ovxn2DI"
```

- [ ] **Step 4: Deploy-time (not code) — set Render env**

On the Render `livekit-agent` worker service, set env var `VERONICA_VOICE_ID=kdnRe2koJdOK4Ovxn2DI`, then redeploy the worker. (Do via Render MCP `update_environment_variables` or note for manual set. Worker must pick up the change.)

---

## Task 5: Rebrand "QuantAlpha" → "NeuralQuant" across product code

**Scope:** `apps/web`, `apps/api`, `apps/livekit-agent` + `apps/web/public`. **Do NOT touch** `docs/`, `memory/`, `offTopic/`, `linkedin_company_post.txt`. Brand string: `NeuralQuant` (one word). Never touch the unrelated word `quantastra`.

**Files (product files containing `QuantAlpha`, from grep):**
`apps/web/src/components/ui/MarketWrapCard.tsx`, `apps/web/src/components/ui/InstallPWA.tsx`, `apps/web/src/components/ui/AIResponseCard.tsx`, `apps/api/src/nq_api/services/enrichment.py`, `apps/api/src/nq_api/services/constants.py`, `apps/api/src/nq_api/routes/astra_portfolio.py`, `apps/api/src/nq_api/routes/testing.py`, `apps/api/src/nq_api/routes/stocks.py`, `apps/web/src/components/NLQueryBox.tsx`, `apps/web/src/components/layout/SideNavBar.tsx`, `apps/web/src/components/layout/MobileDrawer.tsx`, `apps/web/src/components/landing/SEBIDisclaimer.tsx`, `apps/web/src/components/onboarding/WalkthroughProvider.tsx`, `apps/web/src/components/landing/LandingPage.tsx`, `apps/web/src/app/globals.css`, `apps/web/src/app/broker/BrokerPageClient.tsx`, `apps/web/src/app/stocks/[ticker]/page.tsx`, `apps/web/src/app/best-stocks/[sector]/page.tsx`, `apps/web/src/app/signup/page.tsx`, `apps/livekit-agent/src/quantastra/veronica_persona.py`, `apps/livekit-agent/src/quantastra/veronica_logic.py`, `apps/web/src/app/api/og/analysis/[id]/route.tsx`, `apps/web/src/app/screener/page.tsx`, `apps/web/src/app/layout.tsx`, `apps/web/src/app/query/page.tsx`, `apps/web/src/app/hermes/page.tsx`, `apps/web/src/app/methodology/page.tsx`, `apps/web/src/app/hermes/layout.tsx`, `apps/web/src/app/login/page.tsx`, `apps/web/src/app/pricing/page.tsx`, `apps/web/src/app/portfolio/page.tsx`, `apps/livekit-agent/src/quantastra/context.py`, `apps/livekit-agent/src/quantastra/persona.py`

- [ ] **Step 1: Replace `QuantAlpha` → `NeuralQuant` in every product file**

For each file listed above, replace all occurrences of `QuantAlpha` with `NeuralQuant` (use Edit with `replace_all: true` per file). This includes phrases like "QuantAlpha AI", "QuantAlpha Capital", "QuantAlpha" → "NeuralQuant AI" (becomes "NeuralQuant AI"; if a literal "QuantAlpha AI" reads awkward as "NeuralQuant AI" keep it — it's correct), "NeuralQuant Capital", "NeuralQuant".

- [ ] **Step 2: Bump the service-worker cache key (lowercase identifier)**

In `apps/web/public/sw.js`, line 3, change:

```js
const CACHE = "quantalpha-v2";
```
to:
```js
const CACHE = "neuralquant-v1";
```

- [ ] **Step 3: Sweep for remaining lowercase `quantalpha` identifiers in product code**

Run (case-insensitive) and replace any remaining product-code hits (manifest name, package fields, CSS classes, etc.). Do NOT edit `docs/`, `memory/`, `offTopic/`:

Run: `git grep -in "quantalpha" -- apps/`
Expected after fixes: **no output**. For each hit, replace `quantalpha`→`neuralquant` preserving case (`QuantAlpha`→`NeuralQuant`, `quantalpha`→`neuralquant`, `QUANTALPHA`→`NEURALQUANT`).

- [ ] **Step 4: Verify the sweep is clean in product code**

Run: `git grep -il "quantalpha" -- apps/`
Expected: no output.

- [ ] **Step 5: Typecheck web + sanity-import python**

Run: `cd apps/web && npx tsc --noEmit`
Run: `cd apps/api && python -c "import nq_api.services.constants, nq_api.services.enrichment, nq_api.routes.stocks"`
Run: `cd apps/livekit-agent && python -c "import quantastra.persona, quantastra.context, quantastra.veronica_persona, quantastra.veronica_logic"`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/
git commit -m "chore(brand): rename QuantAlpha -> NeuralQuant across product code

UI strings, personas, disclaimers, meta tags, and the service-worker cache
key (neuralquant-v1, one clean cache bust). Historical docs/memory left as-is."
```

---

## Task 6: Simplify greetings to "Hey there" (no name/email, keep session recall)

**Files:**
- Modify: `apps/livekit-agent/src/quantastra/context.py:33-55` (build_personalized_greeting)
- Modify: `apps/livekit-agent/src/quantastra/persona.py:164-165` (INITIAL_GREETING)
- Modify: `apps/livekit-agent/src/quantastra/veronica_logic.py:51-63` (build_veronica_greeting)
- Test: `apps/livekit-agent/tests/test_veronica_logic.py` (append)

> Note: Task 5 already renames `QuantAlpha`→`NeuralQuant` in these files. The greeting wording below uses `NeuralQuant`. If Task 6 runs before Task 5, the rename still catches it.

- [ ] **Step 1: Write the failing greeting test**

Append to `apps/livekit-agent/tests/test_veronica_logic.py`:

```python
from quantastra.veronica_logic import build_veronica_greeting


def test_veronica_greeting_starts_hey_there_no_name():
    g = build_veronica_greeting("Satyam")
    assert g.startswith("Hey there")
    assert "Satyam" not in g


def test_veronica_greeting_anon_starts_hey_there():
    g = build_veronica_greeting(None)
    assert g.startswith("Hey there")
```

- [ ] **Step 2: Run it to confirm failure**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -k greeting -v`
Expected: FAIL — current greeting starts with "Hi" and interpolates the name.

- [ ] **Step 3: Rewrite `build_veronica_greeting` to ignore the name**

In `apps/livekit-agent/src/quantastra/veronica_logic.py`, replace `build_veronica_greeting` (lines 51-63) with:

```python
def build_veronica_greeting(name: str | None = None) -> str:
    """First spoken utterance after the user enables Veronica.

    `name` is accepted for caller compatibility but intentionally unused — the
    greeting stays a simple 'Hey there'.
    """
    return (
        "Hey there, Veronica here — your companion across NeuralQuant. "
        "I'm with you on every page. Just speak whenever something "
        "catches your eye and I'll explain it."
    )
```

- [ ] **Step 4: Run the greeting test — passes**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -k greeting -v`
Expected: 2 passed.

- [ ] **Step 5: Update QuantAstra's personalized greeting (keep session recall, drop name)**

In `apps/livekit-agent/src/quantastra/context.py`, replace `build_personalized_greeting` (lines 33-55) with:

```python
async def build_personalized_greeting(user_id: str) -> str:
    """Build the agent's first spoken utterance. Opens with a simple 'Hey there'
    (no name/email) but keeps last-session recall for returning users."""
    last_summary = await _fetch_last_session_summary(user_id)

    if last_summary:
        return (
            "Hey there, welcome back. In our last session we talked about "
            f"{last_summary} What's on your mind today?"
        )

    from quantastra.persona import INITIAL_GREETING
    return INITIAL_GREETING
```

- [ ] **Step 6: Update `INITIAL_GREETING` to open with "Hey there"**

In `apps/livekit-agent/src/quantastra/persona.py`, lines 164-165, change the opening:

```python
INITIAL_GREETING = (
    "Hey there. I'm QuantAstra, your portfolio manager at NeuralQuant. "
```
(Keep the rest of the string unchanged. The `NeuralQuant` here matches the Task 5 rename.)

- [ ] **Step 7: Run the full agent test suite + sanity-imports**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -v`
Run: `cd apps/livekit-agent && python -c "import quantastra.context, quantastra.persona, quantastra.veronica_logic"`
Expected: tests pass, imports clean.

- [ ] **Step 8: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_logic.py apps/livekit-agent/src/quantastra/context.py apps/livekit-agent/src/quantastra/persona.py apps/livekit-agent/tests/test_veronica_logic.py
git commit -m "feat(agents): greet with a simple 'Hey there' (no name/email), keep session recall"
```

---

## Final verification

- [ ] `cd apps/web && npx tsc --noEmit` — clean
- [ ] `cd apps/api && python -m pytest tests/test_snapshot_price.py -v` — green
- [ ] `cd apps/livekit-agent && python -m pytest -v` — green
- [ ] `git grep -il "quantalpha" -- apps/` — no output
- [ ] Manual (post-deploy): `/portfolio` IN + US tabs load without "Something went wrong"; Ask Morgan shows IN prices; QuantAstra deep-dive shows the stage panel; Veronica greets "Hey there" in the new voice.

## Deploy-time steps (tracked separately from code)
- Render `livekit-agent` worker: set `VERONICA_VOICE_ID=kdnRe2koJdOK4Ovxn2DI`, redeploy.
- Render `nq-api`: redeploy for portfolio/price fixes.
- Vercel `apps/web`: auto-deploys on merge (verify build).
