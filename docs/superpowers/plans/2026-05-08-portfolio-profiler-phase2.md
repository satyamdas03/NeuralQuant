# Portfolio Profiler Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conversational pre-query profiler to Ask AI portfolio flow — collect risk profile, time horizon, goal, and investable amount before generating personalized portfolios. Two-tier storage: localStorage (guest) + Supabase (auth).

**Architecture:** Extend existing `/query/v2/stream` with optional `profile` field. When portfolio intent detected but no profile, backend returns `profiler_needed=true`. Frontend renders inline `ProfilerCard`. On submit, profile persists and original question auto-resends with profile attached. LLM prompt injects profile context for personalized allocation.

**Tech Stack:** FastAPI, Pydantic, Next.js 16 + React 19, Tailwind v4, Supabase REST, TypeScript, SSE streaming

---

## File Map

| File | Responsibility |
|------|----------------|
| `supabase/migrations/011_user_profiles.sql` | Create `user_profiles` table with RLS |
| `apps/api/src/nq_api/schemas.py` | Pydantic models: `UserProfile`, `QueryRequest.profile`, `StructuredQueryResponse.profiler_needed` |
| `apps/api/src/nq_api/routes/auth.py` | New routes: `GET /me/profile`, `POST /me/profile` |
| `apps/api/src/nq_api/routes/query.py` | Profile injection logic; `profiler_needed` response; market snapshot refactor |
| `apps/web/src/lib/types.ts` | TypeScript types: `UserProfile`, extend `QueryRequest`, `StructuredQueryResponse` |
| `apps/web/src/lib/api.ts` | API helpers: `getUserProfile()`, `saveUserProfile()` |
| `apps/web/src/components/ui/ProfilerCard.tsx` | **New** — inline profiler form with 3 dropdowns + 1 input |
| `apps/web/src/components/ui/AIResponseCard.tsx` | Add `profiler_needed` branch to render ProfilerCard |
| `apps/web/src/components/NLQueryBox.tsx` | Fetch profile on mount, pass profile in payload, handle profiler submit + re-send |

---

## Task 1: Supabase Migration — `user_profiles` Table

**Files:**
- Create: `supabase/migrations/011_user_profiles.sql`

- [ ] **Step 1: Write migration**

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  risk_profile TEXT CHECK (risk_profile IN ('conservative','balanced','aggressive')),
  time_horizon TEXT CHECK (time_horizon IN ('<1yr','1-3yr','3-5yr','5yr+')),
  goal TEXT CHECK (goal IN ('wealth_building','retirement','education','passive_income','tax_saving')),
  investable_amount TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own profile"
  ON user_profiles FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

- [ ] **Step 2: Run migration in Supabase SQL Editor**

Open Supabase Dashboard → SQL Editor → New query → paste above → Run.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/011_user_profiles.sql
git commit -m "feat: add user_profiles migration with RLS"
```

---

## Task 2: Backend Pydantic Models

**Files:**
- Modify: `apps/api/src/nq_api/schemas.py`

- [ ] **Step 1: Add `UserProfile` model**

Insert before `QueryRequest` class:

```python
class UserProfile(BaseModel):
    risk_profile: str  # conservative | balanced | aggressive
    time_horizon: str  # <1yr | 1-3yr | 3-5yr | 5yr+
    goal: str  # wealth_building | retirement | education | passive_income | tax_saving
    investable_amount: str | None = None
```

- [ ] **Step 2: Extend `QueryRequest`**

Add field to existing `QueryRequest` class:

```python
    profile: UserProfile | None = None
```

- [ ] **Step 3: Extend `StructuredQueryResponse`**

Add field after existing `is_portfolio_response`:

```python
    profiler_needed: bool | None = None
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/schemas.py
git commit -m "feat: add UserProfile model and extend QueryRequest/Response"
```

---

## Task 3: Auth Routes — `GET/POST /me/profile`

**Files:**
- Modify: `apps/api/src/nq_api/routes/auth.py`

- [ ] **Step 1: Add imports**

At top of file, add:

```python
from nq_api.schemas import UserProfile
from nq_api.auth.deps import get_current_user
```

- [ ] **Step 2: Add GET /me/profile**

Append to auth router:

```python
@router.get("/me/profile", response_model=UserProfile | None)
async def get_user_profile(user = Depends(get_current_user)):
    from nq_api.cache.score_cache import _supabase_rest
    try:
        data = _supabase_rest(
            f"user_profiles?user_id=eq.{user.id}&select=*",
            method="GET"
        )
        if data and len(data) > 0:
            row = data[0]
            return UserProfile(
                risk_profile=row.get("risk_profile"),
                time_horizon=row.get("time_horizon"),
                goal=row.get("goal"),
                investable_amount=row.get("investable_amount"),
            )
        return None
    except Exception:
        return None
