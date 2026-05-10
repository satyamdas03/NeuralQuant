FROM python:3.11-slim

# Install OpenBB Platform API + providers
# Equity + yfinance bundled with openbb-core
# FRED provider for macro data (requires FRED_API_KEY env var)
RUN pip install --no-cache-dir openbb-platform-api openbb-equity openbb-yfinance openbb-fred openbb-federal-reserve openbb-tradier

EXPOSE 6900

# Health check: OpenBB serves /docs (Swagger UI)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/docs')" || exit 1

# FRED_API_KEY must be set via env var for FRED data
CMD ["openbb-api", "--host", "0.0.0.0", "--port", "6900"]