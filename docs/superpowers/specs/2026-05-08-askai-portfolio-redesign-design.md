# Ask AI Portfolio Output Redesign — Phase 1 Design Spec

**Date:** 2026-05-08
**Scope:** Output template redesign for portfolio / investment queries only. Conversational pre-query profiler deferred to Phase 2.
**Approach:** Backward-compatible schema extensions. No breaking changes to existing Ask AI single-stock flow.

---

## 1. Architecture Overview

### Goal
When a user asks a portfolio-style question (e.g. "I have 50k, how do I invest?", "Build a portfolio for me"), Ask AI returns a visually structured response instead of plain JSON cards — a market context strip, allocation bar, stock cards with entry/target/stop-loss, scenario probability bars, action prompt buttons, and a SEBI disclaimer.

### Boundary
Phase 1 does **not** change how the user asks the question. No conversational profiler, no multi-turn form. The LLM receives the user's free-text question plus market context and returns the new structured format. Phase 2 will add the pre-query profiler (targeted questions before the AI builds the portfolio).

### High-level Flow

```
User question
    → _is_portfolio_intent(question)  [lightweight keyword classifier]
    → if portfolio intent:
        - Inject portfolio-specific prompt rules (_PORTFOLIO_OUTPUT_RULES)
        - Inject real-time market context (fetch_real_macro / fetch_real_macro_in)
    → LLM generates StructuredQueryResponse with new optional fields
    → Frontend AIResponseCard detects is_portfolio_response=true
    → Renders new portfolio layout (MarketContextStrip, AllocationBar, etc.)
    → if is_portfolio_response=false or missing:
        → Renders existing single-stock layout (backward compatible)
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keyword-based intent detection, not ML model | Fast, deterministic, good enough for v1. Regex over known portfolio keywords. |
| Optional schema fields (not new endpoint) | One endpoint `/query/v2/stream` serves both modes. Old clients ignore new fields. |
| `is_portfolio_response` flag set by LLM | LLM self-declares when it produced a portfolio layout. Frontend trusts this flag for routing. |
| Market context from existing `fetch_real_macro()` | Reuses live macro data already available. No new data sources. |
| SEBI disclaimer hardcoded in frontend + LLM prompt | Regulatory requirement for Indian investment advice. LLM includes it; frontend renders prominently. |

---

## 2. Backend Schema + Prompt Engineering

### 2.1 New Pydantic Models (in `apps/api/src/nq_api/schemas.py`)

All new fields are **Optional** and default to `None`. Existing `StructuredQueryResponse` fields remain unchanged.

```python
class MarketContextCard(BaseModel):
    label: str           # e.g. "NIFTY 50", "VIX"
    value: str           # e.g. "23,456", "17.4"
    change: Optional[str] = None   # e.g. "+1.2%", "-0.8%"
    sentiment: Optional[str] = None  # "bullish" | "bearish" | "neutral"

class AllocationSegment(BaseModel):
    label: str           # e.g. "Equity Large-Cap"
    percentage: float    # 0–100
    color: Optional[str] = None    # hex color for bar rendering
    rationale: Optional[str] = None  # one-line why this allocation

class PortfolioStockCard(BaseModel):
    ticker: str
    name: Optional[str] = None
    allocation_pct: float  # within portfolio
    entry_price: Optional[str] = None      # e.g. "$287.50"
    target_price: Optional[str] = None     # e.g. "$320.00"
    stop_loss: Optional[str] = None        # e.g. "$260.00"
    risk_reward: Optional[str] = None      # e.g. "1:2.3"
    rationale: Optional[str] = None        # one-line why this stock
    confidence: Optional[int] = None       # 1–10 ForeCast score
    sector: Optional[str] = None

class ScenarioCard(BaseModel):
    label: str           # e.g. "Bull Case", "Base Case", "Bear Case"
    probability_pct: Optional[int] = None  # 0–100
    outcome: Optional[str] = None          # e.g. "+18% in 12 months"
    description: Optional[str] = None      # 1–2 sentence narrative
    color: Optional[str] = None            # hex for probability bar

class ActionPrompt(BaseModel):
    label: str           # e.g. "Add more large-cap?", "Show me mid-cap options?"
    prompt_text: str     # exact text to send as next query
    icon: Optional[str] = None             # emoji or icon name
