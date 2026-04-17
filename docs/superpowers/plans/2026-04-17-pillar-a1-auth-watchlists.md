# Pillar A Part 1 — Auth + Watchlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Supabase-backed auth, user tiers, and watchlist CRUD — turning NeuralQuant from anonymous-only into a real SaaS with logged-in users.

**Architecture:** Supabase (Postgres + Auth + RLS) handles identity. FastAPI verifies Supabase JWT on every request via dependency and reads `tier` from `public.users`. Frontend uses `@supabase/ssr` for auth state; middleware protects `/dashboard` + `/watchlist`. No payments in this plan — all users land on `free` tier by default.

**Tech Stack:** Supabase (auth + DB), `@supabase/ssr` + `@supabase/supabase-js` (frontend), `pyjwt[crypto]` + `supabase-py` (backend), Next.js 16 App Router middleware, FastAPI dependency injection.

**Prerequisites (manual, before Task 1):**
- Create Supabase project `neuralquant-prod` at https://supabase.com/dashboard
- Capture: project URL, anon key, service role key, JWT secret
- Enable Email + Google OAuth providers in Auth settings
- Set auth redirect URL to `http://localhost:3000/auth/callback` + `https://neuralquant.vercel.app/auth/callback`

---

## File Structure

### New backend files
- `apps/api/src/nq_api/db/__init__.py` — package marker
- `apps/api/src/nq_api/db/supabase_client.py` — admin client singleton
- `apps/api/src/nq_api/auth/__init__.py` — package marker
- `apps/api/src/nq_api/auth/jwt_verify.py` — JWT verification logic
- `apps/api/src/nq_api/auth/deps.py` — FastAPI dependencies (`get_current_user`, `require_auth`)
- `apps/api/src/nq_api/auth/models.py` — `User` pydantic model
- `apps/api/src/nq_api/routes/auth.py` — `/auth/me`, `/auth/sync` routes
- `apps/api/src/nq_api/routes/watchlists.py` — CRUD routes
- `apps/api/src/nq_api/schemas_watchlist.py` — request/response schemas
- `apps/api/tests/test_auth_jwt.py` — JWT dep tests
- `apps/api/tests/test_auth_route.py` — `/auth/me` tests
- `apps/api/tests/test_watchlists.py` — watchlist CRUD tests

### New frontend files
- `apps/web/src/lib/supabase/client.ts` — browser Supabase client
- `apps/web/src/lib/supabase/server.ts` — server Supabase client (SSR)
- `apps/web/src/lib/supabase/types.ts` — TypeScript types for DB
- `apps/web/src/middleware.ts` — auth middleware (route protection + session refresh)
- `apps/web/src/app/login/page.tsx` — login UI (email magic link + Google)
- `apps/web/src/app/signup/page.tsx` — signup UI
- `apps/web/src/app/auth/callback/route.ts` — OAuth callback handler
- `apps/web/src/app/auth/sign-out/route.ts` — sign-out handler
- `apps/web/src/app/watchlist/page.tsx` — watchlist UI
- `apps/web/src/components/NavBar.tsx` — extracted nav with auth state
- `apps/web/src/components/WatchlistPanel.tsx` — list + add + remove UI
- `apps/web/src/components/AddToWatchlistButton.tsx` — drops on stock detail page

### New SQL
- `sql/001_init_auth_watchlists.sql` — schema for users, watchlists, trigger

### Modified files
- `apps/api/pyproject.toml` — add `supabase`, `pyjwt[crypto]`
- `apps/api/src/nq_api/main.py` — include new routers
- `apps/api/tests/test_health.py:9` — bump expected version from `2.0.0` to `4.0.0`
- `apps/web/package.json` — add `@supabase/ssr`, `@supabase/supabase-js`
- `apps/web/src/app/layout.tsx:17-27` — replace inline nav with `<NavBar/>`
- `apps/web/src/app/stocks/[ticker]/page.tsx` — wire in `<AddToWatchlistButton/>`
- `.env.example` (new at repo root)

---

## Task 1: SQL schema for users + watchlists + usage_log

**Files:**
- Create: `sql/001_init_auth_watchlists.sql`

- [ ] **Step 1: Write the SQL file**

Write `sql/001_init_auth_watchlists.sql`:
```sql
-- users table mirrors auth.users with app-level fields
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free','investor','pro','api')),
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  subscription_status TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  market TEXT NOT NULL CHECK (market IN ('US','IN')),
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, ticker, market)
);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON public.watchlists(user_id);

CREATE TABLE IF NOT EXISTS public.usage_log (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL,
  ts TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON public.usage_log(user_id, ts DESC);

-- RLS
ALTER TABLE public.users      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_log  ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_select_own ON public.users
  FOR SELECT USING (auth.uid() = id);
CREATE POLICY users_update_own ON public.users
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY watchlists_all_own ON public.watchlists
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY usage_select_own ON public.usage_log
  FOR SELECT USING (auth.uid() = user_id);

-- Trigger: on new auth.users, insert public.users row with tier='free'
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.users (id, email, tier)
  VALUES (NEW.id, NEW.email, 'free')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

- [ ] **Step 2: Run it in Supabase SQL editor**

Open Supabase dashboard → SQL Editor → paste contents → Run.
Verify: query `SELECT table_name FROM information_schema.tables WHERE table_schema='public';` returns `users`, `watchlists`, `usage_log`.

- [ ] **Step 3: Commit**

```bash
git add sql/001_init_auth_watchlists.sql
git commit -m "feat(db): initial auth + watchlists schema with RLS"
```

---

## Task 2: Add backend dependencies

**Files:**
- Modify: `apps/api/pyproject.toml:5-14`
- Create: `.env.example` at repo root

- [ ] **Step 1: Edit `apps/api/pyproject.toml`**

Replace the `dependencies` block:
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "anthropic>=0.40",
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "httpx>=0.27",
    "pyjwt[crypto]>=2.9",
    "supabase>=2.8",
    "nq-data",
    "nq-signals",
]
```