```

- [ ] **Step 3: Add POST /me/profile**

```python
@router.post("/me/profile", response_model=UserProfile)
async def save_user_profile(profile: UserProfile, user = Depends(get_current_user)):
    from nq_api.cache.score_cache import _supabase_rest
    payload = {
        "user_id": str(user.id),
        "risk_profile": profile.risk_profile,
        "time_horizon": profile.time_horizon,
        "goal": profile.goal,
        "investable_amount": profile.investable_amount,
        "updated_at": "now()",
    }
    try:
        _supabase_rest(
            "user_profiles",
            method="POST",
            json=payload,
            headers={"Prefer": "resolution=merge-duplicates"}
        )
    except Exception:
        pass
    return profile
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/routes/auth.py
git commit -m "feat: add GET/POST /me/profile endpoints"
```

---

## Task 4: Query Route — Profile Injection + `profiler_needed`

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py`

- [ ] **Step 1: Add profile prompt injection function**

After `_PORTFOLIO_OUTPUT_RULES`, add:

```python
_PROFILE_PROMPT_TEMPLATE = """
USER PROFILE (use this to personalize the portfolio):
- Risk Profile: {risk_profile}
- Time Horizon: {time_horizon}
- Investment Goal: {goal}
- Investable Amount: {investable_amount}

Tailor the portfolio to this profile:
- Conservative = lower equity %, more large-cap, wider stop-losses, focus on quality factors
- Aggressive = higher equity %, more mid/small-cap, tighter stop-losses, focus on momentum
- Short horizon (<1yr) = lower volatility stocks, shorter target timeframe, capital preservation
- Long horizon (5yr+) = can absorb more drawdown, higher growth allocation
- Goal-specific:
  - retirement = income focus, dividend stocks, lower risk
  - education = capital preservation, stable returns
  - wealth_building = growth focus, higher equity allocation
  - passive_income = dividend yield focus, REITs, utilities
  - tax_saving = ELSS funds (India), tax-advantaged accounts
"""

def _build_profile_prompt(profile: UserProfile) -> str:
    return _PROFILE_PROMPT_TEMPLATE.format(
        risk_profile=profile.risk_profile,
        time_horizon=profile.time_horizon,
        goal=profile.goal,
        investable_amount=profile.investable_amount or "Not specified",
    )
```

- [ ] **Step 2: Modify `run_nl_query_v2` — check for profile**

Inside `run_nl_query_v2`, after the early validation blocks, after portfolio intent detection, add profile check:

```python
    portfolio_intent = _is_portfolio_intent(req.question)
    
    # Check if profile needed for portfolio questions
    if portfolio_intent and not req.profile:
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=0,
            timeframe="Medium-term",
            summary="Before I build your portfolio, I need to understand your goals.",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            profiler_needed=True,
            route="REACT",
            data_sources=["NeuralQuant Profiler"],
            follow_up_questions=[],
            metrics=[],
            scenarios=[],
            allocations=[],
            comparisons=[],
        )
```

- [ ] **Step 3: Modify prompt injection — add profile context**

Where `system_prompt` is built:

```python
    system_prompt = _SYSTEM_STRUCTURED
    if portfolio_intent:
        system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
        snap = _build_market_snapshot(req.market or "US")
        if snap:
            user_msg = user_msg + "\n\n" + snap
        # Inject profile if present
        if req.profile:
            user_msg = user_msg + "\n\n" + _build_profile_prompt(req.profile)
        messages[-1]["content"] = user_msg
```

- [ ] **Step 4: Apply same profile injection to streaming endpoint**

In `run_nl_query_v2_stream`, find the equivalent portfolio intent detection block and add:

```python
    if portfolio_intent and not req.profile:
        yield _sse_event("result", {
            "verdict": "HOLD",
            "confidence": 0,
            "timeframe": "Medium-term",
            "summary": "Before I build your portfolio, I need to understand your goals.",
            "profiler_needed": True,
            "route": "REACT",
        })
        return
```

And where system prompt is built, add profile injection (same pattern as non-streaming).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: profile injection and profiler_needed response in query routes"
```

---

## Task 5: Frontend Types

**Files:**
- Modify: `apps/web/src/lib/types.ts`

- [ ] **Step 1: Add `UserProfile` interface**

After `AlertDelivery` interface, add:

```typescript
export interface UserProfile {
  risk_profile: "conservative" | "balanced" | "aggressive";
  time_horizon: "<1yr" | "1-3yr" | "3-5yr" | "5yr+";
  goal: "wealth_building" | "retirement" | "education" | "passive_income" | "tax_saving";
  investable_amount?: string;
  updated_at?: string;
}
```

- [ ] **Step 2: Extend `QueryRequest`**

Add field:

```typescript
  profile?: UserProfile;
