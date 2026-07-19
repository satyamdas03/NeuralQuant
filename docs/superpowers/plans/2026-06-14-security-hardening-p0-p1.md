# Security Hardening P0 + P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-severity security gaps — stop leaking secrets/PII in logs, lock down the smoke bypass, add CI secret scanning, audit every user-data route for IDOR, and enable Supabase RLS as a defense-in-depth net.

**Architecture:** Backend FastAPI (`nq_api`). All DB access currently uses the Supabase `service_role` key (bypasses RLS), so cross-user safety depends on app-layer `user_id` scoping — P1 both audits that (IDOR) and adds RLS underneath as a net. P0 stops secret/PII leakage and adds scanning.

**Tech Stack:** Python/FastAPI/pytest, Supabase Postgres (RLS/SQL), GitHub Actions (gitleaks).

Branch: `session92-security-p0-p1`. Spec: `docs/superpowers/specs/2026-06-14-security-hardening-p0-p1-design.md`.

---

## Task 1: Log redaction (stop secrets/PII reaching logs)

**Files:**
- Create: `apps/api/src/nq_api/logging_redaction.py`
- Modify: `apps/api/src/nq_api/main.py` (call installer at startup)
- Test: `apps/api/tests/test_logging_redaction.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_logging_redaction.py`:

```python
import logging
from nq_api.logging_redaction import redact, RedactingFilter


def test_redacts_apikey_query():
    assert redact("GET https://x.com/q?symbol=AAPL&apikey=REDACTEDKEY1234567890ABCDEFGHI") \
        == "GET https://x.com/q?symbol=AAPL&apikey=***"


def test_redacts_bearer():
    assert redact("Authorization: Bearer eyJhbG.cit.zzz") == "Authorization: Bearer ***"


def test_redacts_email():
    assert "***@***" in redact("user satyamdas03@gmail.com logged in")


def test_clean_text_unchanged():
    assert redact("nothing secret here") == "nothing secret here"


def test_filter_mutates_record():
    f = RedactingFilter()
    rec = logging.LogRecord("n", logging.INFO, __file__, 1,
                            "key apikey=SECRETVALUE1234567890", None, None)
    assert f.filter(rec) is True
    assert "SECRETVALUE1234567890" not in rec.getMessage()
```

- [ ] **Step 2: Run — confirm fail**

Run: `cd apps/api && python -m pytest tests/test_logging_redaction.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the redaction module**

Create `apps/api/src/nq_api/logging_redaction.py`:

```python
"""Scrub secrets and PII from log records before they are emitted."""
from __future__ import annotations

import logging
import re