```

### 2.2 Extended `StructuredQueryResponse`

Add these optional fields to the existing model:

```python
class StructuredQueryResponse(BaseModel):
    # ... existing fields unchanged ...

    # --- Phase 1: portfolio output fields (all optional) ---
    market_context: Optional[list[MarketContextCard]] = None
    allocation_breakdown: Optional[list[AllocationSegment]] = None
    portfolio_stocks: Optional[list[PortfolioStockCard]] = None
    scenario_analysis: Optional[list[ScenarioCard]] = None
    action_prompts: Optional[list[ActionPrompt]] = None
    sebi_disclaimer: Optional[str] = None
    is_portfolio_response: Optional[bool] = None  # LLM self-declares
```

### 2.3 Intent Detection

```python
_PORTFOLIO_KEYWORDS = [
    "portfolio", "allocate", "allocation", "diversify",
    "how to invest", "where should i invest", "build a portfolio",
    "investment plan", "invest my money", "investment strategy",
    "split my money", "where to put", "how much in", "lump sum",
    "monthly sip", "recurring investment", "long term plan",
    "retirement plan", "child education", "goal based",
]

_PORTFOLIO_TICKER_SIGNS = [
    "i have", "i hold", "my holdings", "i own", "i bought",
    "my portfolio", "i want to invest", "should i buy",
]

def _is_portfolio_intent(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _PORTFOLIO_KEYWORDS) or any(kw in q for kw in _PORTFOLIO_TICKER_SIGNS)
```

Called inside `query.py` before constructing the LLM system prompt. No database state, no user profile. Pure text classification.

### 2.4 Portfolio-Specific Prompt Rules

When `_is_portfolio_intent(question)` returns `True`, append `_PORTFOLIO_OUTPUT_RULES` to the system prompt (after `_SYSTEM_STRUCTURED`):

```
PORTFOLIO OUTPUT RULES (activate only if user asks about portfolio allocation, investment plan, or multiple-stock strategy):

- market_context: Include 3–5 live market context cards. Use real index levels, VIX, and 10Y yield if available. Mark live data with [VERIFIED].
- allocation_breakdown: Show percentage allocation across asset classes / market-cap buckets. Total must sum to 100%. Provide rationale per segment.
- portfolio_stocks: For each recommended stock, include ticker, allocation_pct within portfolio, suggested entry_price, target_price, stop_loss, and risk_reward ratio. Include a one-line rationale and ForeCast confidence 1–10.
- scenario_analysis: Provide exactly 3 scenarios — Bull, Base, Bear. Each gets a probability percentage and 12-month outcome estimate.
- action_prompts: Include 2–3 follow-up prompt buttons that help the user refine the portfolio (e.g., "Add more large-cap?", "Show me mid-cap options?", "Make it more conservative?").
- sebi_disclaimer: Always include the SEBI disclaimer: "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."
- is_portfolio_response: Set this field to true so the frontend knows to render the portfolio layout.
```

### 2.5 Market Context Injection

When portfolio intent is detected:

1. Detect market from user question (IN keywords → India, else default US).
2. Call existing `fetch_real_macro()` or `fetch_real_macro_in()` from `data_builder.py`.
3. Format into a short "Market Snapshot" string appended to the system prompt:

```
Current Market Snapshot (use these exact values, mark [VERIFIED]):
- S&P 500: {sp500_level} [VERIFIED]
- NASDAQ: {nasdaq_level} [VERIFIED]
- VIX: {vix_level} [VERIFIED]
- US 10Y Yield: {yield_10y}% [VERIFIED]
- NIFTY 50: {nifty_level} [VERIFIED]  (if IN market)
- USD/INR: {usd_inr} [VERIFIED]      (if IN market)
```

This reuses existing functions with no new dependencies.

---

## 3. Frontend Components

### 3.1 New Components (all in `apps/web/src/components/ui/`)

| Component | Props | Purpose |
|-----------|-------|---------|
| `MarketContextStrip` | `cards: MarketContextCard[]` | Horizontal scrolling strip of index / VIX / yield cards |
| `AllocationBar` | `segments: AllocationSegment[]` | Stacked horizontal bar chart showing allocation % |
| `PortfolioStockCard` | `stock: PortfolioStockCard` | Card with ticker, allocation %, entry/target/SL, rationale |
| `ScenarioAnalysisPanel` | `scenarios: ScenarioCard[]` | 3-column panel with probability bars and outcome text |
| `ActionPromptButtons` | `prompts: ActionPrompt[], onPromptClick: (text: string) => void` | Row of clickable pill buttons that trigger a new query |
| `SEBIDisclaimer` | `text: string` | Styled disclaimer block (small, muted, prominent border) |

### 3.2 `AIResponseCard.tsx` Integration

Inside `AIResponseCard`, after parsing `StructuredQueryResponse`:

```tsx
if (parsed.is_portfolio_response) {
  return (
    <div className="portfolio-response">
      <MarketContextStrip cards={parsed.market_context ?? []} />
      <AllocationBar segments={parsed.allocation_breakdown ?? []} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(parsed.portfolio_stocks ?? []).map(s => <PortfolioStockCard key={s.ticker} stock={s} />)}
      </div>
      <ScenarioAnalysisPanel scenarios={parsed.scenario_analysis ?? []} />
      <ActionPromptButtons prompts={parsed.action_prompts ?? []} onPromptClick={onFollowUp} />
      <SEBIDisclaimer text={parsed.sebi_disclaimer ?? DEFAULT_SEBI_TEXT} />
    </div>
  );
}
// else: existing single-stock rendering (unchanged)
```

The `onFollowUp` function is passed down from `NLQueryBox` — it triggers the same SSE stream with the prompt text.

### 3.3 TypeScript Type Updates (`apps/web/src/lib/types.ts`)

Add these interfaces (matching Pydantic models) to the existing `StructuredQueryResponse`:

```typescript
export interface MarketContextCard { label: string; value: string; change?: string; sentiment?: string; }
export interface AllocationSegment { label: string; percentage: number; color?: string; rationale?: string; }
export interface PortfolioStockCard { ticker: string; name?: string; allocation_pct: number; entry_price?: string; target_price?: string; stop_loss?: string; risk_reward?: string; rationale?: string; confidence?: number; sector?: string; }
export interface ScenarioCard { label: string; probability_pct?: number; outcome?: string; description?: string; color?: string; }
export interface ActionPrompt { label: string; prompt_text: string; icon?: string; }

