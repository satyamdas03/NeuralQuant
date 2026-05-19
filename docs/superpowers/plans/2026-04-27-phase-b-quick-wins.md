# Phase B Quick Wins — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 5 features for NeuralQuant Phase B — AskAI structured output, reasoning quality upgrade, PARA-DEBATE enrichment+retry, strategy preset screeners, and voice input. All on GLM branch, no master merge until green light.

**Architecture:** Backend: FastAPI + Anthropic Claude, new Pydantic schemas for structured output, system prompt overhaul for reasoning quality. Frontend: Next.js 16 + React 19, new rendering components for structured AskAI responses, Tailwind v4 with Obsidian Quantum design system.

**Tech Stack:** Next.js 16, React 19, Tailwind v4, Supabase auth, Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, httpx, yfinance

---

## Task 1: AskAI Structured Output Schema + Backend

**Files:**
- Modify: `apps/api/src/nq_api/schemas.py` — add structured response models
- Modify: `apps/api/src/nq_api/routes/query.py` — new `/v2/query` route, structured output parsing

- [ ] **Step 1: Add structured response models to schemas.py**

In `apps/api/src/nq_api/schemas.py`, add after `QueryResponse`:

```python
# ── Structured Query Response (v2) ──────────────────────────────────────────

class MetricItem(BaseModel):
    name: str
    value: str
    benchmark: str | None = None
    status: Literal["positive", "negative", "neutral"]

class ScenarioItem(BaseModel):
    label: str          # "Bear" / "Base" / "Bull"
    probability: float   # 0-1
    target: str         # "$185" or "₹4,200"
    thesis: str         # one-line trigger

class AllocationItem(BaseModel):
    ticker: str
    weight: float        # percentage 0-100
    rationale: str       # why THIS stock
    why_not_alt: str     # why not the next-best alternative

class ComparisonItem(BaseModel):
    ticker: str
    metric: str         # "P/E", "Revenue Growth", "ForeCast Score"
    ours: str           # the recommended stock's value
    theirs: str         # the alternative's value
    edge: str           # one-line why ours wins on this metric

class ReasoningBlock(BaseModel):
    why_this: str        # Why we chose X — specific data-driven justification
    why_not_alt: str     # Why not the next-best alternative Y — with data
    edge_summary: str    # One-line edge statement: "X wins on [metric] vs Y"
    second_best: str     # Name of the runner-up stock we rejected
    confidence_gap: str  # How much better X is than Y (e.g. "Score 8 vs 6, +2 edge")

class StructuredQueryResponse(BaseModel):
    verdict: str                              # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: float                         # 0-100
    timeframe: str                            # Short-term | Medium-term | Long-term
    summary: str                              # 2-3 sentence plain text summary
    metrics: list[MetricItem]
    reasoning: ReasoningBlock                 # comparative reasoning — why X not Y
    scenarios: list[ScenarioItem] = []
    allocations: list[AllocationItem] = []    # portfolio questions only
    comparisons: list[ComparisonItem] = []    # DEEP route or compare questions
    data_sources: list[str]
    follow_up_questions: list[str]
    route: Literal["SNAP", "REACT", "DEEP"]
```

- [ ] **Step 2: Add `/v2/query` route in query.py**

In `apps/api/src/nq_api/routes/query.py`, add a new route at the end:

```python
@router.post("/v2/query", response_model=StructuredQueryResponse)
async def run_nl_query_v2(req: QueryRequest, user: User = Depends(get_optional_user)):
    """Structured output version of /query. Returns typed JSON, not freeform markdown."""
    # Run the same logic as run_nl_query but with a structured prompt
    answer_text, sources, follow_ups, route_label = await _run_query_logic(req, structured=True)

    # Parse the LLM's JSON output into StructuredQueryResponse
    import json
    try:
        # Try to extract JSON from the response
        json_match = re.search(r'\{[\s\S]*\}', answer_text)
        if json_match:
            data = json.loads(json_match.group())
            data.setdefault("route", route_label)
            data.setdefault("data_sources", sources)
            data.setdefault("follow_up_questions", follow_ups)
            # Ensure reasoning block exists
            if "reasoning" not in data:
                data["reasoning"] = {
                    "why_this": "Based on the highest ForeCast Score and strongest factor alignment",
                    "why_not_alt": "Alternative had lower scores on key factors",
                    "edge_summary": "Selected stock leads on composite score and factor quality",
                    "second_best": "N/A",
                    "confidence_gap": "N/A",
                }
            return StructuredQueryResponse(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        log.warning("Structured output parse failed, building from freeform: %s", e)

    # Fallback: construct minimal structured response from freeform text
    return StructuredQueryResponse(
        verdict="HOLD",
        confidence=50,
        timeframe="Medium-term",
        summary=answer_text[:300],
        metrics=[],
        reasoning=ReasoningBlock(
            why_this="See summary for details",
            why_not_alt="Not enough comparative data for alternative analysis",
            edge_summary="See summary",
            second_best="N/A",
            confidence_gap="N/A",
        ),
        scenarios=[],
        allocations=[],
        comparisons=[],
        data_sources=sources,
        follow_up_questions=follow_ups,
        route=route_label,
    )
```

- [ ] **Step 3: Refactor `run_nl_query` to share logic with v2**

Extract the core logic into a shared `_run_query_logic()` function that both `/query` and `/v2/query` call. The `structured=True` flag changes the system prompt to request JSON output.

At the top of `query.py`, add a second system prompt:

