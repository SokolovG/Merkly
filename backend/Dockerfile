FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests (root-level — backend deps live here)
COPY pyproject.toml uv.lock ./

# Install production deps into .venv
RUN uv sync --frozen --no-dev

# Copy source
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY backend/ ./backend/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
