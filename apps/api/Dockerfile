# Build context MUST be the repo root: `docker build -f apps/api/Dockerfile .`
FROM python:3.12-slim
WORKDIR /workspace

# Install uv
RUN pip install uv

# Copy full repo (respects .dockerignore)
COPY . .

# Sync workspace — installs nq-data, nq-signals, slack-bolt, everything into .venv
RUN uv sync --frozen --no-dev

EXPOSE 10000

# Render sets PORT env var; uv run ensures venv is active
CMD uv run uvicorn nq_api.main:app --host 0.0.0.0 --port ${PORT:-10000}