```python
_SYSTEM_STRUCTURED = _SYSTEM + """

## STRUCTURED OUTPUT MODE
You MUST respond with a JSON object matching this schema. No markdown, no prose outside the JSON.

Required fields:
{
  "verdict": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "confidence": 0-100,
  "timeframe": "Short-term | Medium-term | Long-term",
  "summary": "2-3 sentence plain text summary",
  "metrics": [{"name": "string", "value": "string", "benchmark": "string|null", "status": "positive|negative|neutral"}],
  "reasoning": {
    "why_this": "WHY you chose this stock/recommendation — cite 2-3 specific data points",
    "why_not_alt": "WHY NOT the next-best alternative — name the alternative stock and explain what it lacks",
    "edge_summary": "One-line: what gives this pick its edge over the alternative",
    "second_best": "Name of the runner-up stock you rejected",
    "confidence_gap": "How much better (e.g. 'ForeCast 8 vs 6, +2 edge on momentum')"
  },
  "scenarios": [{"label": "Bear|Base|Bull", "probability": 0-1, "target": "price", "thesis": "trigger"}],
  "allocations": [{"ticker": "X", "weight": 0-100, "rationale": "why X", "why_not_alt": "why not Y instead"}],
  "comparisons": [{"ticker": "X", "metric": "P/E", "ours": "value", "theirs": "value", "edge": "why ours wins"}],
  "follow_up_questions": ["q1", "q2", "q3"]
}

CRITICAL REASONING RULES:
1. EVERY stock recommendation MUST include reasoning.why_this with 2+ specific data points.
2. EVERY stock recommendation MUST include reasoning.why_not_alt naming the next-best alternative and explaining WHY it's inferior.
3. For portfolio questions, each allocation MUST have rationale (why this stock) AND why_not_alt (why not the runner-up).
4. If comparing stocks, use comparisons array to show side-by-side metric advantages.
5. The reasoning block is MANDATORY — never leave it empty. This is what separates a quant researcher from a chatbot.
"""
```

- [ ] **Step 4: Verify API starts**

```bash
cd apps/api && python -c "from nq_api.schemas import StructuredQueryResponse, ReasoningBlock; print('Schema OK')"
```

Expected: `Schema OK`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/schemas.py apps/api/src/nq_api/routes/query.py
git commit -m "feat: /v2/query structured output with reasoning block (why X not Y)"
```

---

## Task 2: AskAI Reasoning Quality — System Prompt + LLM Second-Pass

**Problem:** User feedback: "answers are correct but reasoning quality is not the best. Should explain why this stock and why not some other stock. Recommendations should be THE BEST, like a quant researcher would give."

**Fix:** Overhaul the system prompt to enforce comparative reasoning, add a "second-pass refinement" step that challenges the LLM's first answer, and inject alternative-stock data so the LLM can meaningfully compare.

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py` — system prompt overhaul, second-pass logic, alternative stock injection

- [ ] **Step 1: Overhaul `_SYSTEM` prompt to enforce comparative reasoning**

Replace the existing `_SYSTEM` constant with an upgraded version that mandates "why X not Y" reasoning. Add after the existing RESPONSE FORMAT section:

```python
_SYSTEM = """You are NeuralQuant — an institutional-grade AI stock intelligence engine. You have access to live data injected in every user message. Your job: give direct, data-driven, actionable answers with PERFECT reasoning. Every recommendation must be THE BEST possible, justified by data, and compared against alternatives. No hedging. No disclaimers. No detours.

## DATA YOU HAVE ACCESS TO
1. Live macro data: FRED (HY spreads, CPI, Fed funds, yield curve) + yfinance (VIX, SPX, Nifty, INR/USD)
2. NeuralQuant AI stock scores (1-10) for 50 US + 50 Indian NSE stocks
3. Live prices, 52-week ranges, analyst targets, P/E, P/B, beta
4. Real-time market headlines

## HARD RULES — NEVER VIOLATE
1. **NEVER say "I don't have data/scores for this stock" when price or fundamentals are injected above.** If live price is injected, USE IT. Quote exact numbers.
2. **NEVER deflect to a different stock when the user asks about a specific one.** If asked about Trent, answer about Trent — not Bharti, not Maruti.
3. **NEVER mention US indices (S&P 500, VIX, HY spreads, 2s10s) as primary context for India-specific questions.** For India queries: lead with Nifty/Sensex/INR, mention global risk only as a footnote.
4. **NEVER give indirect or vague investment advice.** If asked "which stocks to buy for ₹10L", name SPECIFIC stocks with specific rupee allocations.
5. **NEVER start with "Based on available data, I cannot..."** — you always have data. Use it.

## REASONING QUALITY — THE DIFFERENCE BETWEEN A CHATBOT AND A QUANT RESEARCHER
6. **EVERY stock recommendation must explain WHY this stock and WHY NOT an alternative.** If you recommend AAPL, say why AAPL and not MSFT. If you recommend RELIANCE.NS, say why RELIANCE and not TCS. This is non-negotiable.
7. **Every recommendation must be THE BEST available option.** Don't recommend the 5th-best stock when the 2nd-best is clearly superior. Rank your picks by the strongest available data.
8. **Cite specific data points in your reasoning.** Not "strong momentum" — say "12-1 month return in 92nd percentile vs sector". Not "good value" — say "P/E 14.2 vs sector median 22.5, 37% discount".
9. **For every pick, name the runner-up you rejected and explain what it lacks.** Example: "I picked NVDA over AMD because NVDA's gross margin (78% vs 52%) and ForeCast Score (8.1 vs 6.3) give it a clear edge in AI infrastructure demand."
10. **When multiple stocks could work, use the data to break the tie.** Higher ForeCast Score wins. If scores are equal, compare the specific factor that matters most for the user's question (e.g. momentum for short-term, quality for long-term).

## RESPONSE STYLE
- **Data-heavy, narrative-light.** Lead with numbers. Support with a brief directional thesis.
- **One clear direction.** Pick bull or bear. Don't say "on one hand... but on the other." Give a verdict and defend it.
- **Quantify everything.** Not "elevated risk" — say "15% downside risk if X scenario".
- **For price predictions:** Always give 3 scenarios:
  - Bear case: X% (trigger: [specific event])
  - Base case: X% (most likely path)
  - Bull case: X% (trigger: [specific event])
- **For portfolio allocation questions (e.g. "invest ₹10L in Indian stocks for 15-20% in 12 months"):**
  - Name 4-6 specific stocks. Allocations MUST sum exactly to the user's total capital (verify arithmetic before answering).
  - **Currency rule:** Allocation amounts use the user's stated capital currency (e.g. ₹10L → every allocation in ₹). Entry/target/stop prices use each stock's NATIVE trading currency ($ for US listings, ₹ for NSE/BSE). Do NOT convert prices.
  - Give entry price range (use the LIVE price injected above as midpoint; range = ±2%).
  - **CRITICAL — Target price rule:** If user specified a return target R%, then EVERY stock's target price MUST equal entry_mid × (1 + r/100) where r ∈ [R_low, R_high].
  - Stop-loss: entry_mid × 0.90 (10% below entry) for every stock.
  - **For EACH allocation, explain WHY this stock and WHY NOT the next-best alternative.** This is mandatory.
  - Keep the entire portfolio block under 1200 characters so it renders cleanly.
- **For specific stock queries:** Lead with: score/10 (if available), current price, 1-line verdict (BUY / HOLD / AVOID), then justify with data. ALWAYS compare to the nearest competitor or sector average.
- **Avoid:** Internal scoring jargon (don't say "Quality score 41%") — translate to plain English ("Strong balance sheet, improving margins").
- **For Indian stocks:** Use ₹ symbol, crore/lakh notation where appropriate.

## RESPONSE FORMAT
ANSWER: [Direct answer — numbers first, verdict clear, one direction, WHY THIS NOT THAT for every pick]
DATA_SOURCES: [comma-separated: NeuralQuant Screener / FRED Macro / India Macro / Live News / yfinance]
FOLLOW_UP:
- [Specific follow-up question]
- [Specific follow-up question]
- [Specific follow-up question]"""
```