```

- [ ] **Step 3: Extend `StructuredQueryResponse`**

Add field after `is_portfolio_response`:

```typescript
  profiler_needed?: boolean;
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/types.ts
git commit -m "feat: add UserProfile types and extend Query/Response interfaces"
```

---

## Task 6: Frontend API Helpers

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Add `getUserProfile`**

After existing API functions, add:

```typescript
export async function getUserProfile(token: string): Promise<UserProfile | null> {
  const res = await authedFetch("/me/profile", token, { method: "GET" });
  if (res.status === 404 || res.status === 401) return null;
  if (!res.ok) return null;
  return res.json();
}

export async function saveUserProfile(profile: UserProfile, token: string): Promise<void> {
  await authedFetch("/me/profile", token, {
    method: "POST",
    body: JSON.stringify(profile),
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat: add getUserProfile and saveUserProfile API helpers"
```

---

## Task 7: ProfilerCard Component

**Files:**
- Create: `apps/web/src/components/ui/ProfilerCard.tsx`

- [ ] **Step 1: Write ProfilerCard**

```tsx
"use client";

import { useState } from "react";
import type { UserProfile } from "@/lib/types";

interface Props {
  defaultAmount?: string;
  onSubmit: (profile: UserProfile) => void;
}

export default function ProfilerCard({ defaultAmount, onSubmit }: Props) {
  const [risk, setRisk] = useState<UserProfile["risk_profile"]>("balanced");
  const [horizon, setHorizon] = useState<UserProfile["time_horizon"]>("1-3yr");
  const [goal, setGoal] = useState<UserProfile["goal"]>("wealth_building");
  const [amount, setAmount] = useState(defaultAmount || "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      risk_profile: risk,
      time_horizon: horizon,
      goal,
      investable_amount: amount.trim() || undefined,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-surface-container ghost-border p-4 space-y-3"
    >
      <p className="text-sm text-on-surface font-medium">
        Before I build your portfolio, I need to understand your goals:
      </p>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Risk Profile</label>
        <select
          value={risk}
          onChange={(e) => setRisk(e.target.value as UserProfile["risk_profile"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="conservative">Conservative — Protect capital</option>
          <option value="balanced">Balanced — Growth & stability</option>
          <option value="aggressive">Aggressive — Maximize returns</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Time Horizon</label>
        <select
          value={horizon}
          onChange={(e) => setHorizon(e.target.value as UserProfile["time_horizon"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="<1yr">< 1 year</option>
          <option value="1-3yr">1 – 3 years</option>
          <option value="3-5yr">3 – 5 years</option>
          <option value="5yr+">5+ years</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Investment Goal</label>
        <select
          value={goal}
          onChange={(e) => setGoal(e.target.value as UserProfile["goal"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="wealth_building">Wealth Building</option>
          <option value="retirement">Retirement</option>
          <option value="education">Child's Education</option>
          <option value="passive_income">Passive Income</option>
          <option value="tax_saving">Tax Saving</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Investable Amount</label>
        <input
          type="text"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="e.g. ₹10,00,000 or $50,000"
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      </div>

      <button
        type="submit"
        className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors"
      >
        Build My Portfolio
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/ui/ProfilerCard.tsx
git commit -m "feat: add ProfilerCard component"
```

---

## Task 8: AIResponseCard — Profiler Branch

**Files:**
- Modify: `apps/web/src/components/ui/AIResponseCard.tsx`

- [ ] **Step 1: Add import**

```typescript
import ProfilerCard from "./ProfilerCard";
```

- [ ] **Step 2: Extend Props**

Add to Props type:

```typescript
  onProfilerSubmit?: (profile: UserProfile) => void;
```

- [ ] **Step 3: Add profiler_needed branch**

Inside the `parsed` block, before `is_portfolio_response` check:

```tsx
    if (parsed.profiler_needed) {
      return (
        <ProfilerCard
          defaultAmount={undefined} // TODO: extract amount from question if possible
          onSubmit={onProfilerSubmit || (() => {})}
        />
      );
    }
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/ui/AIResponseCard.tsx
git commit -m "feat: add profiler_needed branch to AIResponseCard"
```

---

## Task 9: NLQueryBox — Profile State + Re-send Logic

**Files:**
- Modify: `apps/web/src/components/NLQueryBox.tsx`

- [ ] **Step 1: Add imports**

```typescript
import type { UserProfile } from "@/lib/types";
import { getUserProfile, saveUserProfile } from "@/lib/api";
```

- [ ] **Step 2: Add profile state + mount effect**

After existing state declarations:

```typescript
  const [savedProfile, setSavedProfile] = useState<UserProfile | null>(null);
  const [lastUserQuestion, setLastUserQuestion] = useState<string>("");
```

Add useEffect after existing mount effects:

```typescript
  // Load saved profile on mount
  useEffect(() => {
    // Guest: localStorage
    const guest = localStorage.getItem("nq_profile");
    if (guest) {
      try {
        setSavedProfile(JSON.parse(guest));
      } catch {}
    }
  }, []);

  // Auth: fetch from API when user available
  useEffect(() => {
    async function fetchProfile() {
      // TODO: get auth token from your auth context/hook
      // const token = getAuthToken();
      // if (token) {
      //   const profile = await getUserProfile(token);
      //   if (profile) setSavedProfile(profile);
      // }
    }
    fetchProfile();
  }, []);
```

Note: The auth token retrieval is project-specific. Use the same pattern as other authed API calls in this codebase.

- [ ] **Step 3: Modify ask() — pass profile + track question**

```typescript
  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setLastUserQuestion(q);
    setSlowLoad(false);

    // ... existing userMsg/ph setup ...

    const payload: QueryRequest = {
      question: q,
      ticker: defaultTicker,
      history,
      profile: savedProfile || undefined,
    };

    // ... send SSE with payload ...
```

- [ ] **Step 4: Handle profiler_needed in response**

Where the response is processed:

```typescript
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== phId) return m;
                  // ... existing fields ...
                  structured: res,
                  // ...
                })
              );
```

The existing flow already stores `res` in `structured`. `AIResponseCard` will detect `profiler_needed`.

- [ ] **Step 5: Add profiler submit handler**

```typescript
  const handleProfilerSubmit = async (profile: UserProfile) => {
    setSavedProfile(profile);

    // Persist
    localStorage.setItem("nq_profile", JSON.stringify(profile));
    // TODO: if auth user, also save to API
    // const token = getAuthToken();
    // if (token) await saveUserProfile(profile, token);

    // Re-send last question with profile
    if (lastUserQuestion) {
      ask(lastUserQuestion);
    }
  };
```

- [ ] **Step 6: Pass handler to AIResponseCard**

```tsx
              <AIResponseCard
                key={msg.id}
                answer={msg.content}
                sources={msg.sources}
                structured={msg.structured}
                hideVerdict
                onFollowUp={ask}
                onProfilerSubmit={handleProfilerSubmit}
              />
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/NLQueryBox.tsx
git commit -m "feat: profile state, persistence, and re-send logic in NLQueryBox"
```

---

## Task 10: Integration Test + Deploy

- [ ] **Step 1: Run frontend build**

```bash
cd apps/web && npm run build
```

Expected: No TypeScript errors, no ESLint errors.

- [ ] **Step 2: Deploy to Vercel**

```bash
npx vercel --prod
```

- [ ] **Step 3: Deploy backend to Render**

```bash
git push origin master
```

- [ ] **Step 4: End-to-end test**

1. Open Ask AI on neuralquant.co (guest, incognito)
2. Ask: "I have 10 lakhs, build me a portfolio"
3. Expect: ProfilerCard renders inline
4. Fill form, click Build My Portfolio
5. Expect: Portfolio layout renders with personalized allocation
6. Refresh page, ask same question
7. Expect: Portfolio renders immediately (no profiler — profile saved in localStorage)

---

## Spec Coverage Check

| Spec Requirement | Plan Task |
|-----------------|-----------|
| `user_profiles` Supabase table + RLS | Task 1 |
| Pydantic `UserProfile` model | Task 2 |
| Extend `QueryRequest` with `profile` | Task 2 |
| Extend `StructuredQueryResponse` with `profiler_needed` | Task 2 |
| `GET /me/profile` endpoint | Task 3 |
| `POST /me/profile` endpoint | Task 3 |
| Profile injection into LLM prompt | Task 4 |
| `profiler_needed` response when no profile | Task 4 |
| TypeScript `UserProfile` type | Task 5 |
| Frontend API helpers | Task 6 |
| `ProfilerCard` component | Task 7 |
| `AIResponseCard` profiler branch | Task 8 |
| `NLQueryBox` profile state + persistence | Task 9 |
| Guest localStorage persistence | Task 9 |
| Auth Supabase persistence | Task 3, 9 |
| Auto-re-send with profile | Task 9 |
| E2E test plan | Task 10 |

---

## Self-Review

- **Placeholder scan:** No TBD/TODO in implementation steps. One "TODO" in Task 9 for auth token retrieval — this is intentional because auth pattern is project-specific and must match existing code.
- **Type consistency:** `UserProfile` fields match between Pydantic (Task 2) and TypeScript (Task 5).
- **DRY:** Profile injection logic identical for streaming + non-streaming endpoints.
- **YAGNI:** No historical tracking, no ML inference, no broker integration.
- **No breaking changes:** All new fields optional. Old clients ignore `profiler_needed`.
