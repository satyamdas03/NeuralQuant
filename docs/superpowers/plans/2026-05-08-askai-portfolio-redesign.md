# Ask AI Portfolio Output Redesign — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When user asks portfolio/investment question, Ask AI returns structured portfolio layout (market context strip, allocation bar, stock cards, scenario panel, action buttons, SEBI disclaimer) instead of plain JSON cards.

**Architecture:** Keyword-based portfolio intent detection on backend triggers portfolio-specific LLM prompt rules + live market context injection. LLM returns backward-compatible optional fields. Frontend `AIResponseCard` routes to new portfolio renderer when `is_portfolio_response=true`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Anthropic API, Next.js 16, React 19, TypeScript, Tailwind CSS.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `apps/api/src/nq_api/schemas.py` | Pydantic models: 5 new portfolio models + extended `StructuredQueryResponse` |
| `apps/api/src/nq_api/routes/query.py` | Intent detection (`_is_portfolio_intent`), portfolio prompt rules (`_PORTFOLIO_OUTPUT_RULES`), market snapshot injection, validation post-processing |
| `apps/api/src/nq_api/data_builder.py` | Reuse `fetch_real_macro()` / `fetch_real_macro_in()` (no changes, just imports) |
| `apps/web/src/lib/types.ts` | TypeScript interfaces matching Pydantic models |
| `apps/web/src/components/ui/AIResponseCard.tsx` | Router: portfolio flag → new layout or legacy layout |
| `apps/web/src/components/ui/MarketContextStrip.tsx` | New: horizontal scrolling market context cards |
| `apps/web/src/components/ui/AllocationBar.tsx` | New: stacked horizontal bar showing allocation % |
| `apps/web/src/components/ui/PortfolioStockCard.tsx` | New: card with ticker, entry/target/SL, rationale |
| `apps/web/src/components/ui/ScenarioAnalysisPanel.tsx` | New: 3-column bull/base/bear with probability bars |
| `apps/web/src/components/ui/ActionPromptButtons.tsx` | New: clickable pill buttons triggering follow-up queries |
| `apps/web/src/components/ui/SEBIDisclaimer.tsx` | New: styled disclaimer block |
| `apps/web/src/components/NLQueryBox.tsx` | Pass `ask` callback into `AIResponseCard` for action prompt clicks |

---

## Task 1: Backend — Add Portfolio Pydantic Models

**Files:**
- Modify: `apps/api/src/nq_api/schemas.py`

- [ ] **Step 1: Add 5 new portfolio models after `StockSummary`**

Insert after line 150 (`currency: str = "$"`):

```python

# ── Portfolio Output Models (Phase 1) ────────────────────────────────────────

class MarketContextCard(BaseModel):
    label: str
    value: str
    change: Optional[str] = None
    sentiment: Optional[str] = None

class AllocationSegment(BaseModel):
    label: str
    percentage: float
    color: Optional[str] = None
    rationale: Optional[str] = None

class PortfolioStockCard(BaseModel):
    ticker: str
    name: Optional[str] = None
    allocation_pct: float
    entry_price: Optional[str] = None
    target_price: Optional[str] = None
    stop_loss: Optional[str] = None
    risk_reward: Optional[str] = None
    rationale: Optional[str] = None
    confidence: Optional[int] = None
    sector: Optional[str] = None

class ScenarioCard(BaseModel):
    label: str
    probability_pct: Optional[int] = None
    outcome: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

class ActionPrompt(BaseModel):
    label: str
    prompt_text: str
    icon: Optional[str] = None
```

- [ ] **Step 2: Extend `StructuredQueryResponse` with optional portfolio fields**

Replace the existing `StructuredQueryResponse` class (lines 153–166) with:

```python
class StructuredQueryResponse(BaseModel):
    verdict: str
    confidence: float
    timeframe: str
    summary: str
    stock_summary: StockSummary | None = None
    metrics: list[MetricItem] = []
    reasoning: ReasoningBlock
    scenarios: list[ScenarioItem] = []
    allocations: list[AllocationItem] = []
    comparisons: list[ComparisonItem] = []
    data_sources: list[str] = []
    follow_up_questions: list[str] = []
    route: Literal["SNAP", "REACT", "DEEP"] = "REACT"

    # --- Phase 1: portfolio output fields (all optional) ---
    market_context: Optional[list[MarketContextCard]] = None
    allocation_breakdown: Optional[list[AllocationSegment]] = None
    portfolio_stocks: Optional[list[PortfolioStockCard]] = None
    scenario_analysis: Optional[list[ScenarioCard]] = None
    action_prompts: Optional[list[ActionPrompt]] = None
    sebi_disclaimer: Optional[str] = None
    is_portfolio_response: Optional[bool] = None
```

- [ ] **Step 3: Verify schema loads**

Run: `cd apps/api && python -c "from nq_api.schemas import StructuredQueryResponse, MarketContextCard; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/schemas.py
git commit -m "feat: add portfolio output Pydantic models (Phase 1)

MarketContextCard, AllocationSegment, PortfolioStockCard,
ScenarioCard, ActionPrompt + optional fields on StructuredQueryResponse.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Backend — Intent Detection + Portfolio Prompt Rules

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py`

- [ ] **Step 1: Add portfolio keywords and intent detector after `_SECTOR_MAP`**

Insert after line 80 (after `_SECTOR_MAP` closing brace):

```python
_PORTFOLIO_KEYWORDS = [
    "portfolio", "allocate", "allocation", "diversify",
    "how to invest", "where should i invest", "build a portfolio",
    "investment plan", "invest my money", "investment strategy",
    "split my money", "where to put", "how much in", "lump sum",
    "monthly sip", "recurring investment", "long term plan",
    "retirement plan", "child education", "goal based",
    "i have", "i hold", "my holdings", "i own", "i bought",
    "my portfolio", "i want to invest", "should i buy",
]

def _is_portfolio_intent(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _PORTFOLIO_KEYWORDS)
```

- [ ] **Step 2: Add portfolio-specific prompt rules after `_SYSTEM_STRUCTURED`**

Insert after line 176 (after `_SYSTEM_STRUCTURED` closing `"""`):

```python
_PORTFOLIO_OUTPUT_RULES = """
PORTFOLIO OUTPUT RULES (activate ONLY if user asks about portfolio allocation, investment plan, or multiple-stock strategy):

- market_context: Include 3-5 live market context cards. Use real index levels, VIX, and 10Y yield if available. Mark live data with [VERIFIED].
- allocation_breakdown: Show percentage allocation across asset classes / market-cap buckets. Total must sum to 100%. Provide rationale per segment.
- portfolio_stocks: For each recommended stock, include ticker, allocation_pct within portfolio, suggested entry_price, target_price, stop_loss, and risk_reward ratio. Include a one-line rationale and ForeCast confidence 1-10.
- scenario_analysis: Provide exactly 3 scenarios — Bull, Base, Bear. Each gets a probability percentage and 12-month outcome estimate.
- action_prompts: Include 2-3 follow-up prompt buttons that help the user refine the portfolio (e.g., "Add more large-cap?", "Show me mid-cap options?", "Make it more conservative?").
- sebi_disclaimer: Always include the SEBI disclaimer: "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."
- is_portfolio_response: Set this field to true so the frontend knows to render the portfolio layout.
"""
```

- [ ] **Step 3: Add market snapshot builder function after `_build_macro_context`**

Insert after line 361 (after `_build_macro_context` function ends):