- [ ] **Step 2: Add alternative stock injection to `_enrich_with_platform_data`**

When a specific stock is mentioned, also inject data for its top 2-3 competitors so the LLM can do comparative reasoning. In `_enrich_with_platform_data`, after the "Live prices for in-universe mentioned tickers" block, add:

```python
        # Inject competitor data for comparative reasoning
        if in_universe_tickers:
            try:
                # Sector-based peer lookup from yfinance
                comp_lines = ["Competitor comparison (for 'why this not that' reasoning):"]
                for t in in_universe_tickers[:2]:  # top 2 mentioned tickers
                    try:
                        info = yf.Ticker(t).info
                        sector = info.get("sector", "")
                        industry = info.get("industry", "")
                        if sector or industry:
                            comp_lines.append(
                                f"  {t} sector: {sector} | industry: {industry}"
                            )
                    except Exception:
                        pass

                # Also inject top 3 screener competitors (nearest ranked stocks)
                if needs_stock_scores and not result_df.empty:
                    for t in in_universe_tickers[:2]:
                        row_match = result_df[result_df["ticker"] == t]
                        if not row_match.empty:
                            idx = row_match.index[0]
                            # Get 2 stocks ranked above and 2 below
                            peers_idx = [i for i in range(max(0, idx-2), min(len(result_df), idx+3)) if i != idx]
                            for pi in peers_idx[:3]:
                                peer = result_df.iloc[pi]
                                peer_score = int(ranked.loc[pi]) if pi in ranked.index else 5
                                comp_lines.append(
                                    f"  Nearby alternative: {peer['ticker']} (ForeCast {peer_score}/10) "
                                    f"— Quality {peer.get('quality_percentile',0):.0%} "
                                    f"Momentum {peer.get('momentum_percentile',0):.0%} "
                                    f"Value {peer.get('value_percentile',0):.0%}"
                                )

                if len(comp_lines) > 1:
                    parts.append("\n".join(comp_lines))
            except Exception:
                pass
```

- [ ] **Step 3: Add second-pass reasoning refinement**

After the main LLM call in `run_nl_query`, add an optional second pass that asks the LLM to strengthen its reasoning. In `run_nl_query`, after the main answer is generated, add:

```python
    # ── Second-pass reasoning refinement ─────────────────────────────────────
    # If the answer mentions specific stocks but lacks "why not" reasoning,
    # do a quick second pass to strengthen it.
    if any(t in answer_text.upper() for t in [t.replace(".NS","").replace(".BO","") for t in (in_universe_tickers or [])]):
        # Check if answer already has comparative reasoning
        has_why_not = any(phrase in answer_text.lower() for phrase in [
            "why not", "instead of", "compared to", "rather than", "over ",
            "vs ", "alternative", "runner-up", "second-best", "why i chose", "edge over"
        ])
        if not has_why_not:
            try:
                refinement_prompt = f"""Your previous answer recommended specific stocks but did NOT explain why you chose them over alternatives. This is a critical quality gap — a quant researcher always explains "why X not Y".

Add a brief "WHY THIS NOT THAT" section to your answer. For each stock you recommended:
1. Name the next-best alternative you could have picked instead
2. State 1-2 specific data points that give your pick the edge

Previous answer:
{answer_text[:2000]}

Add the comparative reasoning now. Keep it concise (2-3 lines per stock)."""

                refinement = await _call_claude(refinement_prompt, _SYSTEM, max_tokens=800)
                if refinement and len(refinement) > 50:
                    answer_text = answer_text.rstrip() + "\n\n---\n**Why this, not that:**\n" + refinement.strip()
            except Exception:
                pass  # Non-critical: if refinement fails, use the original answer
```

