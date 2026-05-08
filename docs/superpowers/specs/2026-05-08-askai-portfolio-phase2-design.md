# Ask AI Portfolio Output — Phase 2 Design Spec
# Conversational Pre-Query Profiler

**Date:** 2026-05-08
**Scope:** Add conversational pre-query profiler to Ask AI portfolio flow. Ask user risk profile, time horizon, goal, and investable amount before generating portfolio. Two-tier storage: localStorage (guest) + Supabase (auth).
**Parent Spec:** `2026-05-08-askai-portfolio-redesign-design.md` (Phase 1)

---

## 1. Architecture Overview

### Goal
When a user asks a portfolio question (e.g. "I have 50k, how should I invest?"), Ask AI first checks if a saved user profile exists. If not, it renders an inline profiler form within the chat to collect 4 key fields (risk, horizon, goal, amount). Once collected, the profile is persisted and injected into the LLM prompt for personalized portfolio generation. On subsequent portfolio questions, the saved profile is reused — no re-asking.

### Boundary
- Phase 2 does NOT change Phase 1 portfolio rendering. All Phase 1 components remain unchanged.
- Phase 2 does NOT add a new page or route. Everything happens inside NLQueryBox chat.
- Phase 2 does NOT require an additional LLM call. The profile is injected into the existing single LLM prompt.

### High-Level Flow

```
User types portfolio question
    → Backend detects portfolio intent (_is_portfolio_intent)
    → Backend checks for saved profile:
        - Guest: localStorage key "nq_profile"
        - Auth: GET /me/profile from Supabase
    → Profile exists?
        YES → inject profile into LLM system prompt → generate portfolio
        NO  → return StructuredQueryResponse with profiler_needed=true
    → Frontend sees profiler_needed=true
        → renders ProfilerCard inline in chat
        → user fills 4 fields + clicks Submit
        → frontend saves profile (localStorage or POST /me/profile)
        → frontend auto-resends original question with profile attached
    → Backend receives question + profile
        → injects profile into LLM prompt
        → generates personalized portfolio
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Reuse `/query/v2/stream` endpoint | No new backend route needed. Add `profile` optional field to `QueryRequest`. |
| `profiler_needed` flag in response | Frontend branches on this flag to show/hide ProfilerCard. Clean separation. |
| Guest = localStorage, Auth = Supabase | Two-tier storage. Guests get persistence without signup friction. Auth users get cross-device sync. |
| Profile injected into system prompt | LLM receives "User profile: Conservative, 3-5yr horizon, Retirement goal, ₹10L" as context. No model change. |
| Amount asked inline first, rest in form | Hybrid UX: 1 conversational message + 1 quick form. Faster than 4 separate chat turns. |

---

## 2. Data Models

### 2.1 TypeScript Types (`apps/web/src/lib/types.ts`)

```typescript
export interface UserProfile {
  risk_profile: "conservative" | "balanced" | "aggressive";
  time_horizon: "<1yr" | "1-3yr" | "3-5yr" | "5yr+";
  goal: "wealth_building" | "retirement" | "education" | "passive_income" | "tax_saving";
  investable_amount?: string; // e.g. "₹10,00,000" or "$50,000"
  updated_at?: string;
}

// Extend QueryRequest
export interface QueryRequest {
  question: string;
  ticker?: string;
  market?: Market;
  history?: ConversationMessage[];
  profile?: UserProfile; // NEW — sent when profile exists
}

// Extend StructuredQueryResponse
export interface StructuredQueryResponse {
  // ... existing Phase 1 fields unchanged ...
  profiler_needed?: boolean; // NEW — true when profile missing
}
```

### 2.2 Supabase Schema

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  risk_profile TEXT CHECK (risk_profile IN ('conservative','balanced','aggressive')),
  time_horizon TEXT CHECK (time_horizon IN ('<1yr','1-3yr','3-5yr','5yr+')),
  goal TEXT CHECK (goal IN ('wealth_building','retirement','education','passive_income','tax_saving')),
  investable_amount TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Row Level Security: users can only read/write their own profile
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own profile"
  ON user_profiles FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

### 2.3 Pydantic Models (`apps/api/src/nq_api/schemas.py`)

```python
class UserProfile(BaseModel):
    risk_profile: str  # conservative | balanced | aggressive
    time_horizon: str  # <1yr | 1-3yr | 3-5yr | 5yr+
    goal: str  # wealth_building | retirement | education | passive_income | tax_saving
    investable_amount: str | None = None

class QueryRequest(BaseModel):
    question: str
    ticker: str | None = None
    market: str | None = None
    history: list[ConversationMessage] | None = None
    profile: UserProfile | None = None  # NEW
    session_key: str | None = None

class StructuredQueryResponse(BaseModel):
    # ... existing fields ...
    profiler_needed: bool | None = None  # NEW
```

---

## 3. Backend Changes

### 3.1 Profile Injection in System Prompt

When `portfolio_intent=True` and `req.profile` is present, append to user message:

```
USER PROFILE (use this to personalize the portfolio):
- Risk Profile: {profile.risk_profile}
- Time Horizon: {profile.time_horizon}
- Investment Goal: {profile.goal}
- Investable Amount: {profile.investable_amount}

Tailor the portfolio to this profile:
- Conservative = lower equity %, more large-cap, wider stop-losses
- Aggressive = higher equity %, more mid/small-cap, tighter stop-losses
- Short horizon = lower volatility stocks, shorter target timeframe
- Long horizon = can absorb more drawdown, higher growth allocation
- Goal-specific: retirement = income focus; education = capital preservation; wealth building = growth focus
```

### 3.2 `profiler_needed` Response

When `portfolio_intent=True` and no profile:

```python
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
)
```

### 3.3 API Route for Auth Profile (`/me/profile`)

```python
@router.get("/me/profile", response_model=UserProfile | None)
async def get_user_profile(user: User = Depends(get_current_user)):
    """Fetch saved user profile from Supabase."""
    ...

