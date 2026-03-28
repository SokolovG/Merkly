FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies into .venv (no dev deps in prod)
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data/profiles /app/data/sessions

# Run directly with the venv Python — no re-sync on startup
CMD ["/app/.venv/bin/python", "-m", "src.main"]