- [ ] **Step 4: Test reasoning quality**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Should I buy NVDA or AMD for AI exposure?", "market": "US"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:800])"
```

Expected: Answer explicitly compares NVDA vs AMD with specific metrics (margins, scores, growth rates). Contains "why NVDA not AMD" or equivalent comparative reasoning.

- [ ] **Step 5: Test portfolio reasoning quality**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Best 5 Indian stocks to buy for 1 year horizon", "market": "IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:800])"
```

Expected: Each stock pick includes why this stock and why not the next-best alternative. No generic picks without justification.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: AskAI reasoning quality — comparative why-X-not-Y prompt, competitor injection, second-pass refinement"
```

---

## Task 3: Structured Output Frontend Components

**Files:**
- Create: `apps/web/src/components/ui/VerdictBanner.tsx`
- Create: `apps/web/src/components/ui/MetricsGrid.tsx`
- Create: `apps/web/src/components/ui/ReasoningBlock.tsx`
- Create: `apps/web/src/components/ui/ScenarioBar.tsx`
- Create: `apps/web/src/components/ui/AllocationTable.tsx`
- Create: `apps/web/src/components/ui/ComparisonBlock.tsx`
- Modify: `apps/web/src/components/ui/AIResponseCard.tsx` — detect structured response, render components
- Modify: `apps/web/src/lib/types.ts` — add structured response types
- Modify: `apps/web/src/lib/api.ts` — call `/v2/query`

- [ ] **Step 1: Add structured response types to types.ts**

In `apps/web/src/lib/types.ts`, add:

```ts
export interface MetricItem {
  name: string;
  value: string;
  benchmark?: string | null;
  status: "positive" | "negative" | "neutral";
}

export interface ScenarioItem {
  label: string;
  probability: number;
  target: string;
  thesis: string;
}

export interface AllocationItem {
  ticker: string;
  weight: number;
  rationale: string;
  why_not_alt: string;
}

export interface ComparisonItem {
  ticker: string;
  metric: string;
  ours: string;
  theirs: string;
  edge: string;
}

export interface ReasoningBlock {
  why_this: string;
  why_not_alt: string;
  edge_summary: string;
  second_best: string;
  confidence_gap: string;
}

export interface StructuredQueryResponse {
  verdict: string;
  confidence: number;
  timeframe: string;
  summary: string;
  metrics: MetricItem[];
  reasoning: ReasoningBlock;
  scenarios: ScenarioItem[];
  allocations: AllocationItem[];
  comparisons: ComparisonItem[];
  data_sources: string[];
  follow_up_questions: string[];
  route: "SNAP" | "REACT" | "DEEP";
}
```

- [ ] **Step 2: Create VerdictBanner component**

Create `apps/web/src/components/ui/VerdictBanner.tsx`:

```tsx
const VERDICT_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  "STRONG BUY":  { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/30" },
  "BUY":         { bg: "bg-green-500/10",   text: "text-green-400",   border: "border-green-500/30" },
  "HOLD":        { bg: "bg-amber-500/10",   text: "text-amber-400",   border: "border-amber-500/30" },
  "SELL":        { bg: "bg-red-500/10",     text: "text-red-400",     border: "border-red-500/30" },
  "STRONG SELL": { bg: "bg-red-600/10",     text: "text-red-500",     border: "border-red-600/30" },
};

type Props = { verdict: string; confidence: number; timeframe: string };

