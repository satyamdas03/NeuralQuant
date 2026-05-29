# Anjali → NeuralQuant Automated Data Sync

## Overview
The Anjali repo generates `US_Stock_Analysis_Coloured.xlsx` with pre-computed quintile scores for 1,816+ stocks. NeuralQuant reads this Excel into Supabase for live screener/Ask AI use.

## What Needs to Happen on Every Anjali Data Update

When the Anjali model pushes a new version of `US_Stock_Analysis_Coloured.xlsx` to the repo, the data needs to flow into NeuralQuant's Supabase `anjali_enrichment` table.

## Option A: GitHub Actions Workflow in the Anjali Repo

Add this workflow to `.github/workflows/sync_to_neuralquant.yml` in the Anjali repo:

```yaml
name: Sync Anjali Data to NeuralQuant

on:
  push:
    paths:
      - 'US_Stock_Analysis_Coloured.xlsx'
  workflow_dispatch:  # manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install openpyxl pandas requests

      - name: Checkout NeuralQuant repo
        uses: actions/checkout@v4
        with:
          repository: satyamdas03/NeuralQuant
          token: ${{ secrets.NEURALQUANT_PAT }}
          path: neuralquant

      - name: Install NeuralQuant data package
        run: |
          pip install -e neuralquant/packages/data

      - name: Ingest Anjali Excel to Supabase
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          python neuralquant/scripts/ingest_anjali_excel.py --path US_Stock_Analysis_Coloured.xlsx
```

### Required Secrets in Anjali Repo
Set these in **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | `https://ajkhyayrbqiuvnsmqrdz.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | (get from NeuralQuant's `apps/api/.env`) |
| `NEURALQUANT_PAT` | A GitHub Personal Access Token with `repo` scope on NeuralQuant |

## Option B: Webhook Trigger (NeuralQuant Side)

Alternatively, add a webhook endpoint in NeuralQuant that the Anjali repo calls:

```python
# In apps/api/src/nq_api/routes/anjali.py
@router.post("/api/anjali/sync")
async def trigger_sync(request: Request):
    """Webhook endpoint triggered when Anjali repo updates Excel."""
    # Verify secret
    secret = request.headers.get("X-Anjali-Secret", "")
    if secret != os.environ.get("ANJALI_WEBHOOK_SECRET"):
        raise HTTPException(status_code=401)
    
    # Pull latest Excel from Anjali repo raw URL
    excel_url = "https://raw.githubusercontent.com/satyamdas03/anjali/main/US_Stock_Analysis_Coloured.xlsx"
    # Download, save to temp, run ingestor
    ...
```

Then in the Anjali repo, add a GitHub webhook:
- **Payload URL**: `https://neuralquant.co/api/anjali/sync`
- **Content type**: `application/json`
- **Secret**: `ANJALI_WEBHOOK_SECRET` value
- **Events**: Push events (filter to `.xlsx` files)

## Option C: Scheduled Pull (NeuralQuant Side)

Add a cron job on Render that pulls the Excel nightly:

```yaml
# In render.yaml or via Render dashboard
- type: cron
  name: anjali-sync
  schedule: "0 3 * * *"  # 3 AM UTC
  buildCommand: "pip install -e packages/data openpyxl"
  command: "python scripts/ingest_anjali_excel.py --path /tmp/US_Stock_Analysis_Coloured.xlsx"
  envVars:
    - key: ANJALI_EXCEL_URL
      value: https://raw.githubusercontent.com/satyamdas03/anjali/main/US_Stock_Analysis_Coloured.xlsx
```

The script would first `curl` the Excel from the Anjali repo, then run the ingestor.

## Recommended: Option A (GHA in Anjali Repo)

Simplest approach. The Anjali model that controls the repo should:
1. Add the workflow YAML above to `.github/workflows/`
2. Set the 3 secrets in repo settings
3. Push the workflow — it will auto-trigger on every Excel update

## Excel Column Mapping Reference

The ingestor maps these Excel columns to Supabase:

| Excel Column | DB Column | Notes |
|-------------|-----------|-------|
| Ticker / NseCode | ticker | .NS suffix added for IN market |
| Sector | sector | |
| Sub Sector | sub_sector | |
| Sales YoY Growth | sales_yoy_growth | |
| NetProfit YoY Growth | net_profit_yoy_growth | |
| PE Ratio | pe_ratio | |
| Future PE | future_pe | |
| PB Ratio | pb_ratio | Negative values excluded |
| EV/Sales | ev_sales | |
| RETURN SCORE | return_score | Quintile -4 to +4 |
| GROWTH SCORE | growth_score | Quintile -4 to +4 |
| VALUATION SCORE | valuation_score | Quintile -4 to +4 |
| RISK SCORE | risk_score | Quintile -4 to +4 |
| Alpha (NSE only) | alpha | |
| Final Score (NSE only) | final_score | |
| Rebalance Date (NSE only) | rebalance_date | |

**Composite Anjali Score** = sum of 4 quintile scores (range: -16 to +16)