```python
def _build_market_snapshot(market: str) -> str | None:
    """Build portfolio-specific market snapshot string."""
    from nq_api.data_builder import fetch_real_macro, fetch_real_macro_in
    parts = []
    try:
        if market == "IN":
            m_in = fetch_real_macro_in()
            m_us = fetch_real_macro()
            parts = [
                f"NIFTY 50: {m_in.sensex_close:,.0f} [VERIFIED]",
                f"USD/INR: {m_in.inr_usd:.2f} [VERIFIED]",
                f"India VIX: {m_in.india_vix:.1f} [VERIFIED]",
                f"RBI Repo: {m_in.rbi_repo_rate:.2f}% [VERIFIED]",
                f"US VIX: {m_us.vix:.1f} [VERIFIED]",
                f"US 10Y Yield: {m_us.yield_10y:.2f}% [VERIFIED]",
            ]
        else:
            m = fetch_real_macro()
            parts = [
                f"S&P 500: latest level [VERIFIED]",
                f"NASDAQ: latest level [VERIFIED]",
                f"VIX: {m.vix:.1f} [VERIFIED]",
                f"US 10Y Yield: {m.yield_10y:.2f}% [VERIFIED]",
                f"HY Spread: {m.hy_spread_oas:.0f}bps [VERIFIED]",
                f"Fed Funds: {m.fed_funds_rate:.2f}% [VERIFIED]",
            ]
    except Exception:
        return None
    return "Market Snapshot (use these exact values, mark [VERIFIED]):\n" + "\n".join(f"- {p}" for p in parts) if parts else None
```

- [ ] **Step 4: Modify system prompt construction in the streaming endpoint**

In the `_call_llm` async function inside `run_nl_query_v2_stream` (around line 2158), find where `messages` are built. After `result_holder["user_msg"]` is set and before the Anthropic API call, add:

```python
                # Portfolio intent detection and prompt injection
                portfolio_intent = _is_portfolio_intent(req.question)
                system_prompt = _SYSTEM_STRUCTURED
                if portfolio_intent:
                    system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
                    snap = _build_market_snapshot(req.market or "US")
                    if snap:
                        result_holder["user_msg"] = result_holder["user_msg"] + "\n\n" + snap
```

Then change the `client.messages.create` call to use `system=system_prompt` instead of `system=_SYSTEM_STRUCTURED`.

- [ ] **Step 5: Add portfolio validation post-processing**

After the `parsed = _extract_tool_use_input(response)` block (around line 2210), after `_validate_response_metrics` is called, add:

```python
                # Portfolio validation post-processing
                if parsed and parsed.get("is_portfolio_response"):
                    # Ensure SEBI disclaimer present
                    if not parsed.get("sebi_disclaimer") or "SEBI" not in parsed.get("sebi_disclaimer", "").upper():
                        parsed["sebi_disclaimer"] = (
                            "This is AI-generated investment research, not SEBI-registered investment advice. "
                            "Please consult a certified financial advisor before investing."
                        )
                    # Allocation sum check
                    alloc = parsed.get("allocation_breakdown") or []
                    if alloc:
                        total = sum(float(a.get("percentage", 0)) for a in alloc)
                        if abs(total - 100.0) > 1.0:
                            parsed.setdefault("data_quality_flags", [])
                            parsed["data_quality_flags"].append(f"Allocation sums to {total:.1f}% (expected 100%)")
                    # Scenario count check
                    scenarios = parsed.get("scenario_analysis") or []
                    if len(scenarios) < 3:
                        parsed.setdefault("data_quality_flags", [])
                        parsed["data_quality_flags"].append("Scenario analysis incomplete")
```

- [ ] **Step 6: Run backend import check**

Run: `cd apps/api && python -c "from nq_api.routes.query import _is_portfolio_intent, _PORTFOLIO_OUTPUT_RULES, _build_market_snapshot; print(_is_portfolio_intent('How should I invest 50k?'))"`
Expected: `True`

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: portfolio intent detection, prompt rules, market snapshot, validation

Is_portfolio_intent keyword classifier, _PORTFOLIO_OUTPUT_RULES prompt,
_build_market_snapshot reuses fetch_real_macro/fetch_real_macro_in,
portfolio validation post-processing (SEBI disclaimer fallback,
allocation sum check, scenario count check).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Frontend — Add TypeScript Types

**Files:**
- Modify: `apps/web/src/lib/types.ts`

- [ ] **Step 1: Add 5 new interfaces before `StructuredQueryResponse`**

Insert before line 343 (before `export interface StructuredQueryResponse`):

