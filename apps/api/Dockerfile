# Build context MUST be the repo root: `docker build -f apps/api/Dockerfile .`
FROM python:3.12-slim
WORKDIR /workspace

# Install uv
RUN pip install uv

# Dependency layer: manifests only, so code edits don't re-download ~3GB of deps
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY apps/livekit-agent/pyproject.toml apps/livekit-agent/
COPY packages/data/pyproject.toml packages/data/
COPY packages/signals/pyproject.toml packages/signals/
RUN uv sync --frozen --no-dev --no-install-workspace

# Copy full repo (respects .dockerignore) and install the workspace packages
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 10000

# Render sets PORT env var; uv run ensures venv is active
CMD uv run uvicorn nq_api.main:app --host 0.0.0.0 --port ${PORT:-10000}