_PATTERNS = [
    (re.compile(r"(apikey=)[A-Za-z0-9_\-]+", re.I), r"\1***"),
    (re.compile(r"(api[_-]?key\"?\s*[:=]\s*\"?)[A-Za-z0-9_\-]{8,}", re.I), r"\1***"),
    (re.compile(r"(token=)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***"),
]


def redact(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    """Mutates each record's message in place so no handler emits a secret/PII."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            red = redact(msg)
            if red != msg:
                record.msg = red
                record.args = ()
        except Exception:
            pass
        return True


def install_log_redaction() -> None:
    """Attach the redaction filter to the root logger and all its handlers, and
    silence httpx/httpcore URL logging (which printed apikey= query strings)."""
    root = logging.getLogger()
    f = RedactingFilter()
    root.addFilter(f)
    for h in list(root.handlers):
        h.addFilter(f)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

- [ ] **Step 4: Run — confirm pass**

Run: `cd apps/api && python -m pytest tests/test_logging_redaction.py -v`
Expected: 5 passed.

- [ ] **Step 5: Wire into app startup**

In `apps/api/src/nq_api/main.py`, near the top after `log = logging.getLogger(__name__)` (line ~15), add an import and call it at module import so it covers every logger:

```python
from nq_api.logging_redaction import install_log_redaction
install_log_redaction()
```

Also add it inside the FastAPI startup handler if one exists (so it re-applies after uvicorn installs its handlers). Find the startup event (`@app.on_event("startup")` or lifespan) and add `install_log_redaction()` as its first line. If no startup hook exists, the module-level call is sufficient — note that and skip.

- [ ] **Step 6: Sanity-import + commit**

Run: `cd apps/api && python -c "import nq_api.main" 2>&1 | tail -3` (import may pull heavy deps; if it fails for an unrelated missing dep, instead run `python -c "import nq_api.logging_redaction"`)
```bash
git add apps/api/src/nq_api/logging_redaction.py apps/api/src/nq_api/main.py apps/api/tests/test_logging_redaction.py
git commit -m "security(logs): redact apikey/bearer/email from logs + silence httpx URL logging"
```

---

## Task 2: Smoke-secret lockdown

**Files:**
- Modify: `apps/api/src/nq_api/auth/deps.py`
- Test: `apps/api/tests/test_smoke_bypass.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_smoke_bypass.py`:

```python
from nq_api.auth import deps


def test_bypass_inactive_when_unset(monkeypatch):
    monkeypatch.delenv("SMOKE_TEST_SECRET", raising=False)
    assert deps._smoke_bypass_ok("anything") is False


def test_bypass_inactive_when_secret_too_short(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST_SECRET", "short")
    assert deps._smoke_bypass_ok("short") is False


def test_bypass_active_when_strong_and_matches(monkeypatch):
    secret = "x" * 24
    monkeypatch.setenv("SMOKE_TEST_SECRET", secret)
    assert deps._smoke_bypass_ok(secret) is True
    assert deps._smoke_bypass_ok("wrong") is False
```

- [ ] **Step 2: Run — confirm fail**

Run: `cd apps/api && python -m pytest tests/test_smoke_bypass.py -v`
Expected: FAIL — `_smoke_bypass_ok` does not exist.

- [ ] **Step 3: Add the helper and use it in both bypass sites**

In `apps/api/src/nq_api/auth/deps.py`, add near the top (after imports):

```python
def _smoke_bypass_ok(provided: str | None) -> bool:
    """Only honor the smoke bypass when a STRONG secret (>=24 chars) is set and
    matches. Prevents a weak/empty SMOKE_TEST_SECRET from enabling the bypass."""
    secret = os.environ.get("SMOKE_TEST_SECRET", "")
    return bool(secret) and len(secret) >= 24 and provided == secret
```

Then in `get_current_user_optional` replace:
```python
    _smoke_secret = os.environ.get("SMOKE_TEST_SECRET", "")
    if _smoke_secret and x_smoke_secret == _smoke_secret:
```
with:
```python
    if _smoke_bypass_ok(x_smoke_secret):
```
And the identical block in `get_current_user_smoke` the same way. Remove the now-unused `_smoke_secret = ...` lines in both.

- [ ] **Step 4: Run — confirm pass + regression**

Run: `cd apps/api && python -m pytest tests/test_smoke_bypass.py tests/test_auth_jwt.py -v`
Expected: smoke tests pass; existing auth tests still pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/auth/deps.py apps/api/tests/test_smoke_bypass.py
git commit -m "security(auth): smoke bypass requires a strong (>=24 char) SMOKE_TEST_SECRET"
```

---

## Task 3: CI secret scanning (gitleaks)

**Files:**
- Create: `.github/workflows/secret-scan.yml`
- Create: `.gitleaks.toml`

- [ ] **Step 1: Add the gitleaks config**

Create `.gitleaks.toml`:

```toml
title = "NeuralQuant gitleaks config"

[extend]
useDefault = true

[allowlist]
description = "Allowlisted paths (examples, docs, lockfiles)"
paths = [
  '''.*\.env\.example$''',
  '''.*\.md$''',
  '''package-lock\.json$''',
  '''pnpm-lock\.yaml$''',
]
```

- [ ] **Step 2: Add the workflow**

Create `.github/workflows/secret-scan.yml`:

```yaml
name: secret-scan
on:
  push:
  pull_request:
jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITLEAKS_CONFIG: .gitleaks.toml
```

- [ ] **Step 3: Verify the config is valid locally (best-effort)**

If `gitleaks` is installed locally, run `gitleaks detect --config .gitleaks.toml --no-banner` from the repo root and confirm it exits without flagging real secrets in the working tree. If not installed, skip — the GitHub Action will run it. (If it flags a *historical* secret, that secret must be rotated; add a narrowly-scoped allowlist entry only after rotation.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/secret-scan.yml .gitleaks.toml
git commit -m "security(ci): add gitleaks secret scanning on push + PR"
```

---

## Task 4: Client-bundle secret verification

**Files:** none (verification only; fix only if a leak is found)

- [ ] **Step 1: Grep the web app for non-public secrets**

Run from repo root:
```bash
grep -rniE "SERVICE_ROLE|sk-ant-|FMP_API_KEY|ELEVENLABS_API_KEY|ANTHROPIC_API_KEY|DEEPGRAM_API_KEY|SUPABASE_JWT_SECRET" apps/web/src apps/web/public 2>/dev/null | grep -v NEXT_PUBLIC
```
Expected: **no output**. Only `NEXT_PUBLIC_*` vars (Supabase anon key, public API URL) may appear in `apps/web`.

- [ ] **Step 2: If anything is found**, move that value server-side (it must never ship to the browser): route the call through nq-api instead of the client, and delete the client reference. Re-run Step 1 until clean. If clean, record "client bundle clean — no server secrets exposed" in the operator-actions doc (Task 7).

---

## Task 5: IDOR audit + fixes

**Files:**
- Create: `docs/SECURITY_IDOR_AUDIT.md`
- Modify: any route found to leak (per findings)
- Test: focused regression tests for each fix

This task is investigative. For each user-owned table, read the routes that touch it and verify every read/write is scoped to the **authenticated** `user.id` from `get_current_user` (never a client-supplied id used unchecked).

- [ ] **Step 1: Audit each route against the rule**

Read each file and check every DB call on a user-owned table:

| Table | Files to read |
|---|---|
| users | `auth/deps.py` |
| watchlists | `routes/watchlists.py`, `routes/astra_portfolio.py` |
| alerts | `routes/alerts.py` |
| conversations | `routes/query.py` |
| user_events | `routes/analytics.py`, `routes/analytics_track.py`, `routes/livekit_token.py`, `routes/share.py` |
| user_profiles | `routes/auth.py`, `routes/astra_portfolio.py`, `routes/cron.py` |
| user_sessions / session_activities / session_reports | `routes/session.py`, `session_analysis.py` |
| shared_analyses | `routes/share.py`, `routes/analytics.py` (PUBLIC-by-link — see Step 3) |
| teams / team_members | `routes/team.py` |

**Audit rule for each call:**
1. Mutations (`POST/PATCH/DELETE`) set or match `user_id == user.id`.
2. Reads filter `user_id=eq.{user.id}` (or join through an owned row, e.g. session_activities → user_sessions).
3. Any id taken from request body/query/path is **re-validated** to belong to `user.id` before use.
4. `cron.py` runs as a trusted job (no per-user request) — note it operates server-side and is gated by the cron secret, not user auth; that's acceptable, record it.

- [ ] **Step 2: Write the audit doc as you go**

Create `docs/SECURITY_IDOR_AUDIT.md` with one row per route:

```markdown
# IDOR Audit — user-data routes (2026-06-14)

| Route (method path) | Table | Scoped to user.id? | Verdict | Action |
|---|---|---|---|---|
| GET /watchlist | watchlists | yes (user_id=eq.user.id) | PASS | none |
| ... | ... | ... | PASS/FAIL | fix ref |
```

- [ ] **Step 3: Fix any violation (example pattern)**

A violating read like:
```python
rows = _rest("GET", "watchlists", query={"select": "*"})  # NO user filter — IDOR
```
must become:
```python
rows = _rest("GET", "watchlists", query={"select": "*", "user_id": f"eq.{user.id}"})
```
A mutation that trusts a client `user_id` must be forced to the authenticated id:
```python
body["user_id"] = str(user.id)  # never trust client-supplied owner
```
For `shared_analyses`: read-by-slug for the public view is intentional (capability URL); but the *owner list/delete* endpoints must filter by `user_id=eq.user.id`. Confirm the share slug is high-entropy (UUID/random) — if it is sequential/guessable, record it as a P3 follow-up.

- [ ] **Step 4: Add a regression test per fix**

For each fixed route, add a test that mocks the REST helper and asserts the `user_id` filter is present, e.g. in `apps/api/tests/test_idor_<route>.py`:
```python
def test_watchlist_query_is_user_scoped(monkeypatch):
    captured = {}
    def fake_rest(method, table, query=None, body=None):
        captured["query"] = query or {}
        return []
    monkeypatch.setattr("nq_api.routes.watchlists._rest", fake_rest)
    # ... call the route function with a User(id="U1", ...) ...
    assert captured["query"].get("user_id") == "eq.U1"
```
(Adapt to the actual route's helper + signature. If a route can't be unit-tested without heavy wiring, record it as "verified by code review" in the audit doc instead.)

- [ ] **Step 5: Commit**

```bash
git add docs/SECURITY_IDOR_AUDIT.md apps/api/src/nq_api/routes apps/api/tests
git commit -m "security(authz): IDOR audit of user-data routes + scoping fixes"
```

---

## Task 6: Enable RLS (defense-in-depth) — SQL migration

**Files:**
- Create: `apps/api/migrations/020_enable_rls.sql`

This migration is applied by the operator in the Supabase SQL editor (same as prior migrations). `service_role` (the backend) bypasses RLS, so applying it does **not** change backend behavior — it only adds a net for anon/authenticated direct-Supabase access.

- [ ] **Step 1: Write the migration**

Create `apps/api/migrations/020_enable_rls.sql`:

```sql
-- 020_enable_rls.sql — defense-in-depth row level security.
-- service_role bypasses RLS, so the nq-api backend is unaffected.
-- Apply in Supabase SQL editor. Verify each table's owning column first
-- (most are user_id; users uses id; session_activities joins user_sessions).

-- Helper note: auth.uid() is the authenticated user's UUID.

-- ---- tables owned directly via user_id ----
do $$
declare t text;
begin
  foreach t in array array[
    'watchlists','alerts','conversations','user_events',
    'user_profiles','user_sessions','session_reports'
  ]
  loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists owner_all on public.%I;', t);
    execute format(
      'create policy owner_all on public.%I for all to authenticated '
      'using (user_id = auth.uid()) with check (user_id = auth.uid());', t);
  end loop;
end $$;

-- ---- users: owned via id ----
alter table public.users enable row level security;
drop policy if exists owner_self on public.users;
create policy owner_self on public.users for all to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

-- ---- session_activities: owned via parent user_sessions ----
alter table public.session_activities enable row level security;
drop policy if exists owner_via_session on public.session_activities;
create policy owner_via_session on public.session_activities for all to authenticated
  using (session_id in (select id from public.user_sessions where user_id = auth.uid()))
  with check (session_id in (select id from public.user_sessions where user_id = auth.uid()));

-- ---- shared_analyses: PUBLIC read-by-link, owner-only write ----
alter table public.shared_analyses enable row level security;
drop policy if exists public_read on public.shared_analyses;
drop policy if exists owner_write on public.shared_analyses;
-- anyone (anon + authenticated) may SELECT a row (capability = the unguessable id/slug);
-- PostgREST callers must filter by id, so no blanket enumeration in practice.
create policy public_read on public.shared_analyses for select to anon, authenticated using (true);
create policy owner_write on public.shared_analyses for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ---- teams / team_members: members only ----
alter table public.teams enable row level security;
alter table public.team_members enable row level security;
drop policy if exists member_access on public.team_members;
create policy member_access on public.team_members for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists team_member_access on public.teams;
create policy team_member_access on public.teams for select to authenticated
  using (id in (select team_id from public.team_members where user_id = auth.uid()));

-- ---- verification (run as a normal authenticated user, expect only own rows) ----
-- set role authenticated; select set_config('request.jwt.claim.sub', '<a-user-uuid>', true);
-- select count(*) from public.watchlists;   -- should equal that user's rows only
```

- [ ] **Step 2: Validate SQL parses (best-effort)**

If `psql`/a local Postgres is available, run the file against a scratch DB to confirm it parses. Otherwise eyeball for syntax. (Do NOT run it against production here — the operator applies it.) Note any table whose owning column differs from the assumption (from the Task 5 audit) and correct the migration before handing off.

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/020_enable_rls.sql
git commit -m "security(db): RLS migration enabling per-user policies (service_role bypasses)"
```

---

## Task 7: Operator actions doc (key rotation + RLS apply)

**Files:**
- Create: `docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md`

- [ ] **Step 1: Write the operator runbook**

Create `docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md`:

```markdown
# Security P0/P1 — Operator Actions (do these by hand)

## 1. Rotate the leaked FMP key (URGENT)
The FMP API key was exposed in logs/chat — it is burned.
1. FMP dashboard → API keys → revoke the old key, generate a new one.
2. Update `FMP_API_KEY` on Render (nq-api + any worker) and in local `.env`.
3. Redeploy nq-api. Verify a stock query returns prices.
4. Review whether any OTHER key (Anthropic, ElevenLabs, Deepgram, Supabase) transited logs/chat; rotate any that did.

## 2. Apply the RLS migration
1. Supabase Dashboard → SQL Editor → paste `apps/api/migrations/020_enable_rls.sql` → Run.
2. Run the verification block at the bottom as a sample user; confirm only that user's rows return.
3. Smoke-test the app end-to-end (the backend uses service_role and bypasses RLS, so nothing should break; this confirms no frontend path relied on cross-user anon access).

## 3. Smoke secret hygiene
- Ensure `SMOKE_TEST_SECRET` is **unset** on production nq-api. Set it (>=24 random chars) only transiently when running smoke tests, then unset.

## 4. Confirm CI secret scan is green
- After pushing, check the `secret-scan` GitHub Action passes. If it flags a historical secret, rotate that secret and (only then) add a scoped allowlist entry.
```

- [ ] **Step 2: Commit**

```bash
git add docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md
git commit -m "docs(security): operator runbook for key rotation + RLS apply + smoke hygiene"
```

---

## Final verification
- [ ] `cd apps/api && python -m pytest tests/test_logging_redaction.py tests/test_smoke_bypass.py -v` — green
- [ ] `grep -rniE "SERVICE_ROLE|sk-ant-|FMP_API_KEY" apps/web/src apps/web/public | grep -v NEXT_PUBLIC` — no output
- [ ] `docs/SECURITY_IDOR_AUDIT.md` exists; every user-data route is PASS or has a committed fix
- [ ] `apps/api/migrations/020_enable_rls.sql` written; operator doc lists the apply steps
- [ ] Branch pushed; PR/merge per the usual flow

## Deploy-time / operator (not code)
- Rotate FMP key + redeploy nq-api · Apply RLS migration in Supabase · Keep `SMOKE_TEST_SECRET` unset in prod · Confirm gitleaks Action green.