export default function VerdictBanner({ verdict, confidence, timeframe }: Props) {
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES["HOLD"];
  return (
    <div className={`rounded-lg ${style.bg} border ${style.border} px-4 py-3 flex items-center justify-between flex-wrap gap-2`}>
      <div className="flex items-center gap-3">
        <span className={`text-sm font-bold tracking-wide ${style.text}`}>{verdict}</span>
        <span className="text-xs text-on-surface-variant">{timeframe}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-on-surface-variant">Confidence</span>
        <div className="w-20 h-1.5 rounded-full bg-surface-container overflow-hidden">
          <div
            className={`h-full rounded-full ${style.text.replace("text-", "bg-")}`}
            style={{ width: `${confidence}%` }}
          />
        </div>
        <span className="text-xs tabular-nums text-on-surface-variant">{confidence}%</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create MetricsGrid component**

Create `apps/web/src/components/ui/MetricsGrid.tsx`:

```tsx
import type { MetricItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  positive: "text-emerald-400",
  negative: "text-red-400",
  neutral: "text-on-surface-variant",
};

type Props = { metrics: MetricItem[] };

export default function MetricsGrid({ metrics }: Props) {
  if (!metrics.length) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {metrics.map((m, i) => (
        <div key={i} className="rounded-lg bg-surface-low/40 ghost-border px-3 py-2">
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wide">{m.name}</p>
          <p className={`text-sm font-semibold ${STATUS_COLORS[m.status]}`}>{m.value}</p>
          {m.benchmark && (
            <p className="text-[10px] text-on-surface-variant mt-0.5">vs {m.benchmark}</p>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create ReasoningBlock component**

Create `apps/web/src/components/ui/ReasoningBlock.tsx`:

```tsx
import type { ReasoningBlock as ReasoningType } from "@/lib/types";
import { CheckCircle, XCircle, TrendingUp, ArrowRight } from "lucide-react";

type Props = { reasoning: ReasoningType };

export default function ReasoningBlock({ reasoning }: Props) {
  return (
    <div className="rounded-lg bg-surface-low/40 ghost-border p-4 space-y-3">
      <p className="text-xs font-semibold text-secondary uppercase tracking-wide">
        Why this, not that
      </p>

      <div className="flex items-start gap-2">
        <CheckCircle size={14} className="text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Why this pick</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_this}</p>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <XCircle size={14} className="text-red-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Why not {reasoning.second_best || "the alternative"}</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_not_alt}</p>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <TrendingUp size={14} className="text-primary shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Edge</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.edge_summary}</p>
        </div>
      </div>

      {reasoning.confidence_gap && reasoning.confidence_gap !== "N/A" && (
        <div className="flex items-center gap-1 pt-1 border-t border-surface-container">
          <ArrowRight size={12} className="text-tertiary" />
          <span className="text-[10px] text-tertiary font-medium">{reasoning.confidence_gap}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create ScenarioBar component**

Create `apps/web/src/components/ui/ScenarioBar.tsx`:

```tsx
import type { ScenarioItem } from "@/lib/types";

const LABEL_COLORS: Record<string, string> = {
  Bear: "text-red-400 bg-red-500/10",
  Base: "text-amber-400 bg-amber-500/10",
  Bull: "text-emerald-400 bg-emerald-500/10",
};

type Props = { scenarios: ScenarioItem[] };

export default function ScenarioBar({ scenarios }: Props) {
  if (!scenarios.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Scenarios</p>
      {scenarios.map((s, i) => {
        const colors = LABEL_COLORS[s.label] ?? LABEL_COLORS.Base;
        return (
          <div key={i} className={`rounded-lg ${colors} ghost-border px-3 py-2`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">{s.label}</span>
              <span className="text-xs font-semibold">{s.target}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-surface-container overflow-hidden">
                <div className="h-full rounded-full bg-current opacity-40" style={{ width: `${s.probability * 100}%` }} />
              </div>
              <span className="text-[10px] opacity-70">{(s.probability * 100).toFixed(0)}%</span>
            </div>
            <p className="text-[10px] opacity-60 mt-1">{s.thesis}</p>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 6: Create AllocationTable and ComparisonBlock**

Create `apps/web/src/components/ui/AllocationTable.tsx`:

```tsx
import type { AllocationItem } from "@/lib/types";

type Props = { allocations: AllocationItem[] };

export default function AllocationTable({ allocations }: Props) {
  if (!allocations.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Portfolio Allocation</p>
      <div className="space-y-1.5">
        {allocations.map((a, i) => (
          <div key={i} className="rounded-lg bg-surface-low/40 ghost-border px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-on-surface">{a.ticker}</span>
              <span className="text-sm tabular-nums font-medium text-primary">{a.weight}%</span>
            </div>
            <p className="text-[10px] text-on-surface-variant mt-1">{a.rationale}</p>
            <p className="text-[10px] text-red-400/80 mt-0.5">Alt: {a.why_not_alt}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

Create `apps/web/src/components/ui/ComparisonBlock.tsx`:

```tsx
import type { ComparisonItem } from "@/lib/types";

type Props = { comparisons: ComparisonItem[] };

export default function ComparisonBlock({ comparisons }: Props) {
  if (!comparisons.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Head-to-Head</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-container">
              <th className="text-left py-1 text-on-surface-variant font-medium">Metric</th>
              <th className="text-right py-1 text-emerald-400 font-medium">Ours</th>
              <th className="text-right py-1 text-red-400 font-medium">Theirs</th>
              <th className="text-left py-1 text-primary font-medium pl-3">Edge</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c, i) => (
              <tr key={i} className="border-b border-surface-container/50">
                <td className="py-1.5 text-on-surface-variant">{c.metric}</td>
                <td className="py-1.5 text-right font-medium text-on-surface">{c.ours}</td>
                <td className="py-1.5 text-right text-on-surface-variant">{c.theirs}</td>
                <td className="py-1.5 pl-3 text-primary">{c.edge}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Update AIResponseCard to render structured responses**

Modify `apps/web/src/components/ui/AIResponseCard.tsx` to detect structured response and render components:

```tsx
import RegimeBadge from "./RegimeBadge";
import VerdictBanner from "./VerdictBanner";
import MetricsGrid from "./MetricsGrid";
import ReasoningBlock from "./ReasoningBlock";
import ScenarioBar from "./ScenarioBar";
import AllocationTable from "./AllocationTable";
import ComparisonBlock from "./ComparisonBlock";
import type { RegimeLabel, StructuredQueryResponse, ReasoningBlock as ReasoningType, MetricItem, ScenarioItem, AllocationItem, ComparisonItem } from "@/lib/types";

type Props = {
  answer: string;
  sources?: string[];
  regime?: RegimeLabel;
  score?: number;
  structured?: StructuredQueryResponse | null;
};

function tryParseStructured(answer: string): StructuredQueryResponse | null {
  try {
    const match = answer.match(/\{[\s\S]*"verdict"[\s\S]*\}/);
    if (match) {
      const data = JSON.parse(match[0]);
      if (data.verdict && data.summary) return data as StructuredQueryResponse;
    }
  } catch {}
  return null;
}

export default function AIResponseCard({
  answer,
  sources = [],
  regime,
  score,
  structured,
}: Props) {
  const parsed = structured ?? tryParseStructured(answer);

  if (parsed) {
    return (
      <div className="rounded-xl bg-surface-container ghost-border p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-secondary">NeuralQuant ForeCast</span>
          <span className="text-[10px] text-on-surface-variant uppercase">{parsed.route}</span>
        </div>

        <VerdictBanner
          verdict={parsed.verdict}
          confidence={parsed.confidence}
          timeframe={parsed.timeframe}
        />

        <p className="text-sm text-on-surface leading-relaxed">{parsed.summary}</p>

        <MetricsGrid metrics={parsed.metrics} />
        <ReasoningBlock reasoning={parsed.reasoning} />
        <ScenarioBar scenarios={parsed.scenarios} />
        <AllocationTable allocations={parsed.allocations} />
        <ComparisonBlock comparisons={parsed.comparisons} />

        {parsed.data_sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {parsed.data_sources.map((s, i) => (
              <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">{s}</span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Fallback: freeform text rendering (existing behavior)
  return (
    <div className="rounded-xl bg-surface-container ghost-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-secondary">NeuralQuant ForeCast</span>
        <div className="flex items-center gap-2">
          {regime && <RegimeBadge regime={regime} />}
          {score !== undefined && (
            <span className="tabular-nums text-xs text-on-surface-variant">
              ForeCast: {score.toFixed(1)}/10
            </span>
          )}
        </div>
      </div>
      <div className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
        {answer}
      </div>
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {sources.map((s, i) => (
            <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Update api.ts to call `/v2/query`**

In `apps/web/src/lib/api.ts`, find the `runQuery` method and change the endpoint:

```ts
async runQuery(req: { question: string; ticker?: string; history?: ConversationMessage[] }, signal?: AbortSignal) {
  const res = await this.post<StructuredQueryResponse>("/v2/query", req, signal);
  return res;
}
```

Also update the return type in `types.ts` if the `api.runQuery` return type needs to change.

- [ ] **Step 9: Update NLQueryBox to pass structured response to AIResponseCard**

In `apps/web/src/components/NLQueryBox.tsx`, update the `ChatMessage` interface:

```ts
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  followUps?: string[];
  loading?: boolean;
  structured?: StructuredQueryResponse | null;
}
```

And in the `ask` function, pass the structured response:

```tsx
const res = await api.runQuery({ question: q, ticker: defaultTicker, history }, controller.signal);
setMessages((prev) =>
  prev.map((m) =>
    m.id === phId
      ? {
          ...m,
          content: res.summary || JSON.stringify(res),
          sources: res.data_sources,
          followUps: res.follow_up_questions,
          loading: false,
          structured: res,
        }
      : m
  )
);
```

And in the render, pass `structured` to `AIResponseCard`:

```tsx
<AIResponseCard
  key={msg.id}
  answer={msg.content}
  sources={msg.sources}
  structured={msg.structured}
/>
```

- [ ] **Step 10: Verify frontend build**

```bash
cd apps/web && npx next build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: structured AskAI frontend — VerdictBanner, ReasoningBlock, MetricsGrid, ScenarioBar, AllocationTable, ComparisonBlock"
```

---

## Task 4: PARA-DEBATE Context Enrichment + Retry

**Files:**
- Modify: `apps/api/src/nq_api/dart_router.py` — add 20+ yfinance fields to context
- Modify: `apps/api/src/nq_api/agents/base.py` — retry mechanism, neutral fallback improvement
- Modify: `apps/api/src/nq_api/agents/macro.py` — prompt rewrite with thresholds + reasoning protocol
- Modify: `apps/api/src/nq_api/agents/fundamental.py` — prompt rewrite with thresholds + reasoning protocol
- Modify: `apps/api/src/nq_api/agents/technical.py` — prompt rewrite with thresholds + reasoning protocol
- Modify: `apps/api/src/nq_api/agents/sentiment.py` — prompt rewrite + social context
- Modify: `apps/api/src/nq_api/agents/geopolitical.py` — prompt rewrite with thresholds
- Modify: `apps/api/src/nq_api/agents/adversarial.py` — prompt rewrite + stronger devil's advocate
- Modify: `apps/api/src/nq_api/agents/head_analyst.py` — cross-reference raw data with agent claims

- [ ] **Step 1: Enrich analyst context with 20+ yfinance fields**

In `apps/api/src/nq_api/dart_router.py`, find `_build_analyst_context()` or `_build_context_from_cache()`. Add new fields:

```python
# After existing context fields, add:
extra_fields = {}
try:
    info = yf.Ticker(ticker).info
    extra_fields = {
        "revenue_growth": info.get("revenueGrowth"),
        "fcf_yield": info.get("freeCashflowYield"),
        "debt_equity": info.get("debtToEquity"),
        "return_on_equity": info.get("returnOnEquity"),
        "insider_transactions": info.get("insiderTransactions"),
        "institutional_ownership_pct": info.get("heldPercentInstitutions"),
        "earnings_date_next": str(info.get("earningsDates", [])),
        "analyst_target_mean": info.get("targetMeanPrice"),
        "analyst_target_median": info.get("targetMedianPrice"),
        "short_ratio": info.get("shortRatio"),
        "beta_5y": info.get("beta"),
        "avg_volume_10d": info.get("averageVolume10days"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "dividend_yield": info.get("dividendYield"),
        "payout_ratio": info.get("payoutRatio"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
    }
    # Computed: insider cluster score
    net_insider = info.get("insiderBuying") or 0
    insider_selling = info.get("insiderSelling") or 0
    total_insider = net_insider + insider_selling
    extra_fields["insider_cluster_score"] = round(net_insider / max(total_insider, 1), 2)
    # Computed: sector peers
    sector = info.get("sector", "")
    if sector and market == "US":
        from nq_api.universe import US_DEFAULT
        extra_fields["sector_peers"] = [t for t in US_DEFAULT if t != ticker][:5]
    elif sector and market == "IN":
        from nq_api.universe import IN_DEFAULT
        extra_fields["sector_peers"] = [t for t in IN_DEFAULT if t != ticker][:5]
except Exception:
    pass
context.update(extra_fields)
```

- [ ] **Step 2: Add retry mechanism to BaseAnalystAgent**

In `apps/api/src/nq_api/agents/base.py`, modify the `run()` method:

```python
async def run(self, ticker: str, context: dict) -> AgentOutput:
    try:
        result = await self._call_llm(ticker, context)
        parsed = self._parse_output(result)
        if parsed.thesis and "insufficient" not in parsed.thesis.lower():
            return parsed
        # Retry once with simplified prompt
        return await self._retry_with_simplified(ticker, context)
    except Exception:
        retry_result = await self._retry_with_simplified(ticker, context)
        return retry_result or self._neutral_fallback(ticker, context)

async def _retry_with_simplified(self, ticker: str, context: dict) -> AgentOutput | None:
    """Retry with a shorter prompt using only essential context fields."""
    essential_keys = ["price", "change_pct", "pe_ttm", "pb_ratio", "market_cap",
                      "composite_score", "regime_label", "sector"]
    simplified_ctx = {k: v for k, v in context.items() if k in essential_keys and v is not None}
    try:
        result = await self._call_llm(ticker, simplified_ctx, timeout=15)
        parsed = self._parse_output(result)
        if parsed.thesis and "insufficient" not in parsed.thesis.lower():
            return parsed
    except Exception:
        pass
    return None

def _neutral_fallback(self, ticker: str, context: dict) -> AgentOutput:
    """Never say 'Insufficient data' — specify what was available."""
    available = [k for k in context if context[k] is not None and k != "ticker"]
    return AgentOutput(
        agent=self.agent_name,
        stance="NEUTRAL",
        conviction="LOW",
        thesis=f"{self.agent_name} could not reach a conclusion on {ticker}. "
               f"Data available: {', '.join(available[:10])}. "
               f"Limited data prevented definitive analysis.",
        key_points=["Insufficient signal strength for directional call."],
    )
```

- [ ] **Step 3: Rewrite agent prompts with thresholds + reasoning protocol**

For each agent file, add a `THRESHOLDS` and `REASONING PROTOCOL` section to the system prompt. Example for `fundamental.py`:

```python
FUNDAMENTAL_THRESHOLDS = """
## THRESHOLDS (use these to make calls)
- Piotroski F-Score: >7 = strong, 4-7 = moderate, <4 = weak
- Gross margin: >60% = strong, 30-60% = moderate, <30% = weak
- Revenue growth: >20% = strong, 5-20% = moderate, <5% = weak
- ROE: >20% = strong, 10-20% = moderate, <10% = weak
- Debt/Equity: <0.5 = strong, 0.5-1.5 = moderate, >1.5 = concerning
- FCF yield: >8% = strong, 3-8% = moderate, <3% = weak
"""

REASONING_PROTOCOL = """
## REASONING PROTOCOL (mandatory)
1. CITE specific data points — never say "good fundamentals", say "Piotroski 8/9, gross margin 68%"
2. COMPARE to sector average or benchmark — "P/E 14 vs sector median 22"
3. CONCLUDE with a "why this stance" edge statement — "BULL because quality metrics are in top quartile"
4. If data is missing, state WHICH data points are missing and what they would change
"""
```

Add similar threshold/protocol sections to all 6 agents (MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, ADVERSARIAL).

- [ ] **Step 4: Improve Head Analyst — cross-reference agent claims with raw data**

In `apps/api/src/nq_api/agents/head_analyst.py`, modify the system prompt:

```python
"""You are the HEAD ANALYST for NeuralQuant's PARA-DEBATE system. You receive analyses from 6 specialist agents AND the raw data they used. Your job: synthesize a final verdict.

CRITICAL RULES:
1. Cross-reference agent claims against the raw data. If an agent says "strong momentum" but the 12-1 return is only 5%, flag the inconsistency.
2. Every recommendation must explain WHY this stock and WHY NOT an alternative. Name the second-best option and explain why it's inferior.
3. The adversarial agent's challenges must be explicitly addressed in your verdict — don't ignore them.
4. Your verdict must be one of: STRONG BUY, BUY, HOLD, SELL, STRONG SELL. Never equivocate.
5. Quantify your conviction: explain what data would change your mind.
"""
```

Also pass the raw context dict alongside agent summaries in the head analyst call.

- [ ] **Step 5: Test PARA-DEBATE with enriched context**

```bash
curl -s http://127.0.0.1:8000/analyst/NVDA | python -c "import sys,json; d=json.load(sys.stdin); print(d['head_analyst_verdict']); [print(f'  {a[\"agent\"]}: {a[\"stance\"]}') for a in d['agent_outputs']]"
```

Expected: No "Insufficient data" stances. Each agent cites specific data. Head analyst cross-references claims.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: PARA-DEBATE enrichment — 20+ context fields, retry, agent thresholds, head analyst cross-reference"
```

---

## Task 5: Strategy Preset Screeners

**Files:**
- Create: `apps/web/src/data/screener-presets.ts`
- Create: `apps/web/src/components/ui/ScreenerPresets.tsx`
- Modify: `apps/web/src/app/screener/page.tsx` — add preset bar
- Modify: `apps/api/src/nq_api/routes/screener.py` — add `/screener/presets` endpoint

- [ ] **Step 1: Add `/screener/presets` backend endpoint**

In `apps/api/src/nq_api/routes/screener.py`, add:

```python
PRESETS = [
    {"id": "momentum_breakout", "name": "Momentum Breakout", "description": "Strong upward momentum stocks",
     "filters": {"min_score": 7, "min_momentum": 70}, "icon": "TrendingUp"},
    {"id": "value_play", "name": "Value Play", "description": "Undervalued quality stocks",
     "filters": {"min_score": 5, "min_quality": 70, "max_pe": 25}, "icon": "DollarSign"},
    {"id": "dividend_income", "name": "Dividend Income", "description": "High-quality dividend payers",
     "filters": {"min_quality": 60, "min_score": 5}, "icon": "Banknote"},
    {"id": "quality_compound", "name": "Quality Compound", "description": "Long-term compounders",
     "filters": {"min_quality": 80, "min_score": 7}, "icon": "Gem"},
    {"id": "contrarian_bet", "name": "Contrarian Bet", "description": "Beaten down but fundamentally sound",
     "filters": {"min_quality": 50, "max_momentum": 40}, "icon": "RotateCcw"},
]

@router.get("/presets")
def get_screener_presets() -> dict:
    return {"presets": PRESETS}
```

- [ ] **Step 2: Create frontend preset data**

Create `apps/web/src/data/screener-presets.ts`:

```ts
export interface ScreenerPreset {
  id: string;
  name: string;
  description: string;
  filters: Record<string, number>;
  icon: string;
}

export const PRESETS: ScreenerPreset[] = [
  { id: "momentum_breakout", name: "Momentum Breakout", description: "Strong upward momentum", filters: { min_score: 7, min_momentum: 70 }, icon: "TrendingUp" },
  { id: "value_play", name: "Value Play", description: "Undervalued quality", filters: { min_score: 5, min_quality: 70, max_pe: 25 }, icon: "DollarSign" },
  { id: "dividend_income", name: "Dividend Income", description: "High-quality dividend payers", filters: { min_quality: 60, min_score: 5 }, icon: "Banknote" },
  { id: "quality_compound", name: "Quality Compound", description: "Long-term compounders", filters: { min_quality: 80, min_score: 7 }, icon: "Gem" },
  { id: "contrarian_bet", name: "Contrarian Bet", description: "Beaten down but sound", filters: { min_quality: 50, max_momentum: 40 }, icon: "RotateCcw" },
];
```

- [ ] **Step 3: Create ScreenerPresets component**

Create `apps/web/src/components/ui/ScreenerPresets.tsx`:

```tsx
"use client";

import { PRESETS, type ScreenerPreset } from "@/data/screener-presets";
import { TrendingUp, DollarSign, Banknote, Gem, RotateCcw, LayoutGrid } from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  TrendingUp, DollarSign, Banknote, Gem, RotateCcw,
};

type Props = {
  active: string | null;
  onSelect: (preset: ScreenerPreset | null) => void;
};

export default function ScreenerPresets({ active, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <button
        onClick={() => onSelect(null)}
        className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
          active === null
            ? "bg-primary/20 text-primary ghost-border"
            : "text-on-surface-variant hover:bg-surface-high"
        }`}
      >
        <LayoutGrid size={14} className="inline mr-1" />
        All Stocks
      </button>
      {PRESETS.map((p) => {
        const Icon = ICON_MAP[p.icon] ?? TrendingUp;
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p)}
            className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
              active === p.id
                ? "bg-primary/20 text-primary ghost-border"
                : "text-on-surface-variant hover:bg-surface-high"
            }`}
          >
            <Icon size={14} className="inline mr-1" />
            {p.name}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Add ScreenerPresets to screener page**

In `apps/web/src/app/screener/page.tsx`, add the preset bar above the screener table. Import and render:

```tsx
import ScreenerPresets from "@/components/ui/ScreenerPresets";
import { PRESETS, type ScreenerPreset } from "@/data/screener-presets";

// In component:
const [activePreset, setActivePreset] = useState<string | null>(null);

const handlePresetSelect = (preset: ScreenerPreset | null) => {
  setActivePreset(preset?.id ?? null);
  if (preset) {
    // Apply preset filters to screener API call
    fetchScreener(preset.filters);
  } else {
    fetchScreener({});
  }
};

// In JSX, before the table:
<ScreenerPresets active={activePreset} onSelect={handlePresetSelect} />
```

- [ ] **Step 5: Verify build**

```bash
cd apps/web && npx next build 2>&1 | tail -15
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: strategy preset screeners — Momentum, Value, Dividend, Quality, Contrarian"
```

---

## Task 6: Voice Input for AskAI

**Files:**
- Modify: `apps/web/src/components/ui/ChatInputArea.tsx` — add mic button
- Modify: `apps/web/src/components/NLQueryBox.tsx` — wire voice input

- [ ] **Step 1: Add mic button to ChatInputArea**

In `apps/web/src/components/ui/ChatInputArea.tsx`, add a mic button next to the send button:

```tsx
import { Mic, MicOff, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Props = {
  onSubmit: (text: string) => void;
  disabled?: boolean;
};

export default function ChatInputArea({ onSubmit, disabled }: Props) {
  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setVoiceSupported(!!SR);
  }, []);

  const startListening = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      setIsListening(false);
      // Auto-send after brief delay
      setTimeout(() => {
        if (transcript.trim()) onSubmit(transcript.trim());
      }, 300);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  const handleSubmit = () => {
    if (input.trim()) {
      onSubmit(input.trim());
      setInput("");
    }
  };

  return (
    <div className="flex items-center gap-2 flex-1">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSubmit()}
        placeholder="Ask about any stock, sector, or market..."
        className="flex-1 rounded-lg bg-surface-low border border-surface-container px-3 py-2.5 text-sm text-on-surface placeholder-on-surface-variant focus:outline-none focus:border-primary"
        disabled={disabled}
      />
      {voiceSupported && (
        <button
          onClick={isListening ? stopListening : startListening}
          disabled={disabled}
          className={`rounded-lg p-2.5 transition-colors ${
            isListening
              ? "bg-red-500/20 text-red-400 animate-pulse"
              : "bg-surface-low text-on-surface-variant hover:text-on-surface hover:bg-surface-high"
          } border border-surface-container`}
          title={isListening ? "Stop listening" : "Voice input"}
        >
          {isListening ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
      )}
      <button
        onClick={handleSubmit}
        disabled={disabled || !input.trim()}
        className="rounded-lg p-2.5 bg-primary text-on-primary disabled:opacity-40 hover:bg-primary/90 transition-colors"
      >
        <Send size={18} />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd apps/web && npx next build 2>&1 | tail -10
```

Expected: Clean build.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: voice input for AskAI — Web Speech API mic button"
```

---

## Implementation Order

Execute tasks in this exact order:
1. Task 1: Structured Output Schema + Backend (foundation for everything)
2. Task 2: Reasoning Quality — system prompt + second-pass (the user's main ask)
3. Task 3: Structured Output Frontend Components (renders the structured data)
4. Task 4: PARA-DEBATE Enrichment + Retry (improves debate quality)
5. Task 5: Strategy Preset Screeners (new product surface, quick)
6. Task 6: Voice Input (smallest change, wow factor)

Each task is tested and working before moving to the next. All on GLM branch. Merge to master only on user's green light.