@router.post("/me/profile", response_model=UserProfile)
async def save_user_profile(
    profile: UserProfile,
    user: User = Depends(get_current_user),
):
    """Upsert user profile to Supabase."""
    ...
```

---

## 4. Frontend Components

### 4.1 New Component: `ProfilerCard.tsx`

Renders inline within chat bubble when `profiler_needed=true`.

Props:
```typescript
interface ProfilerCardProps {
  onSubmit: (profile: UserProfile) => void;
}
```

UI:
- 3 dropdowns (risk, horizon, goal) + 1 text input (amount, pre-filled from question if parsed)
- Submit button
- Styled to match Obsidian Quantum design system (glassmorphism, ghost borders)

### 4.2 NLQueryBox Integration

```typescript
// On mount: check for saved profile
useEffect(() => {
  const saved = localStorage.getItem("nq_profile");
  if (saved) setGuestProfile(JSON.parse(saved));
  // Auth profile fetched via useAuth hook
}, []);

// When sending query:
const ask = async (question: string) => {
  const payload: QueryRequest = { question, ... };
  if (savedProfile) payload.profile = savedProfile;
  // ... send SSE request
};

// When response has profiler_needed:
if (res.profiler_needed) {
  // Render ProfilerCard in message list
  setMessages(prev => [...prev, {
    id: Date.now().toString(),
    role: "assistant",
    content: "",
    structured: { profiler_needed: true, ... },
    loading: false,
  }]);
}

// When profiler submitted:
const handleProfilerSubmit = (profile: UserProfile) => {
  // Save profile
  if (user) saveToSupabase(profile);
  else localStorage.setItem("nq_profile", JSON.stringify(profile));
  setSavedProfile(profile);
  // Re-send original question with profile
  ask(lastUserQuestion);
};
```

### 4.3 AIResponseCard Integration

When `parsed.profiler_needed` is true, render `ProfilerCard` instead of portfolio layout:

```tsx
if (parsed.profiler_needed) {
  return <ProfilerCard onSubmit={onProfilerSubmit} />;
}
```

---

## 5. Data Flow + Error Handling

### 5.1 Happy Path (Guest)

1. User: "I want to invest 10 lakhs"
2. Backend: no profile in request → returns `profiler_needed=true`
3. Frontend: renders ProfilerCard
4. User fills form: Conservative, 3-5yr, Retirement, ₹10,00,000
5. Frontend: saves to localStorage, re-sends question with profile
6. Backend: profile present → injects into prompt → generates portfolio
7. Frontend: renders Phase 1 portfolio layout

### 5.2 Happy Path (Auth)

Same as guest, but profile fetched from `/me/profile` on app mount. Saved via POST. Cross-device sync.

### 5.3 Error Cases

| Case | Behavior |
|------|----------|
| Profile fetch fails (Supabase 500) | Frontend falls back to localStorage for this session. Log error. |
| Profile save fails (Supabase 500) | Continue with localStorage. Toast warning: "Profile saved locally only." |
| User edits amount in question after profile saved | New amount overrides saved `investable_amount` for this query only. Does not update saved profile. |
| Guest clears browser data | Profile lost. Next portfolio question triggers profiler again. |
| Invalid amount in text input | Frontend validation: must contain number. No regex strictness on currency format. |

---

## 6. Files to Modify (Phase 2)

| File | Change |
|------|--------|
| `apps/api/src/nq_api/schemas.py` | Add `UserProfile` model; extend `QueryRequest` with `profile`; extend `StructuredQueryResponse` with `profiler_needed` |
| `apps/api/src/nq_api/routes/query.py` | Add profile injection logic; return `profiler_needed` when portfolio intent + no profile |
| `apps/api/src/nq_api/routes/auth.py` | Add `GET /me/profile` and `POST /me/profile` routes |
| `apps/web/src/lib/types.ts` | Add `UserProfile`; extend `QueryRequest` and `StructuredQueryResponse` |
| `apps/web/src/lib/api.ts` | Add `getUserProfile()` and `saveUserProfile()` API helpers |
| `apps/web/src/components/ui/ProfilerCard.tsx` | **New component** — inline profiler form |
| `apps/web/src/components/ui/AIResponseCard.tsx` | Add `profiler_needed` branch to render ProfilerCard |
| `apps/web/src/components/NLQueryBox.tsx` | Fetch profile on mount; pass profile in query payload; handle profiler submission + re-send |
| `apps/web/src/hooks/useAuth.ts` (or similar) | Add profile fetch on auth state change |
| `supabase/migrations/011_user_profiles.sql` | **New migration** — create `user_profiles` table + RLS |

---

## 7. Out of Scope

The following are explicitly deferred to future phases:

- Multi-turn portfolio refinement ("add more large-cap" mutating existing allocation)
- Historical portfolio tracking / performance monitoring
- SEBI registration workflow or compliance automation
- ML-based risk profile inference from user behavior
- Integration with user's actual holdings (broker connection)

---

## 8. Success Criteria

1. First-time portfolio question triggers profiler form 100% of the time.
2. Guest profile persists in localStorage across browser sessions.
3. Auth profile persists in Supabase and syncs across devices.
4. Second portfolio question skips profiler, uses saved profile.
5. Profile is injected into LLM prompt and visibly affects portfolio allocation (e.g. conservative = lower equity %).
6. Single-stock questions are completely unaffected.
7. All new fields are optional — old JSON responses without them do not crash frontend.