// Add to existing StructuredQueryResponse:
export interface StructuredQueryResponse {
  // ... existing fields ...
  market_context?: MarketContextCard[];
  allocation_breakdown?: AllocationSegment[];
  portfolio_stocks?: PortfolioStockCard[];
  scenario_analysis?: ScenarioCard[];
  action_prompts?: ActionPrompt[];
  sebi_disclaimer?: string;
  is_portfolio_response?: boolean;
}
```

---

## 4. Data Flow + Error Handling

### 4.1 Happy Path

1. User types portfolio question → NLQueryBox sends SSE request.
2. Backend detects intent → injects portfolio rules + market snapshot.
3. LLM returns JSON with `is_portfolio_response: true` and populated new fields.
4. Frontend detects flag → renders portfolio layout.
5. User clicks action prompt → new SSE request with prompt text → repeat.

### 4.2 Error Cases + Fallbacks

| Case | Behavior |
|------|----------|
| LLM returns `is_portfolio_response: false` or field missing | Frontend falls back to existing single-stock layout. |
| `market_context` is empty / null | `MarketContextStrip` renders "Market data unavailable" placeholder. |
| `allocation_breakdown` sums to != 100% | `AllocationBar` clamps visually; shows raw values with a warning pill. |
| `portfolio_stocks` contains invalid ticker | Card renders with "Data unavailable" badge; other stocks still show. |
| `action_prompts` missing or empty | Section hidden entirely; no broken UI. |
| `sebi_disclaimer` missing | Frontend renders hardcoded default SEBI disclaimer. Never skip disclaimer. |
| Backend intent detection false negative (user asks portfolio question, backend misses) | LLM may still produce portfolio output based on prompt semantics; flag may still be set. If not, user gets single-stock layout — acceptable degradation. |
| Backend intent detection false positive (single-stock question flagged as portfolio) | LLM receives portfolio rules. If LLM ignores them (single-stock question doesn't need allocation), it likely sets `is_portfolio_response: false`. Frontend falls back safely. |

### 4.3 Validation Rules (Backend Post-Processing)

After LLM response, before sending to frontend:

```python
if response.is_portfolio_response:
    # 1. Allocation sum check
    total = sum(s.percentage for s in (response.allocation_breakdown or []))
    if abs(total - 100.0) > 1.0:
        response.data_quality_flags = response.data_quality_flags or []
        response.data_quality_flags.append(f"Allocation sums to {total:.1f}% (expected 100%)")

    # 2. SEBI disclaimer presence check
    if not response.sebi_disclaimer or "SEBI" not in response.sebi_disclaimer.upper():
        response.sebi_disclaimer = DEFAULT_SEBI_DISCLAIMER

    # 3. Scenario count check
    scenarios = response.scenario_analysis or []
    if len(scenarios) < 3:
        response.data_quality_flags.append("Scenario analysis incomplete")
