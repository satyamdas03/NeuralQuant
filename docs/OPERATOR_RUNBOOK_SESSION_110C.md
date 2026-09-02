# NeuralQuant — Operator Runbook (Session 110c)

Post-code-health non-code tasks required to make the live stack fully clean and secure.
Code status: **green** (`64e9ecf` on `master`, 169 tests passed, Next.js build clean). Blocker fixed: `session.py` no longer references `session_reports.email_sent`, so migration `028_remove_email_schema.sql` is now safe to apply.

---

## 1. GCP VM — India price feeder (fixes IN `change_pct: null`)

**Gap:** `TCS.NS` and `RELIANCE.NS` show `current_price` but `change_pct: null` because Render's IPs are blocked by Yahoo. The GCP e2-micro VM (same one running Hermes) can reach Yahoo.

**Steps:**
```bash
# SSH into the GCP VM
 gcloud compute ssh --zone us-central1-a <vm-name>

# On the VM
sudo bash /opt/neuralquant/infra/gcp/setup_india_feed.sh
sudo nano /opt/neuralquant/apps/api/.env
# Add:
#   SUPABASE_URL=https://<project>.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Test run
sudo /opt/neuralquant/venv/bin/python /opt/neuralquant/infra/gcp/india_feed.py --limit 10

# Watch cron log
sudo tail -f /var/log/india_feed.log
```

**Verify live:**
```bash
curl "https://neuralquant.onrender.com/stocks/TCS.NS?market=IN"
curl "https://neuralquant.onrender.com/stocks/RELIANCE.NS?market=IN"
# Expect non-null change_pct
```

---

## 2. Render — manual deploy `quantastra-agent`

1. [dashboard.render.com](https://dashboard.render.com) → `quantastra-agent` worker
2. **Manual Deploy → Clear build cache & deploy**
3. Wait ~3 min, then test Veronica from the web UI.

---

## 3. Railway cleanup

1. [railway.app](https://railway.app) → project → `zonal-curiosity` service
2. **Settings → Danger → Delete service + persistent volume**
3. Close Railway account if no other paid services remain.

**Pre-check:** `curl https://neuralquant.onrender.com/hermes/health` returns `ok`.

---

## 4. Secret rotation

### CRON_SECRET
- Generate a new 48-char random secret (see generated value in Session 110c chat).
- Update on Render `nq-api` env vars.
- Redeploy `nq-api` (auto-deploy triggers on env change if autoDeploy is on).

### FMP_API_KEY
- [fmp.io](https://fmp.io) dashboard → revoke old key → generate new key.
- Update `FMP_API_KEY` on Render `nq-api` and in local `.env`.
- Verify a US stock query still returns prices.

### HERMES_API_SECRET (optional rotation)
- Generate a new 48-char secret.
- Update both `/opt/hermes/.env` on the GCP VM **and** `HERMES_API_SECRET` on Render `nq-api`.
- Restart Hermes: `sudo systemctl restart hermes`

### SMOKE_TEST_SECRET hygiene
- **Production value should be unset.**
- Only set it transiently (≥24 random chars) when running `scripts/smoke_test.py`, then unset.

---

## 5. Render env — set `ADMIN_EMAILS`

Required for the analytics dashboard to be accessible:
```
ADMIN_EMAILS=satyamdas03@gmail.com
```
Set on Render `nq-api`, then redeploy.

---

## 6. Supabase migrations

Migrations are **not auto-applied**. Apply these in order via Supabase Dashboard → SQL Editor:

1. `supabase/migrations/027_security_events.sql`
2. `supabase/migrations/028_remove_email_schema.sql`
3. `supabase/migrations/029_drop_legacy_email_columns.sql`

All files use `IF NOT EXISTS`, so re-running is safe.

After applying `026_enable_rls.sql` (if not already applied), run the verification block in `docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md`.

---

## 7. GCP VM IP drift check

The VM external IP is ephemeral. If it restarts, update `HERMES_API_URL` on Render.

```bash
# On the VM
curl -s ifconfig.me
```

Compare to the `HERMES_API_URL` value on Render `nq-api`. Update if different.

---

## 8. Final verification

```bash
# Local tests
python -m pytest apps/api/tests packages/ -q --tb=short

# Production smoke (only when SMOKE_TEST_SECRET is transiently set)
python scripts/smoke_test.py

# Spot checks
curl https://neuralquant.onrender.com/health
curl "https://neuralquant.onrender.com/stocks/TCS.NS?market=IN"
curl https://neuralquant.onrender.com/hermes/health
```

Target: 15/15 smoke tests green, IN tickers show `change_pct`, Hermes health `ok`.
