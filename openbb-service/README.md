# OpenBB Service for NeuralQuant

Self-hosted OpenBB Platform API for NeuralQuant's data enrichment.

## Quick Start

1. Push this directory to GitHub as `satyamdas03/openbb-service`
2. Create a new Render Web Service from this repo
3. Set environment variables:
   - `OPENBB_API_HOST=0.0.0.0`
   - `OPENBB_API_PORT=6900`
4. Deploy and get the URL (e.g. `https://nq-openbb.onrender.com`)
5. Update NeuralQuant's env vars:
   - `OPENBB_ENABLED=true`
   - `OPENBB_API_URL=https://nq-openbb.onrender.com`

## API Endpoints Available

Once running, OpenBB serves:
- `/api/v1/equity/price/quote` - Real-time quotes
- `/api/v1/equity/price/historical` - Historical OHLCV
- `/api/v1/equity/fundamental/historical_dividends` - Dividend history
- `/api/v1/equity/fundamental/balance_sheet` - Balance sheets
- `/api/v1/equity/fundamental/income_statement` - Income statements
- `/api/v1/equity/ownership` - Institutional ownership
- `/api/v1/derivatives/options/chains` - Options chains
- `/api/v1/derivatives/options/snapshots` - IV percentile, P/C ratio
- `/api/v1/fixedincome/government/yield_curve` - Treasury yield curve
- `/api/v1/economy/cpi` - Consumer Price Index
- `/api/v1/economy/fred_series` - Any FRED series

## Health Check

OpenBB serves Swagger UI at `/docs` — use this as Render's health check path.