# Hermes on Google Cloud Free Tier

Moves **Hermes** (crypto paper-trading agent + state API) to a GCP Always Free
`e2-micro` VM. This is the free-forever home for Hermes after Railway's trial
expired and Oracle was rejected.

## Why GCP (vs Oracle)

| | GCP e2-micro | Oracle A1 |
|---|---|---|
| Free forever | ✅ Always Free (no expiry) | ✅ but idle-reclaim risk |
| RAM | 1 GB | 12 GB |
| vCPU | 2 shared (burstable) | 2 OCPU ARM |
| Disk | 30 GB HDD | 200 GB |
| Egress | 1 GB/month | 10 TB/month |

GCP is the only major cloud with a **permanent** free VM (AWS/Azure free VMs
expire after 12 months). The trade-off is **1 GB RAM** — enough for Hermes
alone, not the full Oracle stack.

## What runs here (Hermes ONLY)

The 1 GB RAM e2-micro cannot host `nq-trader`, `quantastra-agent`, or the cron
jobs (those need ~5 GB combined). They stay on Render for now.

| Service | Runs here? |
|---|---|
| Hermes (crypto paper-trading + state API) | ✅ yes |
| nq-trader (Alpaca daemon) | ❌ stays on Render |
| quantastra-agent (LiveKit voice) | ❌ stays on Render |
| cron jobs (anjali/market/nightly) | ❌ stays on Render |

## Free tier limits (2026)

- **1** `e2-micro` VM (2 shared vCPU, **1 GB RAM**) — free only in `us-west1`,
  `us-central1`, `us-east1`.
- **30 GB** standard persistent disk.
- **1 GB** egress/month (fine for a trading agent's small API calls).
- External IP is **not** included in free tier — use the ephemeral IP (free) and
  accept it changes on VM restart, or pay ~$3/mo for a static IP.

Sources: [Google Cloud Free](https://cloud.google.com/free) · [GCP Free Tier Guide 2026](https://agentdeals.dev/gcp-free-tier-2026)

## Provisioning steps

1. **Create a GCP account** (credit card required for signup; $0 charged if you
   stay in free tier). Set a **budget alert at $1** immediately
   (Billing → Budgets & alerts) so you're notified before any overage.
2. **Create the VM** (Compute Engine → Create instance):
   - Region: `us-central1` (or `us-west1` / `us-east1`)
   - Machine type: `e2-micro`
   - Boot disk: Ubuntu 24.04 LTS, 30 GB standard persistent disk
   - Allow HTTP traffic (or add a firewall rule for TCP `8000`)
3. **SSH in** (Cloud Console → SSH button, or `gcloud compute ssh`).
4. **Run the setup script** (copy-paste or download from this repo):
   ```bash
   curl -LsSf https://raw.githubusercontent.com/satyamdas03/NeuralQuant/master/infra/gcp/setup.sh | sudo bash
   ```
5. **Fill secrets** in `/opt/hermes/.env`:
   ```bash
   sudo nano /opt/hermes/.env
   # set HERMES_API_SECRET (any long random string) and ANTHROPIC_API_KEY
   ```
6. **Start Hermes**:
   ```bash
   sudo systemctl start hermes
   sudo systemctl status hermes
   ```
7. **Open firewall port 8000** (VPC network → Firewall → add rule: tcp:8000,
   source 0.0.0.0/0) so Render's nq-api can reach the state API.
8. **Point Render at Hermes** — update nq-api env vars:
   - `HERMES_API_URL` → `http://<VM_EXTERNAL_IP>:8000`
   - `HERMES_API_SECRET` → same value as `/opt/hermes/.env`
9. **Verify**:
   ```bash
   curl http://<VM_EXTERNAL_IP>:8000/health
   curl -H "X-Hermes-Secret: <secret>" http://<VM_EXTERNAL_IP>:8000/status
   ```

## Updating Hermes

```bash
sudo bash /opt/hermes/../infra/gcp/deploy.sh   # if repo cloned
# or manually:
sudo -u hermes bash -c 'cd /opt/hermes && git pull origin main && ~/.local/bin/uv sync'
sudo systemctl restart hermes
```

## India price feed (autonomous cron)

Render's outbound IPs are blocked by Yahoo, so `market_refresh` cannot fetch
Indian prices directly. The GCP VM's IP works, so we run a lightweight feeder
here that writes IN prices to the same `stock_snapshot` table.

Setup:
```bash
sudo bash /opt/neuralquant/infra/gcp/setup_india_feed.sh
sudo nano /opt/neuralquant/apps/api/.env   # add SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
sudo /opt/neuralquant/venv/bin/python /opt/neuralquant/infra/gcp/india_feed.py
```

The feeder runs every 15 minutes during Indian market hours
(09:15–15:30 IST = 03:45–10:00 UTC, Mon–Fri). It is a short-lived cron process,
so memory is freed after each run.

Render's in-process scheduler now refreshes **US only**; IN rows are owned by
this GCP feeder. A manual `/cron/market-refresh?market=IN` on Render still falls
back to the `nq-openbb` service as a safety net.

## OOM safety

The e2-micro's 1 GB RAM is tight for Python + pandas + numpy + ccxt + FastAPI
plus the periodic India feeder. `setup.sh` adds a **2 GB swap file** as an OOM
safety net. The feeder is a short-lived cron, so it only briefly spikes memory.
If you see OOM kills in `journalctl -u hermes`, the fallback is `e2-small`
(2 GB RAM, ~$7/mo) — a later call, not now.

## Railway cleanup

After Hermes is live on GCP:
1. Stop/delete the Railway `zonal-curiosity` service + volume.
2. Close the Railway account if no other paid services remain.