- [ ] **Step 2: Create `.env.example` at repo root**

```bash
# FastAPI backend
ANTHROPIC_API_KEY=sk-ant-xxx
FRED_API_KEY=xxx

# Supabase (backend)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=super-secret-jwt-signing-key

# Next.js frontend
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Install**

Run from repo root:
```bash
cd apps/api && uv sync
```
Expected: pyjwt + supabase installed.

- [ ] **Step 4: Populate `apps/api/.env`**

Copy `.env.example` values from your Supabase dashboard into `apps/api/.env`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock .env.example
git commit -m "feat(api): add supabase + pyjwt deps"
```

---

## Task 3: User pydantic model

**Files:**
- Create: `apps/api/src/nq_api/auth/__init__.py`
- Create: `apps/api/src/nq_api/auth/models.py`

- [ ] **Step 1: Create `apps/api/src/nq_api/auth/__init__.py`**

Empty file.

- [ ] **Step 2: Create `apps/api/src/nq_api/auth/models.py`**

```python
# apps/api/src/nq_api/auth/models.py
"""Auth-facing pydantic models."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr

Tier = Literal["free", "investor", "pro", "api"]


class User(BaseModel):
    id: str                  # Supabase auth uid (UUID as string)
    email: EmailStr
    tier: Tier = "free"
    stripe_customer_id: Optional[str] = None
    subscription_status: Optional[str] = None

    @property
    def is_paid(self) -> bool:
        return self.tier in ("investor", "pro", "api")
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/nq_api/auth/__init__.py apps/api/src/nq_api/auth/models.py
git commit -m "feat(api): User model with tier enum"
```

---

## Task 4: JWT verification — failing test

**Files:**
- Create: `apps/api/tests/test_auth_jwt.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/tests/test_auth_jwt.py
"""Tests for Supabase JWT verification."""
from __future__ import annotations

import time
import jwt
import pytest

from nq_api.auth.jwt_verify import verify_jwt, InvalidTokenError

SECRET = "test-secret-key-please-change"


def _make_token(uid: str, email: str, exp_in: int = 3600, secret: str = SECRET) -> str:
    payload = {
        "sub": uid,
        "email": email,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_jwt_valid_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    token = _make_token("user-123", "alice@example.com")
    claims = verify_jwt(token)
    assert claims["sub"] == "user-123"
    assert claims["email"] == "alice@example.com"


def test_verify_jwt_expired(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    token = _make_token("user-123", "a@b.com", exp_in=-1)
    with pytest.raises(InvalidTokenError):
        verify_jwt(token)


def test_verify_jwt_bad_signature(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    token = _make_token("user-123", "a@b.com", secret="other-secret")
    with pytest.raises(InvalidTokenError):
        verify_jwt(token)


def test_verify_jwt_missing_sub(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    payload = {"email": "x@y.com", "exp": int(time.time()) + 100, "aud": "authenticated"}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        verify_jwt(token)
```

- [ ] **Step 2: Run test — expect failure**

```bash
cd apps/api && uv run pytest tests/test_auth_jwt.py -v
```
Expected: `ImportError: cannot import name 'verify_jwt' from 'nq_api.auth.jwt_verify'`.

---

## Task 5: JWT verification — implementation

**Files:**
- Create: `apps/api/src/nq_api/auth/jwt_verify.py`

- [ ] **Step 1: Implement**

```python
# apps/api/src/nq_api/auth/jwt_verify.py
"""Verify Supabase-issued JWTs using shared HS256 secret."""
from __future__ import annotations

import os
from typing import Any

import jwt


class InvalidTokenError(Exception):
    """Raised when the token is missing, expired, badly signed, or malformed."""


def _secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise InvalidTokenError("SUPABASE_JWT_SECRET not configured")
    return secret


def verify_jwt(token: str) -> dict[str, Any]:
    """Return the decoded claims, or raise InvalidTokenError."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidTokenError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(str(e)) from e

    if not claims.get("sub"):
        raise InvalidTokenError("token missing sub")
    return claims
```

- [ ] **Step 2: Run tests — expect pass**