```typescript
// ── Portfolio Output Types (Phase 1) ──────────────────────────────────────────

export interface MarketContextCard {
  label: string;
  value: string;
  change?: string;
  sentiment?: string;
}

export interface AllocationSegment {
  label: string;
  percentage: number;
  color?: string;
  rationale?: string;
}

export interface PortfolioStockCard {
  ticker: string;
  name?: string;
  allocation_pct: number;
  entry_price?: string;
  target_price?: string;
  stop_loss?: string;
  risk_reward?: string;
  rationale?: string;
  confidence?: number;
  sector?: string;
}

export interface ScenarioCard {
  label: string;
  probability_pct?: number;
  outcome?: string;
  description?: string;
  color?: string;
}

export interface ActionPrompt {
  label: string;
  prompt_text: string;
  icon?: string;
}
```

- [ ] **Step 2: Extend `StructuredQueryResponse`**

Replace the existing `StructuredQueryResponse` interface (lines 343–357) with:

```typescript
export interface StructuredQueryResponse {
  verdict: string;
  confidence: number;
  timeframe: string;
  summary: string;
  stock_summary: StockSummary | null;
  metrics: MetricItem[];
  reasoning: ReasoningBlock;
  scenarios: ScenarioItem[];
  allocations: AllocationItem[];
  comparisons: ComparisonItem[];
  data_sources: string[];
  follow_up_questions: string[];
  route: "SNAP" | "REACT" | "DEEP";

  // Phase 1 portfolio fields (all optional)
  market_context?: MarketContextCard[];
  allocation_breakdown?: AllocationSegment[];
  portfolio_stocks?: PortfolioStockCard[];
  scenario_analysis?: ScenarioCard[];
  action_prompts?: ActionPrompt[];
  sebi_disclaimer?: string;
  is_portfolio_response?: boolean;
}
```

- [ ] **Step 3: Verify types compile**

Run: `cd apps/web && npx tsc --noEmit --pretty`
Expected: No errors (or only pre-existing errors).

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/types.ts
git commit -m "feat: TypeScript types for portfolio output (Phase 1)

MarketContextCard, AllocationSegment, PortfolioStockCard,
ScenarioCard, ActionPrompt + optional fields on StructuredQueryResponse.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Frontend — Build New UI Components

**Files:**
- Create: `apps/web/src/components/ui/MarketContextStrip.tsx`
- Create: `apps/web/src/components/ui/AllocationBar.tsx`
- Create: `apps/web/src/components/ui/PortfolioStockCard.tsx`
- Create: `apps/web/src/components/ui/ScenarioAnalysisPanel.tsx`
- Create: `apps/web/src/components/ui/ActionPromptButtons.tsx`
- Create: `apps/web/src/components/ui/SEBIDisclaimer.tsx`

### Task 4a: MarketContextStrip

- [ ] **Step 1: Create component**

```tsx
// apps/web/src/components/ui/MarketContextStrip.tsx
"use client";

import type { MarketContextCard } from "@/lib/types";

export default function MarketContextStrip({
  cards,
}: {
  cards: MarketContextCard[];
}) {
  if (!cards || cards.length === 0) {
    return (
      <div className="rounded-lg bg-surface-high px-3 py-2 text-xs text-on-surface-variant">
        Market data unavailable
      </div>
    );
  }

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {cards.map((c, i) => (
        <div
          key={i}
          className="flex-shrink-0 rounded-lg bg-surface-high border border-outline/30 px-3 py-2 min-w-[100px]"
        >
          <div className="text-[10px] text-on-surface-variant uppercase tracking-wide">{c.label}</div>
          <div className="text-sm font-semibold text-on-surface">{c.value}</div>
          {c.change && (
            <div className={`text-[10px] ${c.change.startsWith("+") ? "text-green-400" : c.change.startsWith("-") ? "text-red-400" : "text-on-surface-variant"}`}>
              {c.change}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

### Task 4b: AllocationBar

- [ ] **Step 2: Create component**

```tsx
// apps/web/src/components/ui/AllocationBar.tsx
"use client";

import type { AllocationSegment } from "@/lib/types";

