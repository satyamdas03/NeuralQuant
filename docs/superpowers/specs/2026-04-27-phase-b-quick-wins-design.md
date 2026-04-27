# Phase B Quick Wins — Design Spec

**Date:** 2026-04-27
**Branch:** GLM
**Status:** Approved

## Overview

Four features to build on the GLM branch (not master — deployed app stays untouched until green light):

1. AskAI Structured Output
2. PARA-DEBATE Context Enrichment + Retry
3. Strategy Preset Screeners
4. Voice Input for AskAI

---

## Feature 1: AskAI Structured Output

### Problem

All three AskAI routes (SNAP, REACT, DEEP) return `answer: str` containing freeform markdown with `**bold**` clutter, unstructured tables, and inconsistent formatting. Frontend renders this as plain `whitespace-pre-wrap` text.

### Solution

Replace the freeform markdown response with a typed JSON schema. Frontend renders each section with purpose-built React components.

### Backend

**New schema** in `apps/api/src/nq_api/schemas.py`:

```python
class MetricItem(BaseModel):
    name: str
    value: str
    benchmark: str | None = None
    status: Literal["positive", "negative", "neutral"]

class ScenarioItem(BaseModel):
    label: str
    probability: float
    target: str
    thesis: str

class AllocationItem(BaseModel):
    ticker: str
    weight: float
    rationale: str

class ComparisonItem(BaseModel):
    ticker: str
    metric: str
    ours: str
    theirs: str
    edge: str

class StructuredQueryResponse(BaseModel):
    verdict: str                              # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: float                         # 0-100
    timeframe: str                            # Short-term | Medium-term | Long-term
    summary: str                              # 2-3 sentence plain text summary
    metrics: list[MetricItem]
    scenarios: list[ScenarioItem] = []
    allocations: list[AllocationItem] = []    # DEEP route only
    comparisons: list[ComparisonItem] = []    # DEEP route only
    data_sources: list[str]
    follow_up_questions: list[str]
    route: Literal["SNAP", "REACT", "DEEP"]
```

**Versioning:** Add `POST /v2/query` route. Old `/query` stays for backward compat. Frontend calls v2.

**Route changes:**

- **SNAP** (`handle_snap`): Build `StructuredQueryResponse` from score cache / yfinance data directly. No LLM call needed — populate `metrics`, `verdict` from existing data.

- **REACT** (`handle_deep` path in `run_nl_query`): Change Claude system prompt to output JSON matching the schema. Parse with `response_model` or structured output extraction.

- **DEEP** (`handle_deep`): Modify `_synthesize_analyst_response()` to return `StructuredQueryResponse`. Head analyst prompt updated to output structured JSON.

**Prompt strategy:** Each route's system prompt instructs Claude to return a JSON object matching `StructuredQueryResponse`. Use `response_model` parameter or regex-based JSON extraction from the response.

### Frontend

**New components** in `apps/web/src/components/`:

- `VerdictBanner` — color-coded verdict badge (green/yellow/red) + confidence progress bar
- `MetricsGrid` — 2-3 column grid of metric cards with color indicators
- `ScenarioBar` — horizontal probability bars with labels
- `AllocationTable` — ticker/weight/rationale table (shown for DEEP route)
- `ComparisonBlock` — side-by-side peer comparison table (shown for DEEP route)

**Update `AIResponseCard`:** Detect `route` field. If response has structured fields, render components. Fallback to plain text for old `/query` responses.

**Update `NLQueryBox`:** Call `/v2/query` instead of `/query`.

---

## Feature 2: PARA-DEBATE Context Enrichment + Retry

### Problem

Agents return "Insufficient data for analysis" via `_neutral_fallback()` when LLM calls fail or context is sparse. Users see unhelpful NEUTRAL stances.

### Solution

#### 2a. Context Enrichment

Add 20+ yfinance fields to the analyst context dict in `_build_analyst_context()` (`dart_router.py`) and `_build_context_from_cache()`:

New fields to fetch per ticker:
- `revenue_growth`, `fcf_yield`, `debt_equity`, `return_on_equity`
- `insider_transactions` (recent buys/sells), `institutional_ownership_percent`
- `earnings_dates` (next earnings), `analyst_target_mean`, `analyst_target_median`
- `short_ratio`, `beta_5y`, `avg_volume_10d`
- Computed: `insider_cluster_score` (net insider buying signal 0-1), `sector_peers[]` (3-5 tickers), `news_headlines[]` (last 5)