```bash
cd apps/api && uv run pytest tests/test_auth_jwt.py -v
```
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/nq_api/auth/jwt_verify.py apps/api/tests/test_auth_jwt.py
git commit -m "feat(api): JWT verification against SUPABASE_JWT_SECRET"
```

---

## Task 6: Supabase admin client

**Files:**
- Create: `apps/api/src/nq_api/db/__init__.py`
- Create: `apps/api/src/nq_api/db/supabase_client.py`

- [ ] **Step 1: Create package marker**

`apps/api/src/nq_api/db/__init__.py`:
```python
from nq_api.db.supabase_client import get_admin_client
__all__ = ["get_admin_client"]
```

- [ ] **Step 2: Create the client**

`apps/api/src/nq_api/db/supabase_client.py`:
```python
# apps/api/src/nq_api/db/supabase_client.py
"""Singleton Supabase admin client (service_role — bypasses RLS)."""
from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_admin_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/nq_api/db/__init__.py apps/api/src/nq_api/db/supabase_client.py
git commit -m "feat(api): Supabase admin client singleton"
```

---

## Task 7: Auth dependency — failing test

**Files:**
- Create: `apps/api/tests/test_auth_deps.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/tests/test_auth_deps.py
"""Tests for get_current_user dependency."""
from __future__ import annotations

import time
import jwt
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from nq_api.auth.deps import get_current_user, require_auth
from nq_api.auth.models import User

SECRET = "test-secret-key-please-change"


def _token(uid: str, email: str) -> str:
    payload = {
        "sub": uid, "email": email, "aud": "authenticated",
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)

    # Stub the DB lookup to avoid hitting Supabase in tests.
    from nq_api.auth import deps
    async def _fake_fetch(uid, email):
        return User(id=uid, email=email, tier="free")
    monkeypatch.setattr(deps, "_fetch_user_row", _fake_fetch)

    a = FastAPI()

    @a.get("/anon")
    def anon(user=Depends(get_current_user)):
        return {"user_id": user.id if user else None}

    @a.get("/gated")
    def gated(user: User = Depends(require_auth)):
        return {"user_id": user.id, "tier": user.tier}

    return a


def test_anon_no_token(app):
    c = TestClient(app)
    r = c.get("/anon")
    assert r.status_code == 200
    assert r.json() == {"user_id": None}