```

---

## 5. Testing Plan

### 5.1 Backend Tests

1. **Intent detection accuracy**: Feed 20 portfolio questions + 20 single-stock questions. Expect >= 90% correct classification.
2. **Schema round-trip**: Create `StructuredQueryResponse` with all new fields. Serialize to JSON → deserialize → assert equality.
3. **Prompt injection**: Verify `_PORTFOLIO_OUTPUT_RULES` only appended when intent=true. Verify market snapshot string present.
4. **SEBI fallback**: Test LLM output missing disclaimer → backend injects default.

### 5.2 Frontend Tests

5. **Component rendering**: Mount `AIResponseCard` with `is_portfolio_response=true` and mock data. Assert all 6 sub-components render.
6. **Action prompt click**: Simulate click on `ActionPromptButtons` → assert `onPromptClick` callback fires with correct text.
7. **Fallback rendering**: Mount with `is_portfolio_response=false` → assert legacy layout renders (existing test pattern).
8. **Missing data resilience**: Mount with `is_portfolio_response=true` but `portfolio_stocks=null` → assert no crash, disclaimer still shows.

### 5.3 End-to-End Tests

9. **Portfolio question → portfolio layout**: "I have 1 lakh rupees, how should I invest?" → expect market strip, allocation bar, stock cards, scenarios, action prompts, SEBI disclaimer.
10. **Single-stock question → legacy layout**: "What do you think of NVDA?" → expect existing StockSummaryCard + VerdictBanner.
11. **Action prompt click → new stream**: Click "Show me mid-cap options?" → expect new SSE stream with that exact text.
12. **India market context**: "Build a portfolio for Indian market" → expect NIFTY 50, USD/INR in market context strip.

---

## 6. Files to Modify (Phase 1)

| File | Change |
|------|--------|
| `apps/api/src/nq_api/schemas.py` | Add 5 new Pydantic models; extend `StructuredQueryResponse` with 7 optional fields |
| `apps/api/src/nq_api/routes/query.py` | Add `_is_portfolio_intent()`, `_PORTFOLIO_KEYWORDS`, `_PORTFOLIO_OUTPUT_RULES`, market snapshot injection logic |
| `apps/api/src/nq_api/data_builder.py` | Ensure `fetch_real_macro()` / `fetch_real_macro_in()` are importable from query.py (likely already are) |
| `apps/web/src/lib/types.ts` | Add 5 new TypeScript interfaces; extend `StructuredQueryResponse` |
| `apps/web/src/components/ui/AIResponseCard.tsx` | Add portfolio branch rendering; pass `onFollowUp` through props |
| `apps/web/src/components/ui/MarketContextStrip.tsx` | New component |
| `apps/web/src/components/ui/AllocationBar.tsx` | New component |
| `apps/web/src/components/ui/PortfolioStockCard.tsx` | New component |
| `apps/web/src/components/ui/ScenarioAnalysisPanel.tsx` | New component |
| `apps/web/src/components/ui/ActionPromptButtons.tsx` | New component |
| `apps/web/src/components/ui/SEBIDisclaimer.tsx` | New component |
| `apps/web/src/components/NLQueryBox.tsx` | Pass `ask` function into `AIResponseCard` for action prompt callbacks |

---

## 7. Out of Scope (Phase 2)

The following are **explicitly deferred** to a future Phase 2 spec:

- Conversational pre-query profiler (ask user risk profile, time horizon, goal, investable amount before generating portfolio).
- User preference storage (risk tolerance, existing holdings, goal tracking).
- Multi-turn portfolio refinement ("add more large-cap" should mutate existing allocation, not generate from scratch).
- Historical portfolio tracking / performance monitoring.
- SEBI registration workflow or compliance automation.

---

## 8. Success Criteria

1. Portfolio questions trigger the new layout 100% of the time (intent detection + LLM flag alignment).
2. Single-stock questions continue to render the legacy layout unchanged.
3. All new fields are optional — old JSON responses without them do not crash the frontend.
4. SEBI disclaimer renders on every portfolio response, even if LLM omits it.
5. Action prompt buttons successfully trigger follow-up SSE queries.
6. Market context cards show live [VERIFIED] data (S&P, NIFTY, VIX, etc.).
