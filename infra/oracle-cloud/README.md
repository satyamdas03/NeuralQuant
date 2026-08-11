# NeuralQuant on Oracle Cloud Free Tier

This kit moves the **"now + safe"** slice of the stack to Oracle Cloud Always Free resources:

- **Hermes** (now) — crypto paper-trading agent + state API
- **nq-trader** (safe) — Alpaca paper-trading daemon
- **quantastra-agent** (safe) — LiveKit voice companion
- **4 cron jobs** (safe) — anjali refresh, market refresh, nightly score US/IN

## Free tier limits (2026)

- **Ampere A1 (ARM) compute**: up to **2 OCPUs + 12 GB RAM** total per tenancy.
- **Block Volume**: 200 GB included.
- **Outbound data**: 10 TB/month.

Sources: [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/), [OCI Free Tier docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), [InfoQ on 2026 limit reduction](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/).

## What fits for free

On a single `VM.Standard.A1.Flex` with 2 OCPU + 12 GB RAM you can run all four groups above with comfortable headroom:

| Service | CPU limit | RAM limit | Purpose |
|---|---|---|---|
| Hermes | 0.75 | 1.5 GB | crypto paper-trading state API |
| nq-trader | 0.50 | 1.0 GB | Alpaca paper-trading daemon |
| quantastra-agent | 0.50 | 1.5 GB | LiveKit voice agent |
| Caddy | 0.25 | 256 MB | reverse proxy + TLS |
| cron | transient | ≤ 1 GB | 4 scheduled cron_invoke jobs |
| **Total reserved** | **~2.0** | **~5.25 GB** | leaves ~6.7 GB for kernel/builds |

## What stays managed

- **nq-api** stays on Render (user-facing core API).
- **nq-openbb** stays on Render (heavy Terminal image; out of scope for "safe" move).
- **Next.js frontend** stays on Vercel (free + global CDN).
- **Supabase** stays managed (auth, RLS, realtime, storage, backups).

## Provisioning steps

1. Create an Oracle Cloud Free Tier account and provision an **Ampere A1** VM (Ubuntu 22.04/24.04 ARM).
2. Add ingress rules for TCP **22, 80, 443** in the VCN security list.
3. SSH in and run `setup.sh`:
   ```bash
   sudo bash setup.sh
   ```
4. Copy `.env.example` to `.env` and fill all secrets:
   ```bash
   cd /opt/neuralquant/infra/oracle-cloud
   cp .env.example .env
   # edit .env
   ```
5. (Optional) Migrate Hermes state from Railway/local:
   ```bash
   # if you have a local tar of Railway's /app/state:
   sudo tar -xzf hermes-state-backup.tar.gz -C /opt/neuralquant/hermes-trading/
   # or just use the existing submodule state directory
   ```
6. Build and start the services:
   ```bash
   docker compose up -d --build
   ```
7. Point Render `nq-api` env vars at the new Oracle VM:
   - `HERMES_API_URL` — `http://<VM_PUBLIC_IP>/hermes` or `https://hermes.yourdomain.com/hermes`
   - `HERMES_API_SECRET` — same value as in `.env`
8. Verify:
   ```bash
   curl http://<VM_PUBLIC_IP>/health
   curl http://<VM_PUBLIC_IP>/hermes/health
   docker compose ps
   docker compose logs -f hermes nq-trader quantastra-agent
   ```

## Railway cleanup

After Hermes is live on Oracle:

1. Stop and delete the `zonal-curiosity` service/project via the Railway dashboard or CLI.
2. Delete the `zonal-curiosity-volume` volume.
3. Close/cancel the Railway account if no other paid services are needed.

## Migration checklist

- [ ] Oracle VM provisioned and SSH works
- [ ] Firewall 80/443 open
- [ ] `.env` populated on VM
- [ ] `docker compose up -d --build` succeeds
- [ ] Hermes `/health` responds
- [ ] nq-trader logs show scanning
- [ ] quantastra-agent logs show LiveKit connection
- [ ] Cron jobs installed (`sudo -u neuralquant crontab -l`)
- [ ] Render `HERMES_API_URL` / `HERMES_API_SECRET` updated
- [ ] `/hermes` page on frontend loads live data
- [ ] Railway service deleted and account closed