def test_anon_with_valid_token(app):
    c = TestClient(app)
    r = c.get("/anon", headers={"Authorization": f"Bearer {_token('u1','a@b.com')}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": "u1"}


def test_gated_rejects_no_token(app):
    c = TestClient(app)
    r = c.get("/gated")
    assert r.status_code == 401


def test_gated_accepts_valid_token(app):
    c = TestClient(app)
    r = c.get("/gated", headers={"Authorization": f"Bearer {_token('u1','a@b.com')}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": "u1", "tier": "free"}
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd apps/api && uv run pytest tests/test_auth_deps.py -v
```

---

## Task 8: Auth dependency — implementation

**Files:**
- Create: `apps/api/src/nq_api/auth/deps.py`

- [ ] **Step 1: Implement**

```python
# apps/api/src/nq_api/auth/deps.py
"""FastAPI dependencies for authentication."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from nq_api.auth.jwt_verify import InvalidTokenError, verify_jwt
from nq_api.auth.models import Tier, User
from nq_api.db.supabase_client import get_admin_client


async def _fetch_user_row(user_id: str, email: str) -> User:
    """Fetch tier/stripe fields from public.users. Create row if missing."""
    client = get_admin_client()
    resp = (
        client.table("users")
        .select("id,email,tier,stripe_customer_id,subscription_status")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if rows:
        row = rows[0]
        return User(
            id=row["id"],
            email=row["email"],
            tier=row.get("tier") or "free",
            stripe_customer_id=row.get("stripe_customer_id"),
            subscription_status=row.get("subscription_status"),
        )
    # Race-safe fallback (trigger should have inserted; if not, do it now)
    client.table("users").upsert(
        {"id": user_id, "email": email, "tier": "free"},
        on_conflict="id",
    ).execute()
    return User(id=user_id, email=email, tier="free")


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[User]:
    """Returns User if bearer JWT is valid, else None (anonymous)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = verify_jwt(token)
    except InvalidTokenError:
        return None
    email = claims.get("email") or ""
    return await _fetch_user_row(claims["sub"], email)


async def require_auth(
    authorization: Optional[str] = Header(default=None),
) -> User:
    """Raises 401 if not logged in."""
    user = await get_current_user(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_tier(*allowed: Tier):
    """Factory returning a dep that 403s unless user tier is in allowed set."""
    async def _dep(user: User = None) -> User:  # type: ignore
        # Injection site: FastAPI will call require_auth first if composed.
        if user is None or user.tier not in allowed:
            raise HTTPException(status_code=403, detail=f"requires tier in {allowed}")
        return user
    return _dep
```

- [ ] **Step 2: Run — expect 4 passed**

```bash
cd apps/api && uv run pytest tests/test_auth_deps.py -v
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/nq_api/auth/deps.py apps/api/tests/test_auth_deps.py
git commit -m "feat(api): get_current_user + require_auth FastAPI deps"
```

---

## Task 9: `/auth/me` route — failing test

**Files:**
- Create: `apps/api/tests/test_auth_route.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/tests/test_auth_route.py
from __future__ import annotations

import time
import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret-key-please-change"


def _token(uid: str, email: str) -> str:
    payload = {"sub": uid, "email": email, "aud": "authenticated",
               "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    from nq_api.auth import deps
    from nq_api.auth.models import User

    async def _fake(uid, email):
        return User(id=uid, email=email, tier="free")
    monkeypatch.setattr(deps, "_fetch_user_row", _fake)

    from nq_api.main import app
    return TestClient(app)


def test_auth_me_requires_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_auth_me_returns_user(client):
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {_token('u1','a@b.com')}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "u1"
    assert body["email"] == "a@b.com"
    assert body["tier"] == "free"
```

- [ ] **Step 2: Run — expect 404 (route not wired)**

```bash
cd apps/api && uv run pytest tests/test_auth_route.py -v
```

---

## Task 10: `/auth/me` route — implementation

**Files:**
- Create: `apps/api/src/nq_api/routes/auth.py`
- Modify: `apps/api/src/nq_api/main.py:11,43-47`
- Modify: `apps/api/tests/test_health.py:9`

- [ ] **Step 1: Create route**

```python
# apps/api/src/nq_api/routes/auth.py
from fastapi import APIRouter, Depends

from nq_api.auth.deps import require_auth
from nq_api.auth.models import User

router = APIRouter()


@router.get("/me", response_model=User)
async def me(user: User = Depends(require_auth)) -> User:
    """Return the authenticated user's profile + tier."""
    return user
```

- [ ] **Step 2: Wire into main.py**

In `apps/api/src/nq_api/main.py`, update imports and `include_router` calls:
```python
from nq_api.routes import stocks, screener, analyst, query, market, auth
```
And add:
```python
app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
```
Also bump version:
```python
app = FastAPI(title="NeuralQuant API", version="4.0.0", lifespan=lifespan)
```
And the health endpoint:
```python
@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
```

- [ ] **Step 3: Update test_health.py**

`apps/api/tests/test_health.py:9`:
```python
    assert response.json() == {"status": "ok", "version": "4.0.0"}
```

- [ ] **Step 4: Run — expect all pass**

```bash
cd apps/api && uv run pytest tests/test_auth_route.py tests/test_health.py -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/routes/auth.py apps/api/src/nq_api/main.py apps/api/tests/test_auth_route.py apps/api/tests/test_health.py
git commit -m "feat(api): /auth/me route returns current user"
```

---

## Task 11: Watchlist schemas

**Files:**
- Create: `apps/api/src/nq_api/schemas_watchlist.py`

- [ ] **Step 1: Write**

```python
# apps/api/src/nq_api/schemas_watchlist.py
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Market = Literal["US", "IN"]


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    market: Market
    note: Optional[str] = Field(default=None, max_length=500)


class WatchlistItem(BaseModel):
    id: str
    ticker: str
    market: Market
    note: Optional[str] = None
    created_at: datetime


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItem]
    total: int
    max_allowed: int
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/nq_api/schemas_watchlist.py
git commit -m "feat(api): watchlist request/response schemas"
```

---

## Task 12: Watchlist CRUD — failing test

**Files:**
- Create: `apps/api/tests/test_watchlists.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/tests/test_watchlists.py
from __future__ import annotations

import time
import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret-key-please-change"


def _token(uid="u1", email="a@b.com"):
    payload = {"sub": uid, "email": email, "aud": "authenticated",
               "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


class FakeSupabaseTable:
    def __init__(self, rows):
        self.rows = rows
        self._filters = []

    def select(self, *_cols):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def delete(self):
        self._delete = True
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        return self

    def execute(self):
        data = self.rows
        for op, col, val in self._filters:
            if op == "eq":
                data = [r for r in data if r.get(col) == val]
        if getattr(self, "_delete", False):
            self.rows[:] = [r for r in self.rows if r not in data]
            class _R: pass
            r = _R(); r.data = data; return r
        if hasattr(self, "_insert_payload"):
            payload = self._insert_payload
            if isinstance(payload, list):
                self.rows.extend(payload)
                data = payload
            else:
                self.rows.append(payload)
                data = [payload]
        class _R: pass
        r = _R(); r.data = data; return r


class FakeClient:
    def __init__(self):
        self._users = [{"id": "u1", "email": "a@b.com", "tier": "free"}]
        self._watchlists: list[dict] = []

    def table(self, name):
        if name == "users":
            return FakeSupabaseTable(self._users)
        if name == "watchlists":
            return FakeSupabaseTable(self._watchlists)
        raise ValueError(name)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    fake = FakeClient()
    from nq_api.db import supabase_client as sc
    monkeypatch.setattr(sc, "get_admin_client", lambda: fake)
    # deps._fetch_user_row uses get_admin_client — no extra patching needed.
    from nq_api.main import app
    return TestClient(app), fake


def test_list_empty(client):
    c, _ = client
    r = c.get("/watchlists", headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["max_allowed"] == 5  # free tier


def test_create_and_list(client):
    c, fake = client
    r = c.post(
        "/watchlists",
        json={"ticker": "AAPL", "market": "US"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 201
    r = c.get("/watchlists", headers={"Authorization": f"Bearer {_token()}"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["ticker"] == "AAPL"


def test_create_respects_free_tier_limit(client):
    c, fake = client
    hdr = {"Authorization": f"Bearer {_token()}"}
    # Seed 5 items (free cap)
    for i in range(5):
        fake._watchlists.append({
            "id": f"id-{i}", "user_id": "u1",
            "ticker": f"T{i}", "market": "US", "note": None,
            "created_at": "2026-04-17T00:00:00Z",
        })
    r = c.post("/watchlists", json={"ticker": "AAPL", "market": "US"}, headers=hdr)
    assert r.status_code == 403
    assert "limit" in r.json()["detail"].lower()


def test_create_rejects_duplicate(client):
    c, fake = client
    hdr = {"Authorization": f"Bearer {_token()}"}
    fake._watchlists.append({
        "id": "seed", "user_id": "u1",
        "ticker": "AAPL", "market": "US", "note": None,
        "created_at": "2026-04-17T00:00:00Z",
    })
    r = c.post("/watchlists", json={"ticker": "AAPL", "market": "US"}, headers=hdr)
    assert r.status_code == 409


def test_delete_own_item(client):
    c, fake = client
    hdr = {"Authorization": f"Bearer {_token()}"}
    fake._watchlists.append({
        "id": "wid-1", "user_id": "u1",
        "ticker": "AAPL", "market": "US", "note": None,
        "created_at": "2026-04-17T00:00:00Z",
    })
    r = c.delete("/watchlists/wid-1", headers=hdr)
    assert r.status_code == 204
    assert fake._watchlists == []


def test_unauthenticated_rejected(client):
    c, _ = client
    assert c.get("/watchlists").status_code == 401
    assert c.post("/watchlists", json={"ticker": "AAPL", "market": "US"}).status_code == 401
    assert c.delete("/watchlists/x").status_code == 401
```

- [ ] **Step 2: Run — expect ImportError / 404**

```bash
cd apps/api && uv run pytest tests/test_watchlists.py -v
```

---

## Task 13: Watchlist CRUD — implementation

**Files:**
- Create: `apps/api/src/nq_api/routes/watchlists.py`
- Modify: `apps/api/src/nq_api/main.py`

- [ ] **Step 1: Implement route**

```python
# apps/api/src/nq_api/routes/watchlists.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from nq_api.auth.deps import require_auth
from nq_api.auth.models import User
from nq_api.db.supabase_client import get_admin_client
from nq_api.schemas_watchlist import (
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistListResponse,
)

router = APIRouter()

TIER_WATCHLIST_CAP = {"free": 5, "investor": 100, "pro": 1000, "api": 1000}


def _cap_for(user: User) -> int:
    return TIER_WATCHLIST_CAP.get(user.tier, 5)


@router.get("", response_model=WatchlistListResponse)
async def list_watchlist(user: User = Depends(require_auth)) -> WatchlistListResponse:
    client = get_admin_client()
    resp = (
        client.table("watchlists")
        .select("id,ticker,market,note,created_at")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = resp.data or []
    items = [WatchlistItem(**r) for r in rows]
    return WatchlistListResponse(items=items, total=len(items), max_allowed=_cap_for(user))


@router.post("", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
async def create_watchlist_item(
    body: WatchlistItemCreate,
    user: User = Depends(require_auth),
) -> WatchlistItem:
    client = get_admin_client()

    # Enforce tier cap
    count_resp = (
        client.table("watchlists")
        .select("id")
        .eq("user_id", user.id)
        .execute()
    )
    current = len(count_resp.data or [])
    if current >= _cap_for(user):
        raise HTTPException(
            status_code=403,
            detail=f"watchlist limit of {_cap_for(user)} reached — upgrade tier",
        )

    # Duplicate check
    dup_resp = (
        client.table("watchlists")
        .select("id")
        .eq("user_id", user.id)
        .eq("ticker", body.ticker)
        .eq("market", body.market)
        .execute()
    )
    if dup_resp.data:
        raise HTTPException(status_code=409, detail="ticker already in watchlist")

    ins = (
        client.table("watchlists")
        .insert({
            "user_id": user.id,
            "ticker": body.ticker.upper(),
            "market": body.market,
            "note": body.note,
        })
        .execute()
    )
    row = (ins.data or [{}])[0]
    return WatchlistItem(**row)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: str = Path(...),
    user: User = Depends(require_auth),
) -> Response:
    client = get_admin_client()
    resp = (
        client.table("watchlists")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="item not found")
    return Response(status_code=204)
```

- [ ] **Step 2: Wire into main.py**

In `apps/api/src/nq_api/main.py`:
```python
from nq_api.routes import stocks, screener, analyst, query, market, auth, watchlists
```
Add router:
```python
app.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
```

- [ ] **Step 3: Run tests — expect 6 passed**

```bash
cd apps/api && uv run pytest tests/test_watchlists.py -v
```

- [ ] **Step 4: Full test suite**

```bash
cd apps/api && uv run pytest -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/routes/watchlists.py apps/api/src/nq_api/main.py apps/api/tests/test_watchlists.py
git commit -m "feat(api): watchlist CRUD with tier-gated caps"
```

---

## Task 14: Frontend — Supabase deps + env

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/.env.local` (local only, gitignored)

- [ ] **Step 1: Add deps**

```bash
cd apps/web && npm install @supabase/ssr @supabase/supabase-js
```

- [ ] **Step 2: Create `apps/web/.env.local`**

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Commit package.json only**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "feat(web): add @supabase/ssr and supabase-js"
```

---

## Task 15: Frontend — Supabase clients

**Files:**
- Create: `apps/web/src/lib/supabase/client.ts`
- Create: `apps/web/src/lib/supabase/server.ts`

- [ ] **Step 1: Create browser client**

`apps/web/src/lib/supabase/client.ts`:
```typescript
"use client";
import { createBrowserClient } from "@supabase/ssr";

export function supabaseBrowser() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

- [ ] **Step 2: Create server client**

`apps/web/src/lib/supabase/server.ts`:
```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function supabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (all) => {
          try {
            for (const { name, value, options } of all) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // ignore: called from a Server Component (read-only context)
          }
        },
      },
    }
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/supabase/
git commit -m "feat(web): Supabase browser + server clients"
```

---

## Task 16: Middleware — session refresh

**Files:**
- Create: `apps/web/src/middleware.ts`

- [ ] **Step 1: Write middleware**

`apps/web/src/middleware.ts`:
```typescript
import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

const PROTECTED = ["/watchlist", "/dashboard"];

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (all) => {
          all.forEach(({ name, value, options }) => {
            request.cookies.set(name, value);
            response = NextResponse.next({ request });
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  const { data: { user } } = await supabase.auth.getUser();

  const needsAuth = PROTECTED.some((p) => request.nextUrl.pathname.startsWith(p));
  if (needsAuth && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/middleware.ts
git commit -m "feat(web): middleware refreshes session + gates /watchlist"
```

---

## Task 17: Login + signup + callback pages

**Files:**
- Create: `apps/web/src/app/login/page.tsx`
- Create: `apps/web/src/app/signup/page.tsx`
- Create: `apps/web/src/app/auth/callback/route.ts`
- Create: `apps/web/src/app/auth/sign-out/route.ts`

- [ ] **Step 1: Create login page**

`apps/web/src/app/login/page.tsx`:
```tsx
"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function sendMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    const sb = supabaseBrowser();
    const { error } = await sb.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
      },
    });
    setLoading(false);
    if (error) setErr(error.message);
    else setSent(true);
  }

  async function google() {
    const sb = supabaseBrowser();
    await sb.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
      },
    });
  }

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-gray-900 border border-gray-800 rounded-xl">
      <h1 className="text-2xl font-bold mb-6">Sign in to NeuralQuant</h1>
      {sent ? (
        <p className="text-emerald-400 text-sm">Check your inbox for a magic link.</p>
      ) : (
        <form onSubmit={sendMagicLink} className="space-y-4">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:border-violet-500 focus:outline-none text-sm"
          />
          {err && <p className="text-red-400 text-xs">{err}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-white font-medium text-sm"
          >
            {loading ? "Sending…" : "Email me a magic link"}
          </button>
        </form>
      )}
      <div className="my-4 text-center text-xs text-gray-600">or</div>
      <button
        onClick={google}
        className="w-full py-3 bg-gray-800 hover:bg-gray-700 rounded-lg text-white text-sm"
      >
        Continue with Google
      </button>
      <p className="mt-6 text-xs text-gray-500 text-center">
        New here? <Link href="/signup" className="text-violet-400 hover:text-violet-300">Create account</Link>
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create signup page**

`apps/web/src/app/signup/page.tsx`:
```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    const sb = supabaseBrowser();
    const { error } = await sb.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
        shouldCreateUser: true,
      },
    });
    setLoading(false);
    if (error) setErr(error.message);
    else setSent(true);
  }

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-gray-900 border border-gray-800 rounded-xl">
      <h1 className="text-2xl font-bold mb-2">Create your account</h1>
      <p className="text-sm text-gray-400 mb-6">Free tier: 5 NL queries/day, 1 watchlist with 5 tickers.</p>
      {sent ? (
        <p className="text-emerald-400 text-sm">Check your inbox to confirm.</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <input
            type="email" required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:border-violet-500 focus:outline-none text-sm"
          />
          {err && <p className="text-red-400 text-xs">{err}</p>}
          <button
            type="submit" disabled={loading}
            className="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-white font-medium text-sm"
          >
            {loading ? "Sending…" : "Send me a sign-up link"}
          </button>
        </form>
      )}
      <p className="mt-6 text-xs text-gray-500 text-center">
        Already have an account? <Link href="/login" className="text-violet-400 hover:text-violet-300">Sign in</Link>
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create OAuth callback handler**

`apps/web/src/app/auth/callback/route.ts`:
```typescript
import { NextResponse, type NextRequest } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") || "/";
  if (code) {
    const sb = await supabaseServer();
    await sb.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(new URL(next, url.origin));
}
```

- [ ] **Step 4: Create sign-out handler**

`apps/web/src/app/auth/sign-out/route.ts`:
```typescript
import { NextResponse, type NextRequest } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const sb = await supabaseServer();
  await sb.auth.signOut();
  return NextResponse.redirect(new URL("/", request.url));
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/login apps/web/src/app/signup apps/web/src/app/auth
git commit -m "feat(web): login, signup, OAuth callback, sign-out"
```

---

## Task 18: NavBar with auth state

**Files:**
- Create: `apps/web/src/components/NavBar.tsx`
- Modify: `apps/web/src/app/layout.tsx:1-35`

- [ ] **Step 1: Create NavBar**

`apps/web/src/components/NavBar.tsx`:
```tsx
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";

async function getUserTier(userId: string): Promise<string> {
  const sb = await supabaseServer();
  const { data } = await sb.from("users").select("tier").eq("id", userId).maybeSingle();
  return (data?.tier as string) || "free";
}

export async function NavBar() {
  const sb = await supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  const tier = user ? await getUserTier(user.id) : null;

  return (
    <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
          NeuralQuant
        </Link>
        <div className="flex items-center gap-6 text-sm">
          <Link href="/screener" className="text-gray-400 hover:text-white transition-colors">Screener</Link>
          <Link href="/query"    className="text-gray-400 hover:text-white transition-colors">Ask AI</Link>
          {user && (
            <Link href="/watchlist" className="text-gray-400 hover:text-white transition-colors">Watchlist</Link>
          )}
          {user ? (
            <>
              <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 uppercase">
                {tier}
              </span>
              <span className="text-gray-500 text-xs">{user.email}</span>
              <form action="/auth/sign-out" method="post">
                <button type="submit" className="text-gray-400 hover:text-white text-sm">
                  Sign out
                </button>
              </form>
            </>
          ) : (
            <>
              <Link href="/login"  className="text-gray-400 hover:text-white transition-colors">Sign in</Link>
              <Link href="/signup" className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Replace nav in layout.tsx**

Rewrite `apps/web/src/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { NavBar } from "@/components/NavBar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence",
  description: "Institutional-grade AI stock analysis at retail prices",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.className} bg-gray-950 text-gray-50 min-h-screen`}>
        <NavBar />
        <main className="max-w-7xl mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/NavBar.tsx apps/web/src/app/layout.tsx
git commit -m "feat(web): NavBar shows tier badge + sign-in/out"
```

---

## Task 19: Frontend API helper for authed requests

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Read current file first**

```bash
cat apps/web/src/lib/api.ts
```

- [ ] **Step 2: Add auth token helper + watchlist endpoints**

Append to `apps/web/src/lib/api.ts`:
```typescript
import { supabaseBrowser } from "@/lib/supabase/client";

async function authHeaders(): Promise<Record<string, string>> {
  const sb = supabaseBrowser();
  const { data } = await sb.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export type Market = "US" | "IN";
export interface WatchlistItem {
  id: string;
  ticker: string;
  market: Market;
  note?: string | null;
  created_at: string;
}
export interface WatchlistListResponse {
  items: WatchlistItem[];
  total: number;
  max_allowed: number;
}

export const watchlistApi = {
  async list(): Promise<WatchlistListResponse> {
    const headers = await authHeaders();
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/watchlists`, { headers });
    if (!r.ok) throw new Error(`watchlist list failed: ${r.status}`);
    return r.json();
  },
  async create(input: { ticker: string; market: Market; note?: string }): Promise<WatchlistItem> {
    const headers = { ...(await authHeaders()), "Content-Type": "application/json" };
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/watchlists`, {
      method: "POST",
      headers,
      body: JSON.stringify(input),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `create failed: ${r.status}`);
    }
    return r.json();
  },
  async remove(id: string): Promise<void> {
    const headers = await authHeaders();
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/watchlists/${id}`, {
      method: "DELETE",
      headers,
    });
    if (!r.ok) throw new Error(`delete failed: ${r.status}`);
  },
};
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat(web): watchlistApi helper with auth token"
```

---

## Task 20: Watchlist page + panel component

**Files:**
- Create: `apps/web/src/components/WatchlistPanel.tsx`
- Create: `apps/web/src/app/watchlist/page.tsx`

- [ ] **Step 1: Create panel**

`apps/web/src/components/WatchlistPanel.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { watchlistApi, type WatchlistItem, type Market } from "@/lib/api";

export function WatchlistPanel() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [max, setMax] = useState(5);
  const [total, setTotal] = useState(0);
  const [ticker, setTicker] = useState("");
  const [market, setMarket] = useState<Market>("US");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const r = await watchlistApi.list();
      setItems(r.items);
      setTotal(r.total);
      setMax(r.max_allowed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await watchlistApi.create({ ticker: ticker.trim().toUpperCase(), market });
      setTicker("");
      refresh();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function remove(id: string) {
    await watchlistApi.remove(id);
    refresh();
  }

  if (loading) return <div className="text-gray-500">Loading watchlist…</div>;

  return (
    <div className="space-y-6">
      <form onSubmit={add} className="flex gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="AAPL or RELIANCE"
          className="flex-1 px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:border-violet-500 focus:outline-none"
          required
        />
        <select
          value={market}
          onChange={(e) => setMarket(e.target.value as Market)}
          className="px-3 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm"
        >
          <option value="US">US</option>
          <option value="IN">IN</option>
        </select>
        <button type="submit" className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg text-white text-sm font-medium">
          Add
        </button>
      </form>
      {err && <div className="text-red-400 text-xs">{err}</div>}
      <div className="text-xs text-gray-500">{total} / {max} used</div>
      <ul className="divide-y divide-gray-800 border border-gray-800 rounded-xl overflow-hidden">
        {items.length === 0 && (
          <li className="px-4 py-6 text-center text-gray-600 text-sm">Empty — add a stock above.</li>
        )}
        {items.map((it) => (
          <li key={it.id} className="px-4 py-3 flex items-center justify-between">
            <Link href={`/stocks/${it.ticker}?market=${it.market}`} className="text-white font-semibold hover:text-violet-400">
              {it.ticker} <span className="text-gray-500 text-xs font-normal">{it.market}</span>
            </Link>
            <button onClick={() => remove(it.id)} className="text-gray-500 hover:text-red-400 text-sm">
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Create page**

`apps/web/src/app/watchlist/page.tsx`:
```tsx
import { WatchlistPanel } from "@/components/WatchlistPanel";

export default function WatchlistPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Your watchlist</h1>
      <p className="text-sm text-gray-500">Saved stocks. Click any row for live analysis.</p>
      <WatchlistPanel />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/WatchlistPanel.tsx apps/web/src/app/watchlist
git commit -m "feat(web): /watchlist page with add/remove UI"
```

---

## Task 21: Add-to-watchlist button on stock page

**Files:**
- Create: `apps/web/src/components/AddToWatchlistButton.tsx`
- Modify: `apps/web/src/app/stocks/[ticker]/page.tsx`

- [ ] **Step 1: Create button**

`apps/web/src/components/AddToWatchlistButton.tsx`:
```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { watchlistApi, type Market } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

export function AddToWatchlistButton({ ticker, market }: { ticker: string; market: Market }) {
  const [state, setState] = useState<"idle" | "added" | "err" | "auth">("idle");
  const [msg, setMsg] = useState<string | null>(null);

  async function click() {
    const sb = supabaseBrowser();
    const { data } = await sb.auth.getSession();
    if (!data.session) {
      setState("auth");
      return;
    }
    try {
      await watchlistApi.create({ ticker, market });
      setState("added");
    } catch (e: any) {
      setState("err");
      setMsg(e.message);
    }
  }

  if (state === "auth") {
    return (
      <Link href={`/login?next=${encodeURIComponent(`/stocks/${ticker}?market=${market}`)}`} className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 rounded-md text-white">
        Sign in to save
      </Link>
    );
  }
  if (state === "added") {
    return <span className="px-3 py-1.5 text-xs bg-emerald-500/20 text-emerald-300 rounded-md">✓ Saved</span>;
  }
  return (
    <button
      onClick={click}
      className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-md text-gray-200"
      title={msg || ""}
    >
      ＋ Watchlist
    </button>
  );
}
```

- [ ] **Step 2: Read current stock page**

```bash
cat apps/web/src/app/stocks/\[ticker\]/page.tsx
```

- [ ] **Step 3: Place the button near the StockMetaBar or top area**

In `apps/web/src/app/stocks/[ticker]/page.tsx`, import:
```tsx
import { AddToWatchlistButton } from "@/components/AddToWatchlistButton";
```
And place `<AddToWatchlistButton ticker={ticker} market={market} />` next to the ticker heading (near `<StockMetaBar ... />` — exact placement depends on current layout; prefer a sibling of the header h1).

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/AddToWatchlistButton.tsx apps/web/src/app/stocks
git commit -m "feat(web): AddToWatchlistButton on stock detail page"
```

---

## Task 22: End-to-end smoke test (manual)

**Files:** none

- [ ] **Step 1: Start backend**

```bash
cd apps/api && uv run uvicorn nq_api.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd apps/web && npm run dev
```

- [ ] **Step 3: Verify flow**

Open http://localhost:3000:
1. Click `Sign up`, enter email, receive magic link
2. Click link → land back on site, navbar shows `FREE` badge + email
3. Click `Watchlist` → empty state
4. Add AAPL/US → appears
5. Try adding 5 more to verify free cap 403s
6. Navigate to `/stocks/AAPL`, click `＋ Watchlist` → `✓ Saved`
7. Click `Sign out` → navbar reverts to `Sign in` / `Sign up`

- [ ] **Step 4: No commit needed — manual only**

---

## Task 23: Deploy-readiness check

**Files:** none

- [ ] **Step 1: Backend env on Render**

In Render dashboard → Service → Environment, add:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

- [ ] **Step 2: Frontend env on Vercel**

In Vercel dashboard → Project → Settings → Environment Variables, add:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_BASE_URL` = `https://neuralquant.onrender.com`

- [ ] **Step 3: Update Supabase allowed redirect URLs**

Supabase → Auth → URL Configuration → add `https://neuralquant.vercel.app/auth/callback`.

- [ ] **Step 4: Push + deploy**

```bash
git push origin master
```
Render auto-redeploys backend. Vercel auto-redeploys frontend.

- [ ] **Step 5: Live smoke test**

Repeat Task 22 steps against https://neuralquant.vercel.app.

---

## Summary

When all 23 tasks complete:
- Users can sign up/in via magic link or Google
- `/auth/me` returns tier from Supabase
- Watchlists CRUD enforced by RLS + tier caps
- Screener, Ask AI, and stock pages remain anonymous-accessible (no regressions)
- Phase 3 feature set fully intact (tests still green)

Next plan: **Pillar A Part 2 — Stripe checkout + rate limiting + tier-gating UI.**