Each agent's `_build_user_message()` already receives the full context dict — enriched data flows automatically.

#### 2b. Retry Mechanism

Modify `BaseAnalystAgent` in `base.py`:

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
        return await self._retry_with_simplified(ticker, context) or self._neutral_fallback(ticker, context)

async def _retry_with_simplified(self, ticker, context) -> AgentOutput | None:
    # Shorter prompt, essential fields only, 15s timeout
    ...

def _neutral_fallback(self, ticker, context) -> AgentOutput:
    # Never say "Insufficient data" — specify what was available
    available = [k for k in context if context[k] is not None]
    return AgentOutput(
        agent=self.agent_name,
        stance="NEUTRAL",
        conviction="LOW",
        thesis=f"{self.agent_name} could not reach a conclusion on {ticker}. Data available: {', '.join(available[:10])}.",
        key_points=["Limited data prevented definitive analysis."],
    )
```

#### 2c. Agent Prompt Rewrites

Add to each agent's system prompt:
- **THRESHOLDS section:** Explicit numeric thresholds (Piotroski >7 strong, <3 weak; momentum >75 high, <25 low; etc.)
- **REASONING PROTOCOL:** Must cite specific data points, must compare to sector average or benchmark, must conclude with "Why X not Y" edge statement

#### 2d. Head Analyst Improvement

- Pass raw context dict alongside agent summaries
- Head analyst prompt: "You have both agent analyses and raw data. Cross-reference claims against data. Flag inconsistencies."
- Better verdict grounding

---

## Feature 3: Strategy Preset Screeners

### What

Pre-built investment strategy presets that auto-populate screener filters with one click.

### Presets

| ID | Name | Description | Filters |
|----|------|-------------|---------|
| momentum_breakout | Momentum Breakout | Strong upward momentum stocks | min_score: 7, min_momentum: 70 |
| value_play | Value Play | Undervalued quality stocks | min_score: 5, min_quality: 70, max_pe: 25 |
| dividend_income | Dividend Income | High-quality dividend payers | min_quality: 60, min_score: 5 |
| quality_compound | Quality Compound | Long-term compounders | min_quality: 80, min_score: 7 |
| contrarian_bet | Contrarian Bet | Beaten down but fundamentally sound | min_quality: 50, max_momentum: 40 |

### Backend

New endpoint `GET /screener/presets` in `routes/screener.py` returning the preset config. No auth required — public endpoint.

Existing `POST /screener` already accepts `min_score`, `min_quality`, `min_momentum` filter params. Presets map to these params.

### Frontend

New `ScreenerPresets` component above `ScreenerTable`:
- Horizontal scrollable card row with icons
- Clicking a preset calls `POST /screener` with preset params
- Active preset highlighted
- "All Stocks" default shows unfiltered top 50

---

## Feature 4: Voice Input

### What

Mic button in AskAI chat using Web Speech API (`SpeechRecognition`).

### Implementation

**`NLQueryBox.tsx` additions (~50 lines):**

- Mic icon button next to send button (use `Mic` icon from lucide-react)
- On click: check `window.SpeechRecognition || window.webkitSpeechRecognition`
- Start listening: show pulsing mic icon, disable text input
- On result: populate input field with transcript, auto-send query
- On error / unsupported browser: show tooltip "Voice input not supported in this browser"
- Listening state tracked with `isListening` boolean

**No backend changes.** Speech-to-text happens entirely in the browser. Transcribed text is sent as a normal query to `/v2/query`.

### Browser Support

- Chrome/Edge: Full support
- Safari: Supported with `webkitSpeechRecognition`
- Firefox: Not supported — fallback tooltip shown

---

## Build Order

1. AskAI Structured Output (biggest UX win, touches most files)
2. PARA-DEBATE Context Enrichment + Retry (improves answer quality)
3. Strategy Preset Screeners (new product surface, quick)
4. Voice Input (smallest change, wow factor)

Each feature is tested and working before moving to the next. All work on GLM branch. Merge to master only on user's green light.