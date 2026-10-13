# Secret Scan Report — 2026-10-13

**Scope:** Working tree and git history of `github.com/satyamdas03/NeuralQuant` at `origin/master`.
**Method:** `git log --all --oneline -S <prefix>` and `rg` prefix search on working tree. No values extracted or printed.
**Scanner:** Claude Code (manual, read-only).
**Owner action required:** Satyam must rotate any real keys and confirm rotation.

---

## Executive Summary

No real, full secret values were found in the current working tree. The main historical exposure is the audit dump file `NEURALQUANT_MASTER_REPORT_AUDIT_GB`, which contained multiple secret-shaped strings and was committed in `9a8fd6d` and removed in `26bc004`. It remains in git history. Whether those strings were live keys or partial/redacted entries is UNKNOWN from this scan; treat as real until proven otherwise and rotate.

---

## Confirmed Historical Exposure

| File | Commit Introduced | Commit Removed | Key Types Present | Current Status |
|---|---|---|---|---|
| `NEURALQUANT_MASTER_REPORT_AUDIT_GB` | `9a8fd6d` | `26bc004` | `sk-ant-`, `sk_live_`, `whsec_`, `service_role` | Deleted from working tree; remains in git history. |

**Recommendation:** Satyam to decide whether to rewrite history to remove `9a8fd6d` and `26bc004` entirely. Do not rewrite history without explicit owner approval.

---

## Working-Tree Findings

### Files with only env-var names or placeholders (no real values detected)

| File | Key Types Mentioned | Verdict |
|---|---|---|
| `.env.example` | `ANTHROPIC_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PAYPAL_CLIENT_SECRET`, `LIVEKIT_API_SECRET`, `CRON_SECRET`, `SMOKE_TEST_SECRET`, `ADMIN_EMAILS`, etc. | Placeholder template. No values. |
| `apps/api/.env.example` | Same set | Placeholder template. No values. |
| `infra/gcp/.env.example` | Same set | Placeholder template. No values. |
| `render.yaml` | Env var names only | No values committed. |
| `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md` | `sk-ant-`, `whsec_` appeared in history; current file has no full key strings | Likely redacted in `9f01a44`. Current file clean. |
| `docs/superpowers/plans/2026-06-14-security-hardening-p0-p1.md` | `sk-ant-`, `whsec_`, `SERVICE_ROLE` | Documentation/plan text only; truncated placeholders. |
| `docs/superpowers/specs/2026-06-14-security-hardening-p0-p1-design.md` | `service_role` | Design doc text only. |

### Source files that read secrets from environment (expected, not a leak)

These files access `os.environ` for keys but do not contain hardcoded values in the working tree:

| File | Variable(s) |
|---|---|
| `apps/api/src/nq_api/config.py` | Multiple API keys |
| `apps/api/src/nq_api/auth/deps.py` | `CRON_SECRET`, `SMOKE_TEST_SECRET`, `TEAM_API_TOKEN`, `ADMIN_EMAILS` |
| `packages/data/src/nq_data/fmp.py` | `FMP_API_KEY` |
| `packages/data/src/nq_data/finnhub.py` | `FINNHUB_API_KEY` |
| `apps/livekit-agent/src/quantastra/*.py` | `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY` |
| `apps/api/src/nq_api/routes/*.py` | Various service keys |

---

## Git History Findings by Prefix

| Prefix | Commits (hash + message) | Files | Notes |
|---|---|---|---|
| `sk-ant-` | `26bc004`, `9a8fd6d`, `9f01a44`, `930d586`, `e00b8f9`, `a969395` | `NEURALQUANT_MASTER_REPORT_AUDIT_GB`, `apps/api/.env.example`, `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md`, `.env.example`, `docs/superpowers/plans/...` | Current `.env.example` files are clean. Historical audit dump is the exposure. |
| `sk_live_` | `26bc004`, `9a8fd6d` | `NEURALQUANT_MASTER_REPORT_AUDIT_GB` | Only in the audit dump. |
| `whsec_` | `26bc004`, `9a8fd6d`, `9f01a44`, `a969395` | `NEURALQUANT_MASTER_REPORT_AUDIT_GB`, `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md` | Current shutdown plan clean. |
| `service_role` | `26bc004`, `9a8fd6d`, `855e0ac`, `b31c7b2`, `21394b3`, `aebcbba`, `8766c73`, `930d586`, `53d170c`, `3584513c`, `84bf13b`, `985a008` | Audit dump, migrations, README, docs | All current occurrences are SQL comments, design docs, or env var names. No live key. |

---

## Unknowns

1. Whether the strings in `NEURALQUANT_MASTER_REPORT_AUDIT_GB` were live keys or partial/redacted examples.
2. Whether `.env` files or local uncommitted files on Satyam's machine contain real keys.
3. Whether the Render/Vercel dashboards have rotated keys since the audit dump was created.
4. Whether `apps/web/.next/` build output or other generated artifacts contain secret strings (not scanned because build output is gitignored and not present in working tree).

---

## Recommended Owner Actions

1. **Rotate these key types** regardless of whether the audit dump strings were live:
   - Anthropic API key (`sk-ant-...`)
   - Stripe live secret key (`sk_live_...`)
   - Stripe webhook secret (`whsec_...`)
   - Supabase service role key / JWT secret
2. **Confirm rotation** by replying to this report.
3. **Decide on history rewrite** for `NEURALQUANT_MASTER_REPORT_AUDIT_GB` (commits `9a8fd6d` and `26bc004`).
4. **Add CI secret-scan** to the web build output and repo (separate S6 follow-up).

---

## Evidence Commands Used

```bash
# Working tree prefix scan (redacted)
rg -n "sk-ant-|sk_live_|whsec_|service_role|..." .

# Git history prefix scan
git log --all --oneline -S "sk-ant-" --name-only
git log --all --oneline -S "sk_live_" --name-only
git log --all --oneline -S "whsec_" --name-only
git log --all --oneline -S "service_role" --name-only
```

No secret values were printed in this report.
