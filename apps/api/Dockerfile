# Build context MUST be the repo root: `docker build -f apps/api/Dockerfile .`
FROM python:3.12-slim
WORKDIR /app

# Install uv
RUN pip install uv

# Copy workspace packages first (for layer caching)
COPY packages/ /workspace/packages/
COPY pyproject.toml /workspace/pyproject.toml
COPY uv.lock /workspace/uv.lock

# Copy the API package
COPY apps/api/ /app/

# Install everything (including slack-bolt from pyproject.toml dependencies)
RUN cd /workspace && uv sync --frozen --no-dev && \
    uv pip install --system -e /app && \
    pip install "slack-bolt>=1.18" "slack-sdk>=3.21"

EXPOSE 10000

# Render sets PORT env var; use it at runtime
CMD uvicorn nq_api.main:app --host 0.0.0.0 --port ${PORT:-10000}