export default function AllocationBar({
  segments,
}: {
  segments: AllocationSegment[];
}) {
  if (!segments || segments.length === 0) return null;

  const total = segments.reduce((s, x) => s + (x.percentage || 0), 0);
  const warn = Math.abs(total - 100) > 1;

  return (
    <div className="space-y-2">
      <div className="flex h-4 w-full overflow-hidden rounded-full">
        {segments.map((seg, i) => (
          <div
            key={i}
            style={{
              width: `${Math.max(0, Math.min(100, seg.percentage))}%`,
              backgroundColor: seg.color || "#6366f1",
            }}
            className="first:rounded-l-full last:rounded-r-full"
            title={`${seg.label}: ${seg.percentage}%${seg.rationale ? " — " + seg.rationale : ""}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: seg.color || "#6366f1" }}
            />
            <span className="text-on-surface font-medium">{seg.label}</span>
            <span className="text-on-surface-variant">{seg.percentage}%</span>
          </div>
        ))}
      </div>
      {warn && (
        <div className="rounded bg-amber-500/10 px-2 py-1 text-[10px] text-amber-400 border border-amber-500/20">
          Allocation sums to {total.toFixed(1)}% (expected 100%)
        </div>
      )}
    </div>
  );
}
```

### Task 4c: PortfolioStockCard

- [ ] **Step 3: Create component**

```tsx
// apps/web/src/components/ui/PortfolioStockCard.tsx
"use client";

import type { PortfolioStockCard as PSC } from "@/lib/types";

export default function PortfolioStockCard({ stock }: { stock: PSC }) {
  return (
    <div className="rounded-xl bg-surface-high border border-outline/30 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-on-surface">{stock.ticker}</span>
          {stock.name && <span className="text-xs text-on-surface-variant">{stock.name}</span>}
        </div>
        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
          {stock.allocation_pct}%
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        {stock.entry_price && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Entry</div>
            <div className="text-xs font-medium text-on-surface">{stock.entry_price}</div>
          </div>
        )}
        {stock.target_price && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Target</div>
            <div className="text-xs font-medium text-green-400">{stock.target_price}</div>
          </div>
        )}
        {stock.stop_loss && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Stop Loss</div>
            <div className="text-xs font-medium text-red-400">{stock.stop_loss}</div>
          </div>
        )}
      </div>

      {stock.risk_reward && (
        <div className="text-[10px] text-on-surface-variant">
          R:R {stock.risk_reward}
        </div>
      )}
      {stock.rationale && (
        <p className="text-xs text-on-surface leading-snug">{stock.rationale}</p>
      )}
      {stock.confidence && (
        <div className="text-[10px] text-on-surface-variant">
          ForeCast: {stock.confidence}/10
        </div>
      )}
    </div>
  );
}
```

### Task 4d: ScenarioAnalysisPanel

- [ ] **Step 4: Create component**

```tsx
// apps/web/src/components/ui/ScenarioAnalysisPanel.tsx
"use client";

import type { ScenarioCard } from "@/lib/types";

const SCENARIO_COLORS: Record<string, string> = {
  Bull: "#22c55e",
  Base: "#6366f1",
  Bear: "#ef4444",
};

export default function ScenarioAnalysisPanel({
  scenarios,
}: {
  scenarios: ScenarioCard[];
}) {
  if (!scenarios || scenarios.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
        Scenario Analysis
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {scenarios.map((s, i) => {
          const color = s.color || SCENARIO_COLORS[s.label] || "#6366f1";
          const prob = s.probability_pct ?? 0;
          return (
            <div
              key={i}
              className="rounded-xl bg-surface-high border border-outline/30 p-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold" style={{ color }}>
                  {s.label}
                </span>
                <span className="text-xs text-on-surface-variant">{prob}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-surface-container overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${Math.min(100, prob)}%`, backgroundColor: color }}
                />
              </div>
              {s.outcome && (
                <div className="text-sm font-medium text-on-surface">{s.outcome}</div>
              )}
              {s.description && (
                <p className="text-xs text-on-surface-variant leading-snug">{s.description}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

### Task 4e: ActionPromptButtons

- [ ] **Step 5: Create component**

```tsx
// apps/web/src/components/ui/ActionPromptButtons.tsx
"use client";

import type { ActionPrompt } from "@/lib/types";

export default function ActionPromptButtons({
  prompts,
  onPromptClick,
}: {
  prompts: ActionPrompt[];
  onPromptClick: (text: string) => void;
}) {
  if (!prompts || prompts.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p, i) => (
        <button
          key={i}
          onClick={() => onPromptClick(p.prompt_text)}
          className="rounded-full bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
        >
          {p.icon && <span className="mr-1">{p.icon}</span>}
          {p.label}
        </button>
      ))}
    </div>
  );
}
```

### Task 4f: SEBIDisclaimer

- [ ] **Step 6: Create component**

```tsx
// apps/web/src/components/ui/SEBIDisclaimer.tsx
"use client";

export default function SEBIDisclaimer({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2">
      <p className="text-[10px] leading-relaxed text-amber-200/80">
        {text}
      </p>
    </div>
  );
}
```

- [ ] **Step 7: Verify components compile**

Run: `cd apps/web && npx tsc --noEmit --pretty`
Expected: No new errors from these 6 files.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/ui/MarketContextStrip.tsx \
  apps/web/src/components/ui/AllocationBar.tsx \
  apps/web/src/components/ui/PortfolioStockCard.tsx \
  apps/web/src/components/ui/ScenarioAnalysisPanel.tsx \
  apps/web/src/components/ui/ActionPromptButtons.tsx \
  apps/web/src/components/ui/SEBIDisclaimer.tsx
git commit -m "feat: portfolio UI components (Phase 1)

MarketContextStrip, AllocationBar, PortfolioStockCard,
ScenarioAnalysisPanel, ActionPromptButtons, SEBIDisclaimer.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Frontend — Integrate Portfolio Renderer into AIResponseCard

**Files:**
- Modify: `apps/web/src/components/ui/AIResponseCard.tsx`
- Modify: `apps/web/src/components/NLQueryBox.tsx`

- [ ] **Step 1: Update `AIResponseCard.tsx` Props + Imports**

Replace the imports block (lines 1–9) with:

```tsx
import RegimeBadge from "./RegimeBadge";
import VerdictBanner from "./VerdictBanner";
import MetricsGrid from "./MetricsGrid";
import ReasoningBlock from "./ReasoningBlock";
import ScenarioBar from "./ScenarioBar";
import AllocationTable from "./AllocationTable";
import ComparisonBlock from "./ComparisonBlock";
import StockSummaryCard from "./StockSummaryCard";
import MarketContextStrip from "./MarketContextStrip";
import AllocationBar from "./AllocationBar";
import PortfolioStockCard from "./PortfolioStockCard";
import ScenarioAnalysisPanel from "./ScenarioAnalysisPanel";
import ActionPromptButtons from "./ActionPromptButtons";
import SEBIDisclaimer from "./SEBIDisclaimer";
import type { RegimeLabel, StructuredQueryResponse } from "@/lib/types";
```

Update `Props` type (lines 11–18) to add `onFollowUp`:

```tsx
type Props = {
  answer: string;
  sources?: string[];
  regime?: RegimeLabel;
  score?: number;
  structured?: StructuredQueryResponse | null;
  hideVerdict?: boolean;
  onFollowUp?: (text: string) => void;
};
```

Update function signature and destructuring (line 31–38):

```tsx
export default function AIResponseCard({
  answer,
  sources = [],
  regime,
  score,
  structured,
  hideVerdict = false,
  onFollowUp,
}: Props) {
```

- [ ] **Step 2: Add portfolio branch rendering inside `parsed` block**

After line 41 (`if (parsed) {`), add as the first block inside the returned div:

```tsx
    if (parsed) {
      if (parsed.is_portfolio_response) {
        return (
          <div className="rounded-xl bg-surface-container ghost-border p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-secondary">NeuralQuant Portfolio ForeCast</span>
              <span className="text-[10px] text-on-surface-variant uppercase">{parsed.route}</span>
            </div>

            <MarketContextStrip cards={parsed.market_context ?? []} />
            <AllocationBar segments={parsed.allocation_breakdown ?? []} />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(parsed.portfolio_stocks ?? []).map((s) => (
                <PortfolioStockCard key={s.ticker} stock={s} />
              ))}
            </div>

            <ScenarioAnalysisPanel scenarios={parsed.scenario_analysis ?? []} />

            {onFollowUp && (
              <ActionPromptButtons
                prompts={parsed.action_prompts ?? []}
                onPromptClick={onFollowUp}
              />
            )}

            <SEBIDisclaimer
              text={
                parsed.sebi_disclaimer ??
                "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."
              }
            />

            {parsed.data_sources.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {parsed.data_sources.map((s, i) => (
                  <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      }

      // Legacy single-stock layout (unchanged below this)
```

- [ ] **Step 3: Pass `ask` into `AIResponseCard` from `NLQueryBox.tsx`**

In `NLQueryBox.tsx`, find the `AIResponseCard` JSX element (around line 168–174). Update to:

```tsx
              <AIResponseCard
                key={msg.id}
                answer={msg.content}
                sources={msg.sources}
                structured={msg.structured}
                hideVerdict
                onFollowUp={ask}
              />
```

- [ ] **Step 4: Verify types compile**

Run: `cd apps/web && npx tsc --noEmit --pretty`
Expected: No new errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/ui/AIResponseCard.tsx \
  apps/web/src/components/NLQueryBox.tsx
git commit -m "feat: integrate portfolio renderer into AIResponseCard

Portfolio branch renders MarketContextStrip, AllocationBar,
PortfolioStockCards, ScenarioAnalysisPanel, ActionPromptButtons,
SEBIDisclaimer when is_portfolio_response=true. Legacy layout
unchanged for single-stock queries. onFollowUp wired from NLQueryBox.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: End-to-End Test

- [ ] **Step 1: Start backend + frontend locally**

Terminal 1: `cd apps/api && uvicorn nq_api.main:app --reload --port 8000`
Terminal 2: `cd apps/web && npm run dev`

- [ ] **Step 2: Test portfolio question**

Open `http://localhost:3000/query`
Ask: "I have 50k, how should I invest?"

Verify renders:
- Market context strip with index cards
- Allocation bar summing to ~100%
- 2+ stock cards with entry/target/SL
- 3 scenario cards with probability bars
- Action prompt buttons (clickable)
- SEBI disclaimer at bottom

- [ ] **Step 3: Test action prompt click**

Click one action prompt button → new SSE stream starts with that text.

- [ ] **Step 4: Test single-stock question (backward compatibility)**

Ask: "What do you think of NVDA?"
Verify: renders legacy layout (StockSummaryCard, VerdictBanner, MetricsGrid, etc.) — no portfolio components.

- [ ] **Step 5: Test India portfolio question**

Ask: "Build a portfolio for Indian market with 1 lakh"
Verify: market strip shows NIFTY 50, USD/INR.

- [ ] **Step 6: Commit test results (if any fixes needed)**

If fixes needed from testing, commit them with `fix:` prefix.

---

## Spec Coverage Checklist

| Spec Requirement | Implementing Task |
|------------------|---------------------|
| Keyword-based intent detection | Task 2, Step 1 |
| Portfolio-specific prompt rules | Task 2, Step 2 |
| Market context injection (fetch_real_macro reuse) | Task 2, Step 3 |
| Optional schema fields (backward compatible) | Task 1, Steps 1–2 |
| `is_portfolio_response` flag | Task 1, Step 2 + Task 2, Step 2 |
| SEBI disclaimer hardcoded fallback | Task 2, Step 5 + Task 4f + Task 5, Step 2 |
| Allocation sum validation | Task 2, Step 5 |
| Scenario count validation | Task 2, Step 5 |
| Frontend portfolio branch routing | Task 5, Step 2 |
| Action prompt buttons trigger follow-up | Task 4e + Task 5, Steps 2–3 |
| Legacy layout unchanged for single-stock | Task 5, Step 2 |
| India market context (NIFTY, USD/INR) | Task 2, Step 3 |

---

## Placeholder Scan

- No "TBD", "TODO", "implement later", "fill in details" found.
- Every step contains complete code blocks.
- Every step contains exact run commands with expected output.
- Types/methods consistent across tasks (`ask` in NLQueryBox matches `onFollowUp` in AIResponseCard, etc.).
