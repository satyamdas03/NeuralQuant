FROM python:3.11-slim

# Install OpenBB Platform API (includes core + FastAPI server)
# Individual extension packages are auto-discovered at runtime
RUN pip install --no-cache-dir openbb-platform-api

# yfinance provider is bundled with openbb-core
# No need for separate extension packages - they auto-register

EXPOSE 6900

# Health check: OpenBB serves /docs (Swagger UI)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/docs')" || exit 1

CMD ["openbb-api", "--host", "0.0.0.0", "--port", "6900"]